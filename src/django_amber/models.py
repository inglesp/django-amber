import os

from django.apps import apps
from django.db import models, transaction

from .serializer import Deserializer, Serializer


class PagesManager(models.Manager):
    def get_by_natural_key(self, key):
        return self.get(key=key)


class DjangoPagesModel(models.Model):
    objects = PagesManager()

    class Meta:
        abstract = True

    @classmethod
    def dump_dir_path(cls):
        app_config = apps.get_app_config(cls._meta.app_label)
        return os.path.join(app_config.path, 'data', cls._meta.model_name)

    def dump_to_file(self):
        filename = '{}{}'.format(self.key, self.content_format)
        dir_path = self.dump_dir_path()
        os.makedirs(dir_path, exist_ok=True)
        path = os.path.join(dir_path, filename)

        serializer = Serializer()
        serializer.serialize([self], use_natural_foreign_keys=True)
        data = serializer.getvalue()

        with open(path, 'w') as f:
            f.write(data)

    def natural_key(self):
        return (self.key,)

    def __str__(self):
        return self.key


class ModelWithoutContent(DjangoPagesModel):
    key = models.CharField(max_length=255)

    content_format = '.yml'

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


def load_from_file(paths):
    objs_with_deferred_fields = []

    with transaction.atomic():
        for path in paths:
            with open(path, 'rb') as f:
                for obj in Deserializer(f, handle_forward_references=True):
                    obj.save()

                    if obj.deferred_fields:
                        objs_with_deferred_fields.append(obj)

        for obj in objs_with_deferred_fields:
            obj.save_deferred_fields()
