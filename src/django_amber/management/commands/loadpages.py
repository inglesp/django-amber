from django.core.management import call_command
from django.core.management.base import BaseCommand

from ...models import DjangoPagesModel
from ...serialization_helpers import find_file_paths_in_dir, load_from_file


class Command(BaseCommand):
    def handle(self, *args, **kwargs):
        call_command('migrate')

        paths = []

        for model in DjangoPagesModel.subclasses():
            paths.extend(find_file_paths_in_dir(model.get_dump_dir_path()))

        load_from_file(paths)
