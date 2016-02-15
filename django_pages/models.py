from django.db import models


class PagesManager(models.Manager):
    def get_by_natural_key(self, key):
        return self.get(key=key)


class PagesModel(models.Model):
    key = models.CharField(max_length=255)
    content = models.TextField()
    content_format = models.CharField(max_length=255)

    objects = PagesManager()

    class Meta:
        abstract = True

    def natural_key(self):
        return (self.key,)
