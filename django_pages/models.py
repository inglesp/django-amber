import os

from django.apps import apps
from django.db import models

from .serializer import Serializer


class PagesManager(models.Manager):
    def get_by_natural_key(self, key):
        return self.get(key=key)


class PagesModel(models.Model):
    key = models.CharField(max_length=255)
    content = models.TextField()
    content_format = models.CharField(max_length=255)

    objects = PagesManager()

    dump_on_save = False

    class Meta:
        abstract = True

    def natural_key(self):
        return (self.key,)

    def save(self, *args, **kwargs):
        super(PagesModel, self).save(*args, **kwargs)
        if self.dump_on_save:
            self.dump_to_file()

    def dump_to_file(self):
        filename = '{}{}'.format(self.key, self.content_format)
        app = apps.app_configs[self._meta.app_label]
        dir_path = os.path.join(app.path, 'pages', self._meta.model_name)
        os.makedirs(dir_path, exist_ok=True)
        path = os.path.join(dir_path, filename)

        serializer = Serializer()
        serializer.serialize([self], use_natural_foreign_keys=True)
        data = serializer.getvalue()

        with open(path, 'w') as f:
            f.write(data)
