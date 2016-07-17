import glob
import os

from django.apps import apps
from django.core.management import call_command
from django.core.management.base import BaseCommand

from ...models import DjangoPagesModel, load_from_file


class Command(BaseCommand):
    def handle(self, *args, **kwargs):
        paths = []

        for app_config in apps.get_app_configs():
            for model in app_config.get_models():
                if issubclass(model, DjangoPagesModel):
                    paths.extend(glob.glob(os.path.join(model.dump_dir_path(), '*')))

        load_from_file(paths)
