import os
import re

from django.conf import settings
from django.db import models, transaction

from .serializer import Deserializer, Serializer


class PagesManager(models.Manager):
    def get_by_natural_key(self, key):
        return self.get(key=key)


class DjangoPagesModel(models.Model):
    objects = PagesManager()

    class Meta:
        abstract = True

    dump_path_template =  '[app_label]/data/[model_name]/[key].[content_format]'

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

    def dump_to_file(self):
        dump_path = self.dump_path()
        os.makedirs(os.path.dirname(dump_path), exist_ok=True)

        serializer = Serializer()
        serializer.serialize([self], use_natural_foreign_keys=True)
        data = serializer.getvalue()

        print('dump_path:', dump_path)

        with open(dump_path, 'w') as f:
            f.write(data)

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
