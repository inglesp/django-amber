import os
import shutil

from django.apps import apps
from django.core.management.base import BaseCommand

from ...models import DjangoPagesModel, MetadataModel, PageModel


class Command(BaseCommand):
    def handle(self, *args, **kwargs):
        for app_config in apps.get_app_configs():
            # TODO This will cause problems for any app that doesn't have
            # anything to do with django-pages, but which has a metadata or
            # pages directory.
            shutil.rmtree(
                os.path.join(app_config.path, MetadataModel.model_type),
                ignore_errors=True
            )
            shutil.rmtree(
                os.path.join(app_config.path, PageModel.model_type),
                ignore_errors=True
            )

            for model in app_config.get_models():
                if issubclass(model, DjangoPagesModel):
                    for obj in model.objects.all():
                        obj.dump_to_file()
