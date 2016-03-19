import os

from django.apps import apps
from django.core.management import find_commands
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    def handle(self, *args, **kwargs):
        for app_config in reversed(list(apps.get_app_configs())):
            if app_config.name == 'django_pages':
                continue

            path = os.path.join(app_config.path, 'management')
            print(find_commands(path))
            
            # commands.update({name: app_config.name for name in find_commands(path)})

        # commands = {name: 'django.core' for name in find_commands(upath(__path__[0]))}
