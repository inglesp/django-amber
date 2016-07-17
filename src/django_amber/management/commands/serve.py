import glob
import os
from time import sleep

from django.apps import apps
from django.core.management.base import BaseCommand

from django_amber.models import load_from_file
from django_amber.utils import run_runserver_in_thread


def load_changed(changed_paths):
    load_from_file(changed_paths)

    # TODO  Decide what to do if loading data raises DeserializationError.


def remove_missing(missing_paths):
    for path in missing_paths:
        dir_path, filename = os.path.split(path)
        path_segments = dir_path.split(os.path.sep)

        app_label = path_segments[-3]
        model_name = path_segments[-1]
        model = apps.get_model(app_label, model_name)

        key, _ = os.path.splitext(filename)

        instance = model.objects.get_by_natural_key(key)
        instance.delete()

    # TODO  Decide what to do if deleting the object causes cascading
    # deletes.  Options:
    #  * do nothing, leaving data on filesystem in inconsistent state;
    #  * roll back and raise exception;
    #  * remove related files from filesystem.


def get_mtimes():
    mtimes = {}

    for app_config in apps.get_app_configs():
        path = os.path.join(app_config.path, 'data', '**', '*')
        for filename in glob.glob(path):
            stat = os.stat(filename)
            mtimes[filename] = stat.st_mtime

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
        parser.add_argument('port', nargs='?',  help='Optional port number')

    def handle(self, *args, **kwargs):
        port = kwargs.get('port')
        run_runserver_in_thread(port)

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

        print()
