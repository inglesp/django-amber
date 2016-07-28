import glob
import os
from time import sleep

from django.apps import apps
from django.core.management import call_command
from django.core.management.base import BaseCommand
from django.core.management.commands.runserver import Command as RunserverCommand

from django_amber.serialization_helpers import load_from_file
from django_amber.utils import run_runserver_in_process

from ...models import DjangoPagesModel
from ...serializer import get_fields_from_path


def load_changed(changed_paths):
    load_from_file(changed_paths)

    # TODO  Decide what to do if loading data raises DeserializationError.


def remove_missing(missing_paths):
    for path in missing_paths:
        fields = get_fields_from_path(path)

        app_label = fields['app_label']
        model_name = fields['model_name']
        model = apps.get_model(app_label, model_name)

        key_field_values = [fields[field_name].replace('/', '//') for field_name in model.key_field_names]
        key = '/'.join(key_field_values)

        instance = model.objects.get_by_natural_key(key)
        instance.delete()

    # TODO  This requires that the key be computable from the fields that are
    # stored in the model's path.  This assumption is not enforced anywhere.

    # TODO  Decide what to do if deleting the object causes cascading
    # deletes.  Options:
    #  * do nothing, leaving data on filesystem in inconsistent state;
    #  * roll back and raise exception;
    #  * remove related files from filesystem.


def get_mtimes():
    mtimes = {}

    for model in DjangoPagesModel.subclasses():
        path = model.dump_path_glob_path()
        for filename in glob.glob(path):
            try:
                stat = os.stat(filename)
                mtimes[filename] = stat.st_mtime
            except FileNotFoundError:
                # Race condition: the file has disappeared in the time between
                # the glob and the stat.
                pass

    return mtimes


def compare_mtimes(old_mtimes, new_mtimes):
    changed_paths = []
    missing_paths = []

    for filename, old_mtime in old_mtimes.items():
        new_mtime = new_mtimes.get(filename)
        if new_mtime is None:
            missing_paths.append(filename)
        elif new_mtime != old_mtime:
            changed_paths.append(filename)

    for filename in new_mtimes:
        if filename not in old_mtimes:
            changed_paths.append(filename)

    return changed_paths, missing_paths


class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument(
            'port',
            nargs='?',
            default=RunserverCommand.default_port,
            help='Optional port number'
        )

    def handle(self, *args, **kwargs):
        port = kwargs.get('port')

        call_command('loadpages')

        p = run_runserver_in_process(port)

        try:
            self.serve()
        finally:
            p.terminate()

        print()

    def serve(self):
        mtimes = get_mtimes()

        while True:
            try:
                sleep(0.1)
            except KeyboardInterrupt:
                break

            new_mtimes = get_mtimes()
            changed_paths, missing_paths = compare_mtimes(mtimes, new_mtimes)
            load_changed(changed_paths)
            remove_missing(missing_paths)
            mtimes = new_mtimes
