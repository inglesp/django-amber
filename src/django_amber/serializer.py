from collections import defaultdict
import os.path
import re

import yaml

try:
    from yaml import CSafeLoader as SafeLoader
except ImportError:
    from yaml import SafeLoader


from django.apps import apps
from django.db import models
from django.conf import settings
from django.core.exceptions import FieldDoesNotExist
from django.core.serializers.base import DeserializationError
from django.core.serializers.python import Serializer as PythonSerializer
from django.core.serializers.pyyaml import DjangoSafeDumper

from .models import DjangoPagesModel
from .python_serializer import Deserializer as PythonDeserializer


class Serializer(PythonSerializer):
    internal_use_only = False

    def end_serialization(self):
        assert len(self.objects) == 1
        obj = self.objects[0]

        app_label, model_name = obj['model'].split('.')
        model = apps.get_model(app_label, model_name)

        fields = {name: value for name, value in obj['fields'].items() if value}

        for bracketed_field_name in re.findall('\[[\w_]+\]', model.dump_path_template):
            field_name = bracketed_field_name[1:-1]
            if field_name not in ['app_label', 'model_name']:
                fields.pop(field_name, None)

        fields.pop('key', None)
        content = fields.pop('content', None)

        for field_name, field_value in fields.items():
            if is_fk_field(model, field_name):
                assert isinstance(field_value, tuple) and len(field_value) == 1
                fields[field_name] = field_value[0]

            if is_m2m_field(model, field_name):
                assert isinstance(field_value, list) and all(len(v) == 1 for v in field_value)
                fields[field_name] = [v[0] for v in field_value]

        yaml.dump(fields, self.stream, Dumper=DjangoSafeDumper,
                  default_flow_style=False, **self.options)

        if content is not None:
            self.stream.write('---\n')
            self.stream.write(content)

    def getvalue(self):
        return super(PythonSerializer, self).getvalue()


def get_segments_from_path(path):
    return path.replace(os.path.sep, '.').split('.')


def get_fields_from_path(path):
    path_segments = get_segments_from_path(os.path.relpath(path, settings.BASE_DIR))

    path_templs = defaultdict(list)

    for model in DjangoPagesModel.subclasses():
        path_templs[model.dump_path_template].append(model)

    for path_templ in path_templs:
        path_templ_segments = get_segments_from_path(path_templ)

        if len(path_segments) != len(path_templ_segments):
            continue

        fields = {}

        no_match = False

        for path_seg, path_templ_seg in zip(path_segments, path_templ_segments):
            if path_templ_seg[0] == '[' and path_templ_seg[-1] == ']':
                fields[path_templ_seg[1:-1]] = path_seg
            else:
                if path_templ_seg != path_seg:
                    no_match = True
                    break

        if no_match:
            continue

        if len(path_templs[path_templ]) == 1:
            model = path_templs[path_templ][0]

            if 'model_name' not in fields:
                fields['model_name'] = model._meta.model_name

            if 'app_label' not in fields:
                fields['app_label'] = model._meta.app_label

        return fields

    raise RuntimeError('Could not find model for loading data at {}'.format(path))


# Built-in deserializers take either a stream or string, but we require a file,
# because we extract some of the data about the object deserialized in the file
# from its path.
def Deserializer(file, **options):
    fields = get_fields_from_path(file.name)

    data = file.read().decode('utf-8')

    separator = '\n---\n'

    parts = data.split(separator, 1)

    try:
        fields.update(yaml.load(parts[0], Loader=SafeLoader))
    except yaml.YAMLError as e:
        raise DeserializationError(e)

    app_label = fields.pop('app_label')
    model_name = fields.pop('model_name')
    model = apps.get_model(app_label, model_name)

    for field_name, field_value in fields.items():
        if is_fk_field(model, field_name):
            assert isinstance(field_value, str)
            fields[field_name] = [field_value]

        if is_m2m_field(model, field_name):
            assert isinstance(field_value, list) and all(isinstance(v, str) for v in field_value)
            fields[field_name] = [[v] for v in field_value]

    if model.has_content:
        if len(parts) == 1:
            raise DeserializationError('Missing content')

        fields['content'] = parts[1]
    elif 'content_format' in fields:
        del fields['content_format']

    if 'key' not in fields:
        key_field_values = [fields[field_name].replace('/', '//') for field_name in model.key_field_names]
        fields['key'] = '/'.join(key_field_values)

    record = {
        'model': '{}.{}'.format(app_label, model_name),
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
