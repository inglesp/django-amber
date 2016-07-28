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

    dump_path_template =  '[app_label]/data/[model_name]/[key].[content_format]'

    key_field_names = ['key']

    @classmethod
    def subclasses(cls):
        for app_config in apps.get_app_configs():
            for model in app_config.get_models():
                if issubclass(model, DjangoPagesModel):
                    yield model

    @classmethod
    def dump_path_glob_path(cls):
        dump_path = cls.dump_path_template

        for bracketed_field_name in re.findall('\[[\w_]+\]', cls.dump_path_template):
            field_name = bracketed_field_name[1:-1]
            if field_name == 'app_label':
                value = cls._meta.app_label
            elif field_name == 'model_name':
                value = cls._meta.model_name
            else:
                value = '*'

            dump_path = dump_path.replace(bracketed_field_name, value)

        dump_path = dump_path.replace('/', os.path.sep)

        return os.path.join(settings.BASE_DIR, dump_path)

    def dump_path(self):
        dump_path = self.dump_path_template

        for bracketed_field_name in re.findall('\[[\w_]+\]', self.dump_path_template):
            field_name = bracketed_field_name[1:-1]
            if field_name == 'app_label':
                value = self._meta.app_label
            elif field_name == 'model_name':
                value = self._meta.model_name
            else:
                value = getattr(self, field_name)

            dump_path = dump_path.replace(bracketed_field_name, value)

        dump_path = dump_path.replace('/', os.path.sep)

        return os.path.join(settings.BASE_DIR, dump_path)

    def natural_key(self):
        return (self.key,)

    def __str__(self):
        return self.key

    def save(self, *args, **kwargs):
        if not self.key:
            key_field_values = [getattr(self, field_name).replace('/', '//') for field_name in self.key_field_names]
            self.key = '/'.join(key_field_values)
        super().save(*args, **kwargs)


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
