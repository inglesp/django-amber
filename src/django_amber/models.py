import os
import re

from django.apps import apps
from django.conf import settings
from django.db import models


class PagesManager(models.Manager):
    def get_by_natural_key(self, key):
        return self.get(key=key)


class DjangoPagesModel(models.Model):
    objects = PagesManager()

    class Meta:
        abstract = True

    dump_dir_path = None
    key_structure = None

    @classmethod
    def get_dump_dir_path(cls):
        if cls.dump_dir_path is None:
            app_config = apps.get_app_config(cls._meta.app_label)
            return os.path.join(app_config.path, 'data', cls._meta.model_name)
        else:
            return os.path.join(settings.BASE_DIR, *cls.dump_dir_path.split('/'))

    @classmethod
    def subclasses(cls):
        for app_config in apps.get_app_configs():
            for model in app_config.get_models():
                if issubclass(model, DjangoPagesModel):
                    yield model

    @classmethod
    def fields_from_key(cls, key):
        if cls.key_structure is None:
            return {}

        pattern = cls.key_structure
        for field_name in cls.field_names_from_key_structure():
            pattern = pattern.replace('[{}]'.format(field_name), '(?P<{}>.+)'.format(field_name))

        match = re.match(pattern, key)
        return match.groupdict()

    @classmethod
    def field_names_from_key_structure(cls):
        return re.findall('\[(\w*)\]', cls.key_structure)

    def dump_path(self):
        if not self.key:
            self.set_key()

        return os.path.join(self.get_dump_dir_path(), *self.key.split('/')) + '.' + self.content_format

    def natural_key(self):
        return (self.key,)

    def set_key(self):
        assert self.key_structure is not None

        key = self.key_structure
        for field_name in self.field_names_from_key_structure():
            value = getattr(self, field_name)
            if isinstance(value, DjangoPagesModel):
                value = value.key
            else:
                value = str(value)
            key = key.replace('[{}]'.format(field_name), value)

        self.key = key

    def __str__(self):
        return self.key


class ModelWithoutContent(DjangoPagesModel):
    key = models.CharField(max_length=255)

    content_format = 'yml'

    has_content = False

    class Meta:
        abstract = True


class ModelWithContent(DjangoPagesModel):
    key = models.CharField(max_length=255)
    content = models.TextField()
    content_format = models.CharField(max_length=255)

    has_content = True

    class Meta:
        abstract = True


def parse_dump_path(path):
    for model in DjangoPagesModel.subclasses():
        if os.path.commonpath([path, model.get_dump_dir_path()]) == model.get_dump_dir_path():
            remainder = os.path.relpath(path, model.get_dump_dir_path())
            key, content_format_with_dot = os.path.splitext(remainder)
            content_format = content_format_with_dot[1:]
            return model, key, content_format

    assert False
