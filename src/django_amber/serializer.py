import yaml

try:
    from yaml import CSafeLoader as SafeLoader
except ImportError:
    from yaml import SafeLoader


from django.apps import apps
from django.db import models
from django.core.exceptions import FieldDoesNotExist
from django.core.serializers.base import DeserializationError
from django.core.serializers.python import Serializer as PythonSerializer
from django.core.serializers.pyyaml import DjangoSafeDumper

from .models import parse_dump_path
from .python_serializer import Deserializer as PythonDeserializer


class Serializer(PythonSerializer):
    internal_use_only = False

    def end_serialization(self):
        assert len(self.objects) == 1
        obj = self.objects[0]

        app_label, model_name = obj['model'].split('.')
        model = apps.get_model(app_label, model_name)

        fields = {name: value for name, value in obj['fields'].items() if value}

        fields.pop('key', None)
        fields.pop('content_format', None)
        content = fields.pop('content', None)

        if model.key_structure is not None:
            for field_name in model.field_names_from_key_structure():
                fields.pop(field_name)

        for field_name, field_value in fields.items():
            if is_fk_field(model, field_name):
                assert isinstance(field_value, tuple) and len(field_value) == 1
                fields[field_name] = field_value[0]

            if is_m2m_field(model, field_name):
                assert isinstance(field_value, list) and all(len(v) == 1 for v in field_value)
                fields[field_name] = [v[0] for v in field_value]

            if is_time_field(model, field_name):
                # See comment in django.core.serializers.pyyaml.Serializer.handle_field
                fields[field_name] = str(fields[field_name])

        yaml.dump(fields, self.stream, Dumper=DjangoSafeDumper,
                  default_flow_style=False, **self.options)

        if content is not None:
            self.stream.write('---\n')
            self.stream.write(content)

    def getvalue(self):
        return super(PythonSerializer, self).getvalue()


# Built-in deserializers take either a stream or string, but we require a file,
# because we extract some of the data about the object deserialized in the file
# from its path.
def Deserializer(file, **options):
    model, key, content_format = parse_dump_path(file.name)

    fields = {'key': key}
    fields.update(model.fields_from_key(key))

    data = file.read().decode('utf-8')
    separator = '\n---\n'
    parts = data.split(separator, 1)

    if model.has_content:
        try:
            yaml_fields = yaml.load(parts[0], Loader=SafeLoader)
        except yaml.YAMLError as e:
            raise DeserializationError(e)

        if len(parts) == 1:
            if isinstance(yaml_fields, dict):
                raise DeserializationError('Missing content')

            fields['content'] = parts[0]
        else:
            try:
                fields.update(yaml.load(parts[0], Loader=SafeLoader))
            except yaml.YAMLError as e:
                raise DeserializationError(e)
            fields['content'] = parts[1]

        fields['content_format'] = content_format
    else:
        assert len(parts) == 1
        try:
            fields.update(yaml.load(parts[0], Loader=SafeLoader))
        except yaml.YAMLError as e:
            raise DeserializationError(e)

    for field_name, field_value in fields.items():
        if is_fk_field(model, field_name):
            assert isinstance(field_value, str)
            fields[field_name] = [field_value]

        if is_m2m_field(model, field_name):
            assert isinstance(field_value, list) and all(isinstance(v, str) for v in field_value)
            fields[field_name] = [[v] for v in field_value]

        if is_time_field(model, field_name):
            if isinstance(fields[field_name], int):
                num_seconds = fields[field_name]
                assert 0 <= num_seconds <= 24 * 60 * 60
                hours, minutes_and_seconds = divmod(num_seconds, 60 * 60)
                minutes, seconds = divmod(minutes_and_seconds, 60)
                fields[field_name] = '{}:{}:{}'.format(hours, minutes, seconds)

    record = {
        'model': '{}.{}'.format(model._meta.app_label, model._meta.model_name),
        'fields': fields,
    }

    try:
        yield from PythonDeserializer([record], **options)
    except Exception as e:
        raise DeserializationError(e)


def is_fk_field(model, field_name):
    try:
        field = model._meta.get_field(field_name)
    except FieldDoesNotExist:
        return False

    return field.remote_field and isinstance(field.remote_field, models.ManyToOneRel)


def is_m2m_field(model, field_name):
    try:
        field = model._meta.get_field(field_name)
    except FieldDoesNotExist:
        return False

    return field.remote_field and isinstance(field.remote_field, models.ManyToManyRel)


def is_time_field(model, field_name):
    try:
        field = model._meta.get_field(field_name)
    except FieldDoesNotExist:
        return False

    return isinstance(field, models.TimeField)
