import glob
import os

from django.core.management import call_command
from django.core.management.base import BaseCommand

from ...models import DjangoPagesModel
from ...serialization_helpers import load_from_file

class Command(BaseCommand):
    def handle(self, *args, **kwargs):
        call_command('migrate')

        paths = []

        for model in DjangoPagesModel.subclasses():
            paths.extend(glob.glob(model.dump_path_glob_path()))

        load_from_file(paths)
