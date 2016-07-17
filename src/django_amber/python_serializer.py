"""
This is a modified version of django/core/serializers/python.py, which allows
deserialization of fixtures with forward references.  See Django ticket #26291.

A Python "serializer". Doesn't do much serializing per se -- just converts to
and from basic Python data types (lists, dicts, strings, etc.). Useful as a basis for
other serializers.
"""
from __future__ import unicode_literals

from collections import OrderedDict

from django.apps import apps
from django.conf import settings
from django.core.exceptions import ObjectDoesNotExist
from django.core.serializers import base
from django.db import DEFAULT_DB_ALIAS, models
from django.utils import six
from django.utils.encoding import force_text, is_protected_type


class Serializer(base.Serializer):
    """
    Serializes a QuerySet to basic Python objects.
    """

    internal_use_only = True

    def start_serialization(self):
        self._current = None
        self.objects = []

    def end_serialization(self):
        pass

    def start_object(self, obj):
        self._current = OrderedDict()

    def end_object(self, obj):
        self.objects.append(self.get_dump_object(obj))
        self._current = None

    def get_dump_object(self, obj):
        model = obj._meta.proxy_for_model if obj._deferred else obj.__class__
        data = OrderedDict([('model', force_text(model._meta))])
        if not self.use_natural_primary_keys or not hasattr(obj, 'natural_key'):
            data["pk"] = force_text(obj._get_pk_val(), strings_only=True)
        data['fields'] = self._current
        return data

    def handle_field(self, obj, field):
        value = field.value_from_object(obj)
        # Protected types (i.e., primitives like None, numbers, dates,
        # and Decimals) are passed through as is. All other values are
        # converted to string first.
        if is_protected_type(value):
            self._current[field.name] = value
        else:
            self._current[field.name] = field.value_to_string(obj)

    def handle_fk_field(self, obj, field):
        if self.use_natural_foreign_keys and hasattr(field.remote_field.model, 'natural_key'):
            related = getattr(obj, field.name)
            if related:
                value = related.natural_key()
            else:
                value = None
        else:
            value = getattr(obj, field.get_attname())
            if not is_protected_type(value):
                value = field.value_to_string(obj)
        self._current[field.name] = value

    def handle_m2m_field(self, obj, field):
        if field.remote_field.through._meta.auto_created:
            if self.use_natural_foreign_keys and hasattr(field.remote_field.model, 'natural_key'):
                def m2m_value(value):
                    return value.natural_key()
            else:
                def m2m_value(value):
                    return force_text(value._get_pk_val(), strings_only=True)
            self._current[field.name] = [m2m_value(related)
                               for related in getattr(obj, field.name).iterator()]

    def getvalue(self):
        return self.objects


def Deserializer(object_list, **options):
    """
    Deserialize simple Python objects back into Django ORM instances.

    It's expected that you pass the Python objects themselves (instead of a
    stream or a string) to the constructor
    """
    db = options.pop('using', DEFAULT_DB_ALIAS)
    ignore = options.pop('ignorenonexistent', False)
    handle_forward_references = options.pop('handle_forward_references', False)
    field_names_cache = {}  # Model: <list of field_names>

    for d in object_list:
        # Look up the model and starting build a dict of data for it.
        try:
            Model = _get_model(d["model"])
        except base.DeserializationError:
            if ignore:
                continue
            else:
                raise
        data = {}
        if 'pk' in d:
            try:
                data[Model._meta.pk.attname] = Model._meta.pk.to_python(d.get('pk'))
            except Exception as e:
                raise base.DeserializationError.WithData(e, d['model'], d.get('pk'), None)
        m2m_data = {}
        deferred_fields = {}

        if Model not in field_names_cache:
            field_names_cache[Model] = {f.name for f in Model._meta.get_fields()}
        field_names = field_names_cache[Model]

        # Handle each field
        for (field_name, field_value) in six.iteritems(d["fields"]):

            if ignore and field_name not in field_names:
                # skip fields no longer on model
                continue

            if isinstance(field_value, str):
                field_value = force_text(
                    field_value, options.get("encoding", settings.DEFAULT_CHARSET), strings_only=True
                )

            field = Model._meta.get_field(field_name)

            # Handle M2M relations
            if field.remote_field and isinstance(field.remote_field, models.ManyToManyRel):
                model = field.remote_field.model
                if hasattr(model._default_manager, 'get_by_natural_key'):
                    def m2m_convert(value):
                        if hasattr(value, '__iter__') and not isinstance(value, six.text_type):
                            return model._default_manager.db_manager(db).get_by_natural_key(*value).pk
                        else:
                            return force_text(model._meta.pk.to_python(value), strings_only=True)
                else:
                    def m2m_convert(v):
                        return force_text(model._meta.pk.to_python(v), strings_only=True)

                try:
                    m2m_field_values = []
                    for pk in field_value:
                        m2m_field_values.append(m2m_convert(pk))
                except Exception as e:
                    if isinstance(e, ObjectDoesNotExist) and handle_forward_references:
                        deferred_fields[field] = field_value
                        continue
                    raise base.DeserializationError.WithData(e, d['model'], d.get('pk'), pk)

                m2m_data[field.name] = m2m_field_values

            # Handle FK fields
            elif field.remote_field and isinstance(field.remote_field, models.ManyToOneRel):
                model = field.remote_field.model
                if field_value is not None:
                    try:
                        default_manager = model._default_manager
                        field_name = field.remote_field.field_name
                        if hasattr(default_manager, 'get_by_natural_key'):
                            if hasattr(field_value, '__iter__') and not isinstance(field_value, six.text_type):
                                try:
                                    obj = default_manager.db_manager(db).get_by_natural_key(*field_value)
                                except ObjectDoesNotExist:
                                    if handle_forward_references:
                                        deferred_fields[field] = field_value
                                        continue
                                    else:
                                        raise

                                value = getattr(obj, field.remote_field.field_name)
                                # If this is a natural foreign key to an object that
                                # has a FK/O2O as the foreign key, use the FK value
                                if model._meta.pk.remote_field:
                                    value = value.pk
                            else:
                                value = model._meta.get_field(field_name).to_python(field_value)
                            data[field.attname] = value
                        else:
                            data[field.attname] = model._meta.get_field(field_name).to_python(field_value)
                    except Exception as e:
                        raise base.DeserializationError.WithData(e, d['model'], d.get('pk'), field_value)
                else:
                    data[field.attname] = None

            # Handle all other fields
            else:
                try:
                    data[field.name] = field.to_python(field_value)
                except Exception as e:
                    raise base.DeserializationError.WithData(e, d['model'], d.get('pk'), field_value)

        obj = base.build_instance(Model, data, db)
        yield DeserializedObject(obj, m2m_data, deferred_fields)


def _get_model(model_identifier):
    """
    Helper to look up a model from an "app_label.model_name" string.
    """
    try:
        return apps.get_model(model_identifier)
    except (LookupError, TypeError):
        raise base.DeserializationError("Invalid model identifier: '%s'" % model_identifier)


class DeserializedObject(object):
    """
    A deserialized model.

    Basically a container for holding the pre-saved deserialized data along
    with the many-to-many data saved with the object.

    Call ``save()`` to save the object (with the many-to-many data) to the
    database; call ``save(save_m2m=False)`` to save just the object fields
    (and not touch the many-to-many stuff.)
    """

    def __init__(self, obj, m2m_data=None, deferred_fields=None):
        self.object = obj
        self.m2m_data = m2m_data
        self.deferred_fields = deferred_fields

    def __repr__(self):
        return "<DeserializedObject: %s(pk=%s)>" % (
            self.object._meta.label, self.object.pk)

    def save(self, save_m2m=True, using=None, **kwargs):
        # Call save on the Model baseclass directly. This bypasses any
        # model-defined save. The save is also forced to be raw.
        # raw=True is passed to any pre/post_save signals.
        models.Model.save_base(self.object, using=using, raw=True, **kwargs)
        if self.m2m_data and save_m2m:
            for accessor_name, object_list in self.m2m_data.items():
                getattr(self.object, accessor_name).set(object_list)

        # prevent a second (possibly accidental) call to save() from saving
        # the m2m data twice.
        self.m2m_data = None

    def save_deferred_fields(self, using=None):
        if self.deferred_fields is None:
            return

        self.m2m_data = {}

        for field, field_value in self.deferred_fields.items():
            if field.remote_field and isinstance(field.remote_field, models.ManyToManyRel):
                model = field.remote_field.model

                def m2m_convert(value):
                    return model._default_manager.db_manager(using).get_by_natural_key(*value).pk

                try:
                    m2m_field_values = []
                    for pk in field_value:
                        m2m_field_values.append(m2m_convert(pk))
                except Exception as e:
                    opts = self.object._meta
                    label = '{}.{}'.format(opts.app_label, opts.model_name)
                    raise base.DeserializationError.WithData(e, label, self.object.pk, pk)
                self.m2m_data[field.name] = m2m_field_values

            elif field.remote_field and isinstance(field.remote_field, models.ManyToOneRel):
                model = field.remote_field.model
                default_manager = model._default_manager
                field_name = field.remote_field.field_name
                try:
                    obj = default_manager.db_manager(using).get_by_natural_key(*field_value)
                except Exception as e:
                    opts = self.object._meta
                    label = '{}.{}'.format(opts.app_label, opts.model_name)
                    raise base.DeserializationError.WithData(e, label, self.object.pk, field_value)
                value = getattr(obj, field_name)
                if model._meta.pk.remote_field:
                    value = value.pk
                setattr(self.object, field.attname, value)

            else:
                assert False

        self.save()
