from django.db import models
from django_pages.models import PageModel


class Article(PageModel):
    title = models.CharField(max_length=255)
    author = models.ForeignKey('Author', null=True)
    category = models.ForeignKey('Category', null=True)


class Author(models.Model):
    name = models.CharField(max_length=255)

    class Manager(models.Manager):
        def get_by_natural_key(self, name):
            return self.get(name=name)

    objects = Manager()

    def natural_key(self):
        return (self.name,)


class Category(models.Model):
    name = models.CharField(max_length=255)
