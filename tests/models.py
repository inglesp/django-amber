from django.db import models
from django_pages.models import PagesModel


class Thing(PagesModel):
    colour = models.CharField(max_length=255)
    related_thing_a = models.ForeignKey('RelatedThingA', null=True)
    related_thing_b = models.ForeignKey('RelatedThingB', null=True)


class RelatedThingA(models.Model):
    name = models.CharField(max_length=255)


class RelatedThingB(models.Model):
    name = models.CharField(max_length=255)

    class Manager(models.Manager):
        def get_by_natural_key(self, name):
            return self.get(name=name)

    objects = Manager()
