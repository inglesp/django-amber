from django.db import models
from django_pages.models import PagesModel


class Thing(PagesModel):
    colour = models.CharField(max_length=255)
