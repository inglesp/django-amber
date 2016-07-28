from django.db import models
from django_amber.models import ModelWithContent, ModelWithoutContent


class Article(ModelWithContent):
    title = models.CharField(max_length=255)
    author = models.ForeignKey('Author', null=True)
    tags = models.ManyToManyField('Tag', related_name='articles')


class Author(ModelWithoutContent):
    name = models.CharField(max_length=255)
    editor = models.ForeignKey('Author', null=True)
    tags = models.ManyToManyField('Tag', related_name='authors')


class Tag(ModelWithoutContent):
    name = models.CharField(max_length=255)

    dump_path_template =  'tests/tag-data/[key].yml'
