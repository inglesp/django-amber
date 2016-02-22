import os
import shutil

from django.core import management, serializers
from django.test import TestCase, override_settings

from .models import Article, Author


def get_path(model_name, filename):
    if model_name == 'article':
        model_type = 'pages'
    else:
        assert False

    return os.path.join('tests', model_type, model_name, filename)


def create_author(**kwargs):
    attrs = {
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


class TestModel(TestCase):
    def test_natural_key(self):
        obj = create_article(key='django')
        self.assertEqual(obj.natural_key(), ('django',))

    def test_get_by_natural_key(self):
        obj1 = create_article(key='django')
        obj2 = create_article(key='python')
        self.assertEqual(Article.objects.get_by_natural_key('django'), obj1)


class TestDeserialization(TestCase):
    def deserialize(self, model_name, filename):
        path = get_path(model_name, filename)
        with open(path, 'rb') as f:
            return next(serializers.deserialize('md', f))

    def test_deserialization(self):
        deserialized_obj = self.deserialize('article', 'valid.md')
        obj = deserialized_obj.object

        self.assertEqual(obj.key, 'valid')
        self.assertEqual(obj.content_format, '.md')
        self.assertEqual(obj.content, 'This is an article about *Django*.\n')
        self.assertEqual(obj.title, 'All about Django')

    def test_deserialization_with_foreign_key(self):
        related_obj = create_author()

        deserialized_obj = self.deserialize('article', 'with_foreign_key.md')
        obj = deserialized_obj.object

        self.assertEqual(obj.author, related_obj)

    def test_deserialization_with_invalid_yaml(self):
        with self.assertRaises(serializers.base.DeserializationError):
            self.deserialize('article', 'invalid_yaml.md')

    def test_deserialization_with_invalid_object(self):
        with self.assertRaises(serializers.base.DeserializationError):
            self.deserialize('article', 'invalid_object.md')

    def test_deserialization_with_missing_content(self):
        with self.assertRaises(serializers.base.DeserializationError):
            self.deserialize('article', 'missing_content.md')


class TestSerialization(TestCase):
    def _test_roundtrip(self, model_name, filename):
        path = get_path(model_name, filename)
        with open(path, 'rb') as f:
            obj = next(serializers.deserialize('md', f)).object

        obj.save()

        with open(path) as f:
            expected = f.read()

        actual = serializers.serialize('md', [obj], use_natural_foreign_keys=True)
        self.assertEqual(actual, expected)

    def test_serialization(self):
        self._test_roundtrip('article', 'valid.md')

    def test_serialization_with_foreign_key(self):
        related_obj = create_author()
        self._test_roundtrip('article', 'with_foreign_key.md')


class TestLoadData(TestCase):
    def test_loaddata(self):
        path = get_path('article', 'valid.md')
        management.call_command('loaddata', path, verbosity=0)

        obj = Article.objects.get(key='valid')
        self.assertEqual(obj.key, 'valid')
        self.assertEqual(obj.content_format, '.md')
        self.assertEqual(obj.content, 'This is an article about *Django*.\n')
        self.assertEqual(obj.title, 'All about Django')


class TestDumpToFile(TestCase):
    def _test_dump_to_file(self, filename, **kwargs):
        obj = create_article(**kwargs)
        obj.dump_to_file()

        path = get_path('article', filename).replace('pages', 'pages.bak')
        with open(path) as f:
            expected = f.read()

        with open(get_path('article', 'django.md')) as f:
            actual = f.read()

        self.assertEqual(actual, expected)

    def test_dump_to_file(self):
        self._test_dump_to_file('valid.md')

    def test_dump_to_file_with_foreign_key(self):
        related_obj = create_author()
        self._test_dump_to_file('with_foreign_key.md', author=related_obj)

    def setUp(self):
        shutil.move(
            os.path.join('tests', 'pages'),
            os.path.join('tests', 'pages.bak')
        )

    def tearDown(self):
        try:
            shutil.rmtree(os.path.join('tests', 'pages'))
        except FileNotFoundError:
            pass

        shutil.move(
            os.path.join('tests', 'pages.bak'),
            os.path.join('tests', 'pages')
        )
