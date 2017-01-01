from django.db import models
from django_amber.models import ModelWithContent, ModelWithoutContent


class Article(ModelWithContent):
    title = models.CharField(max_length=255)
    slug = models.CharField(max_length=255)
    language = models.CharField(max_length=255)
    author = models.ForeignKey('Author', null=True)
    tags = models.ManyToManyField('Tag', related_name='articles')

    dump_dir_path = 'tests/data/articles'
    key_structure = '[language]/[slug]'


class Author(ModelWithoutContent):
    name = models.CharField(max_length=255)
    editor = models.ForeignKey('Author', null=True)
    tags = models.ManyToManyField('Tag', related_name='authors')


class Tag(ModelWithoutContent):
    name = models.CharField(max_length=255)


class Comment(ModelWithContent):
    article = models.ForeignKey('Article')
    date = models.DateField()

    key_structure = '[article]/[date]'


class DateTimeModel(ModelWithoutContent):
    date = models.DateField(null=True)
    time = models.TimeField(null=True)
    datetime = models.DateTimeField(null=True)
