import os.path

import yaml

from django.core.serializers.base import DeserializationError
from django.core.serializers.python import (
    Deserializer as PythonDeserializer, Serializer as PythonSerializer,
)


# This is required for Django to recognise this module as being valid for
# deserialization.
class Serializer(PythonSerializer):
    internal_use_only = False


# Built-in deserializers take either a stream or string, but we require a file,
# because we extract some of the data about the object deserialized in the file
# from its path.
def Deserializer(file, **options):
    path, filename = os.path.split(file.name)
    path_segments = path.split(os.path.sep)

    app_label = path_segments[-3]
    model_name = path_segments[-1]

    data = file.read().decode('utf-8')

    separator = '\n---\n'

    if separator not in data:
        raise DeserializationError('Missing content')

    parts = data.split(separator, 1)

    try:
        fields = yaml.load(parts[0], Loader=yaml.CSafeLoader)
    except yaml.YAMLError as e:
        raise DeserializationError(e)

    fields['key'], fields['content_format'] = os.path.splitext(filename)
    fields['content'] = parts[1]
    
    record = {
        'model': '{}.{}'.format(app_label, model_name),
        'fields': fields,
    }

    try:
        yield from PythonDeserializer([record], **options)
    except Exception as e:
        raise DeserializationError(e)
