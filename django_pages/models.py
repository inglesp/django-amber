from django.db import models


class PagesModel(models.Model):
    key = models.CharField(max_length=255)
    content = models.TextField()
    content_format = models.CharField(max_length=255)

    class Meta:
        abstract = True
