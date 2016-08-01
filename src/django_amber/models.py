import os

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

    def dump_path(self):
        return os.path.join(self.get_dump_dir_path(), *self.key.split('/')) + '.' + self.content_format

    def natural_key(self):
        return (self.key,)

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
