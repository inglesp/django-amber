import os
import shutil

from django.apps import apps
from django.core.management.base import BaseCommand

from ...models import DjangoPagesModel


class Command(BaseCommand):
    def handle(self, *args, **kwargs):
        for app_config in apps.get_app_configs():
            for model in app_config.get_models():
                if issubclass(model, DjangoPagesModel):
                    shutil.rmtree(model.dump_dir_path(), ignore_errors=True)
                    for obj in model.objects.all():
                        obj.dump_to_file()
