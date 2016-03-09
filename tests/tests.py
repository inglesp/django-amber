import os
import shutil

from django.core import management, serializers
from django.test import TestCase, override_settings

from .models import Article, Author, Tag


def get_path(model_name, filename):
    if model_name == 'article':
        model_type = 'pages'
    elif model_name == 'author':
        model_type = 'metadata'
    else:
        assert False

    return os.path.join('tests', model_type, model_name, filename)


def get_test_file_path(model_name, filename):
    if model_name == 'article':
        model_type = 'pages'
    elif model_name == 'author':
        model_type = 'metadata'
    else:
        assert False

    return os.path.join('tests', 'test-files', model_type, model_name, filename)


def copy_test_files_into_place():
    for model_type in ['metadata', 'pages']:
        shutil.copytree(
            os.path.join('tests', 'test-files', model_type),
            os.path.join('tests', model_type)
        )


def clear_test_files():
    for model_type in ['metadata', 'pages']:
        shutil.rmtree(os.path.join('tests', model_type), ignore_errors=True)


def create_author(**kwargs):
    attrs = {
        'key': 'peter',
        'name': 'Peter',
    }

    attrs.update(kwargs)
    return Author.objects.create(**attrs)


def create_article(**kwargs):
    attrs = {
        'key': 'django',
        'content': 'This is an article about *Django*.\n',
        'content_format': '.md',
        'title': 'All about Django',
    }

    attrs.update(kwargs)
    return Article.objects.create(**attrs)


def create_tags():
    keys = ['python', 'django']
    return [Tag.objects.create(key=key, name=key.title()) for key in keys]


class TestModel(TestCase):
    def test_metadata_natural_key(self):
        obj = create_author(key='peter')
        self.assertEqual(obj.natural_key(), ('peter',))

    def test_metadata_get_by_natural_key(self):
        obj1 = create_author(key='peter')
        obj2 = create_author(key='clare')
        self.assertEqual(Author.objects.get_by_natural_key('clare'), obj2)

    def test_page_natural_key(self):
        obj = create_article(key='django')
        self.assertEqual(obj.natural_key(), ('django',))

    def test_page_get_by_natural_key(self):
        obj1 = create_article(key='django')
        obj2 = create_article(key='python')
        self.assertEqual(Article.objects.get_by_natural_key('django'), obj1)


class TestDeserialization(TestCase):
    def setUp(self):
        copy_test_files_into_place()

    def tearDown(selt):
        clear_test_files()

    def deserialize(self, model_name, filename):
        path = get_path(model_name, filename)
        with open(path, 'rb') as f:
            return next(serializers.deserialize('md', f))

    def test_metadata_deserialization(self):
        deserialized_obj = self.deserialize('author', 'valid.yml')
        obj = deserialized_obj.object

        self.assertEqual(obj.key, 'valid')
        self.assertEqual(obj.name, 'Peter')

    def test_page_deserialization(self):
        deserialized_obj = self.deserialize('article', 'valid.md')
        obj = deserialized_obj.object

        self.assertEqual(obj.key, 'valid')
        self.assertEqual(obj.content_format, '.md')
        self.assertEqual(obj.content, 'This is an article about *Django*.\n')
        self.assertEqual(obj.title, 'All about Django')

    def test_metadata_deserialization_with_foreign_key(self):
        related_obj = create_author(key='clare')

        deserialized_obj = self.deserialize('author', 'with_foreign_key.yml')
        obj = deserialized_obj.object

        self.assertEqual(obj.editor, related_obj)

    def test_page_deserialization_with_foreign_key(self):
        related_obj = create_author()

        deserialized_obj = self.deserialize('article', 'with_foreign_key.md')
        obj = deserialized_obj.object

        self.assertEqual(obj.author, related_obj)

    def test_metadata_deserialization_with_many_to_many_field(self):
        tags = create_tags()

        deserialized_obj = self.deserialize('author', 'with_many_to_many_field.yml')
        deserialized_obj.save()  # Saving is required to create m2m links
        obj = deserialized_obj.object

        self.assertEqual(list(obj.tags.all()), tags)

    def test_page_deserialization_with_many_to_many_field(self):
        tags = create_tags()

        deserialized_obj = self.deserialize('article', 'with_many_to_many_field.md')
        deserialized_obj.save()  # Saving is required to create m2m links
        obj = deserialized_obj.object

        self.assertEqual(list(obj.tags.all()), tags)

    def test_metadata_deserialization_with_invalid_yaml(self):
        with self.assertRaises(serializers.base.DeserializationError):
            self.deserialize('author', 'invalid_yaml.yml')

    def test_page_deserialization_with_invalid_yaml(self):
        with self.assertRaises(serializers.base.DeserializationError):
            self.deserialize('article', 'invalid_yaml.md')

    def test_metadata_deserialization_with_invalid_object(self):
        with self.assertRaises(serializers.base.DeserializationError):
            self.deserialize('author', 'invalid_object.yml')

    def test_page_deserialization_with_invalid_object(self):
        with self.assertRaises(serializers.base.DeserializationError):
            self.deserialize('article', 'invalid_object.md')

    def test_page_deserialization_with_missing_content(self):
        with self.assertRaises(serializers.base.DeserializationError):
            self.deserialize('article', 'missing_content.md')


class TestSerialization(TestCase):
    def setUp(self):
        copy_test_files_into_place()

    def tearDown(selt):
        clear_test_files()

    def _test_roundtrip(self, model_name, filename):
        path = get_path(model_name, filename)
        with open(path, 'rb') as f:
            deserialized_obj = next(serializers.deserialize('md', f))

        deserialized_obj.save()
        obj = deserialized_obj.object

        with open(path) as f:
            expected = f.read()

        actual = serializers.serialize('md', [obj], use_natural_foreign_keys=True)
        self.assertEqual(actual, expected)

    def test_metadata_serialization(self):
        self._test_roundtrip('author', 'valid.yml')

    def test_page_serialization(self):
        self._test_roundtrip('article', 'valid.md')

    def test_metadata_serialization_with_foreign_key(self):
        related_obj = create_author(key='clare')
        self._test_roundtrip('author', 'with_foreign_key.yml')

    def test_page_serialization_with_foreign_key(self):
        related_obj = create_author()
        self._test_roundtrip('article', 'with_foreign_key.md')

    def test_metadata_serialization_with_many_to_many_field(self):
        create_tags()
        self._test_roundtrip('author', 'with_many_to_many_field.yml')

    def test_page_serialization_with_many_to_many_field(self):
        create_tags()
        self._test_roundtrip('article', 'with_many_to_many_field.md')


class TestLoadData(TestCase):
    def setUp(self):
        copy_test_files_into_place()

    def tearDown(selt):
        clear_test_files()

    def test_metadata_loaddata(self):
        path = get_path('author', 'valid.yml')
        management.call_command('loaddata', path, verbosity=0)

        obj = Author.objects.get(key='valid')
        self.assertEqual(obj.key, 'valid')
        self.assertEqual(obj.name, 'Peter')

    def test_page_loaddata(self):
        path = get_path('article', 'valid.md')
        management.call_command('loaddata', path, verbosity=0)

        obj = Article.objects.get(key='valid')
        self.assertEqual(obj.key, 'valid')
        self.assertEqual(obj.content_format, '.md')
        self.assertEqual(obj.content, 'This is an article about *Django*.\n')
        self.assertEqual(obj.title, 'All about Django')


class TestDumpToFile(TestCase):
    def setUp(self):
        clear_test_files()

    def tearDown(self):
        clear_test_files()

    def _test_dump_to_file(self, model_name, filename):
        if model_name == 'article':
            actual_path = get_path(model_name, 'django.md')
            expected_path = get_test_file_path(model_name, filename)
        elif model_name == 'author':
            actual_path = get_path(model_name, 'peter.yml')
            expected_path = get_test_file_path(model_name, filename)
        else:
            assert False

        with open(actual_path) as f:
            actual = f.read()

        with open(expected_path) as f:
            expected = f.read()

        self.assertEqual(actual, expected)

    def test_metadata_dump_to_file(self):
        obj = create_author()
        obj.dump_to_file()

        self._test_dump_to_file('author', 'valid.yml')

    def test_page_dump_to_file(self):
        obj = create_article()
        obj.dump_to_file()

        self._test_dump_to_file('article', 'valid.md')

    def test_metadata_dump_to_file_with_foreign_key(self):
        obj = create_author(editor=create_author(key='clare'))
        obj.dump_to_file()

        self._test_dump_to_file('author', 'with_foreign_key.yml')

    def test_page_dump_to_file_with_foreign_key(self):
        obj = create_article(author=create_author())
        obj.dump_to_file()

        self._test_dump_to_file('article', 'with_foreign_key.md')

    def test_metadata_dump_to_file_with_many_to_many_field(self):
        obj = create_author()
        obj.tags = create_tags()
        obj.dump_to_file()

        self._test_dump_to_file('author', 'with_many_to_many_field.yml')

    def test_page_dump_to_file_with_many_to_many_field(self):
        obj = create_article()
        obj.tags = create_tags()
        obj.dump_to_file()

        self._test_dump_to_file('article', 'with_many_to_many_field.md')
