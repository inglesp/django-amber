import os

from django.db import transaction

from .serializer import Deserializer, Serializer


class LoadFromFileError(Exception):
    def __init__(self, original_exception, path):
        self.original_exception = original_exception
        self.path = path


def dump_to_file(instance):
    dump_path = instance.dump_path()
    os.makedirs(os.path.dirname(dump_path), exist_ok=True)

    serializer = Serializer()
    serializer.serialize([instance], use_natural_foreign_keys=True)
    data = serializer.getvalue()

    with open(dump_path, 'w') as f:
        f.write(data)


def load_from_file(paths):
    objs_with_deferred_fields = []

    with transaction.atomic():
        for path in paths:
            try:
                with open(path, 'rb') as f:
                    for obj in Deserializer(f, handle_forward_references=True):
                        obj.save()

                        if obj.deferred_fields:
                            objs_with_deferred_fields.append(obj)
            except Exception as e:
                raise LoadFromFileError(e, path)

        for obj in objs_with_deferred_fields:
            obj.save_deferred_fields()


def find_file_paths_in_dir(path):
    for root, _, file_paths in os.walk(path):
        for file_path in file_paths:
            if file_path[0] != '.':
                yield os.path.join(root, file_path)
