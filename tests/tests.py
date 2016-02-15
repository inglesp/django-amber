from django.test import TestCase

from .models import Thing


class PagesTest(TestCase):
    def test_model(self):
        t1 = Thing(
            key='thing 1',
            content='This is a *Thing*',
            content_format='markdown',
            colour='blue',
        )
        t1.save()

        t2 = Thing.objects.get(colour=t1.colour)
        self.assertEqual(t1.content, t2.content)
