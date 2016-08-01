import os
from time import sleep

from django.core.management import call_command
from django.core.management.base import BaseCommand
from django.core.management.commands.runserver import Command as RunserverCommand

from ...serialization_helpers import find_file_paths_in_dir, load_from_file
from ...models import DjangoPagesModel, parse_dump_path
from ...utils import run_runserver_in_process


def load_changed(changed_paths):
    load_from_file(changed_paths)

    # TODO  Decide what to do if loading data raises DeserializationError.


def remove_missing(missing_paths):
    for path in missing_paths:
        model, key, _ = parse_dump_path(path)

        instance = model.objects.get_by_natural_key(key)
        instance.delete()

    # TODO  Decide what to do if deleting the object causes cascading
    # deletes.  Options:
    #  * do nothing, leaving data on filesystem in inconsistent state;
    #  * roll back and raise exception;
    #  * remove related files from filesystem.


def get_mtimes():
    mtimes = {}

    for model in DjangoPagesModel.subclasses():
        for path in find_file_paths_in_dir(model.get_dump_dir_path()):
            try:
                stat = os.stat(path)
                mtimes[path] = stat.st_mtime
            except FileNotFoundError:
                # Race condition: the file has disappeared in the time between
                # the glob and the stat.
                pass

    return mtimes


def compare_mtimes(old_mtimes, new_mtimes):
    changed_paths = []
    missing_paths = []

    for path, old_mtime in old_mtimes.items():
        new_mtime = new_mtimes.get(path)
        if new_mtime is None:
            missing_paths.append(path)
        elif new_mtime != old_mtime:
            changed_paths.append(path)

    for path in new_mtimes:
        if path not in old_mtimes:
            changed_paths.append(path)

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
