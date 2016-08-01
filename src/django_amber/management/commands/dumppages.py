import shutil

from django.core.management.base import BaseCommand

from ...models import DjangoPagesModel
from ...serialization_helpers import dump_to_file


class Command(BaseCommand):
    def handle(self, *args, **kwargs):
        for model in DjangoPagesModel.subclasses():
            shutil.rmtree(model.get_dump_dir_path(), ignore_errors=True)
            for obj in model.objects.all():
                dump_to_file(obj)
