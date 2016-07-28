import glob
import os

from django.core.management.base import BaseCommand

from ...models import DjangoPagesModel
from ...serialization_helpers import dump_to_file


class Command(BaseCommand):
    def handle(self, *args, **kwargs):
        for model in DjangoPagesModel.subclasses():
            for path in glob.glob(model.dump_path_glob_path()):
                os.remove(path)

        for model in DjangoPagesModel.subclasses():
            for obj in model.objects.all():
                dump_to_file(obj)
