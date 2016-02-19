import os
import shutil

from django.core import management, serializers
from django.test import TestCase, override_settings

from .models import Article, Author, Category


BASE_PATH = os.path.join('tests', 'test-pages', 'article')


class TestModel(TestCase):
    def test_natural_key(self):
        obj = Article.objects.create(
            key='django',
            content='This is an article about *Django*.',
            content_format='.md',
            title='All about Django',
        )
        self.assertEqual(obj.natural_key(), ('django',))

    def test_get_by_natural_key(self):
        obj1 = Article.objects.create(
            key='django',
            content='This is an article about *Django*.',
            content_format='.md',
            title='All about Django',
        )

        obj2 = Article.objects.create(
            key='python',
            content='This is an article about *Python*.',
            content_format='.md',
            title='All about Python',
        )

        self.assertEqual(Article.objects.get_by_natural_key('django'), obj1)


class TestDeserialization(TestCase):
    def deserialize(self, filename):
        path = os.path.join(BASE_PATH, filename)
        with open(path, 'rb') as f:
            return next(serializers.deserialize('md', f))

    def test_deserialization(self):
        deserialized_obj = self.deserialize('valid.md')
        obj = deserialized_obj.object

        self.assertEqual(obj.key, 'valid')
        self.assertEqual(obj.content_format, '.md')
        self.assertEqual(obj.content, 'This is an article about *Django*.\n')
        self.assertEqual(obj.title, 'All about Django')

    def test_deserialization_with_foreign_key(self):
        related_obj = Category.objects.create(pk=1, name='programming')

        deserialized_obj = self.deserialize('with_foreign_key.md')
        obj = deserialized_obj.object

        self.assertEqual(obj.category, related_obj)

    def test_deserialization_with_natural_foreign_key(self):
        related_obj = Author.objects.create(name='Peter')

        deserialized_obj = self.deserialize('with_natural_foreign_key.md')
        obj = deserialized_obj.object

        self.assertEqual(obj.author, related_obj)

    def test_deserialization_with_invalid_yaml(self):
        with self.assertRaises(serializers.base.DeserializationError):
            self.deserialize('invalid_yaml.md')

    def test_deserialization_with_missing_content(self):
        with self.assertRaises(serializers.base.DeserializationError):
            self.deserialize('missing_content.md')

    def test_deserialization_with_invalid_object(self):
        with self.assertRaises(serializers.base.DeserializationError):
            self.deserialize('invalid_object.md')


class TestSerialization(TestCase):
    def _test_roundtrip(self, filename, **kwargs):
        path = os.path.join(BASE_PATH, filename)
        with open(path, 'rb') as f:
            obj = next(serializers.deserialize('md', f)).object

        obj.save()

        with open(path) as f:
            expected = f.read()

        actual = serializers.serialize('md', [obj], **kwargs)
        self.assertEqual(actual, expected)

    def test_serialization(self):
        self._test_roundtrip('valid.md')

    def test_serialization_with_foreign_key(self):
        related_obj = Category.objects.create(pk=1, name='programming')
        self._test_roundtrip('with_foreign_key.md')

    def test_serialization_with_natural_foreign_key(self):
        related_obj = Author.objects.create(name='Peter')
        self._test_roundtrip('with_natural_foreign_key.md', use_natural_foreign_keys=True)


class TestLoadData(TestCase):
    def test_loaddata(self):
        path = os.path.join(BASE_PATH, 'valid.md')
        management.call_command('loaddata', path, verbosity=0)

        obj = Article.objects.get(key='valid')
        self.assertEqual(obj.key, 'valid')
        self.assertEqual(obj.content_format, '.md')
        self.assertEqual(obj.content, 'This is an article about *Django*.\n')
        self.assertEqual(obj.title, 'All about Django')


class TestDumpToFile(TestCase):
    def _test_dump_to_file(self, filename, **kwargs):
        obj = Article.objects.create(
            key='django',
            content='This is an article about *Django*.\n',
            content_format='.md',
            title='All about Django',
            **kwargs
        )

        obj.dump_to_file()

        with open(os.path.join(BASE_PATH, filename)) as f:
            expected = f.read()

        with open(os.path.join('tests', 'pages', 'article', 'django.md')) as f:
            actual = f.read()

        self.assertEqual(actual, expected)

    def test_dump_to_file(self):
        self._test_dump_to_file('valid.md')

    def test_dump_to_file_with_foreign_key(self):
        related_obj = Category.objects.create(pk=1, name='programming')
        self._test_dump_to_file('with_foreign_key.md', category=related_obj)

    def test_dump_to_file_with_natural_foreign_key(self):
        related_obj = Author.objects.create(name='Peter')
        self._test_dump_to_file('with_natural_foreign_key.md', author=related_obj)

    def setUp(self):
        try:
            shutil.rmtree(os.path.join('tests', 'pages', 'article'))
        except FileNotFoundError:
            pass

    def tearDown(self):
        try:
            shutil.rmtree(os.path.join('tests', 'pages', 'article'))
        except FileNotFoundError:
            pass
