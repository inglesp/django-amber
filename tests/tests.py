from filecmp import dircmp
import glob
import os
import shutil
from threading import Thread
from time import sleep

import requests

from django.core import management, serializers
from django.core.exceptions import ObjectDoesNotExist
from django.test import TestCase, TransactionTestCase, override_settings

from django_amber.management.commands import serve
from django_amber.models import load_from_file
from django_amber.serializer import Deserializer, Serializer
from django_amber.utils import get_free_port, wait_for_server

from .models import Article, Author, Tag


def get_path(model_name, filename):
    return os.path.join('tests', 'data', model_name, filename)


def get_test_file_path(model_name, filename):
    return os.path.join('tests', 'test-files', 'data', model_name, filename)


def set_up_dumped_data(valid_only=False):
    clear_dumped_data()

    shutil.copytree(
        os.path.join('tests', 'test-files', 'data'),
        os.path.join('tests', 'data')
    )

    if valid_only:
        for path in glob.glob(os.path.join('tests', '*', '*', 'invalid_*')):
            os.remove(path)


def clear_dumped_data():
    shutil.rmtree(os.path.join('tests', 'data'), ignore_errors=True)


valid_data_paths = [os.path.abspath(rel_path) for rel_path in [
    'tests/data/author/jane.yml',
    'tests/data/author/john.yml',
    'tests/data/tag/django.yml',
    'tests/data/tag/python.yml',
    'tests/data/article/django.md',
    'tests/data/article/python.md',
]]


class DjangoPagesTestCase(TestCase):
    @classmethod
    def create_model_instances(cls):
        tag1 = Tag.objects.create(key='django', name='Django')
        tag2 = Tag.objects.create(key='python', name='Python')

        cls.author1 = Author.objects.create(
            key='jane',
            name='Jane Smith'
        )
        cls.author1.tags.add(tag1, tag2)

        cls.author2 = Author.objects.create(
            key='john',
            name='John Jones',
            editor=cls.author1
        )
        cls.author2.tags.add(tag1, tag2)

        cls.article1 = Article.objects.create(
            key='django',
            title='All about Django',
            content='This is an article about *Django*.\n',
            content_format='.md',
            author=cls.author1,
        )
        cls.article1.tags.add(tag1)

        cls.article2 = Article.objects.create(
            key='python',
            title='All about Python',
            content='This is an article about *Python*.\n',
            content_format='.md',
            author=cls.author2,
        )
        cls.article2.tags.add(tag2)

    def check_dumped_output_correct(self, model_type, filename):
        with open(get_path(model_type, filename)) as f:
            actual = f.read()

        with open(get_test_file_path(model_type, filename)) as f:
            expected = f.read()

        self.assertEqual(actual, expected)


class TestModel(DjangoPagesTestCase):
    @classmethod
    def setUpTestData(cls):
        cls.create_model_instances()

    def test_natural_key_without_content(self):
        self.assertEqual(self.author1.natural_key(), ('jane',))

    def test_get_by_natural_key_without_content(self):
        self.assertEqual(Author.objects.get_by_natural_key('john'), self.author2)

    def test_natural_key_with_content(self):
        self.assertEqual(self.article1.natural_key(), ('django',))

    def test_get_by_natural_key_with_content(self):
        self.assertEqual(Article.objects.get_by_natural_key('python'), self.article2)


class TestDeserialization(DjangoPagesTestCase):
    @classmethod
    def setUpClass(cls):
        super(TestDeserialization, cls).setUpClass()
        set_up_dumped_data()

    def deserialize(self, model_name, filename):
        path = get_path(model_name, filename)
        with open(path, 'rb') as f:
            return next(Deserializer(f))

    def test_deserialization_without_content(self):
        Author.objects.create(key='jane', name='Jane Smith')
        Tag.objects.create(key='django', name='Django')
        Tag.objects.create(key='python', name='Python')

        deserialized_obj = self.deserialize('author', 'john.yml')
        deserialized_obj.save()
        obj = deserialized_obj.object

        self.assertEqual(obj.key, 'john')
        self.assertEqual(obj.name, 'John Jones')
        self.assertEqual(obj.editor.key, 'jane')
        self.assertEqual([tag.key for tag in obj.tags.all()], ['django', 'python'])

    def test_deserialization_with_content(self):
        Author.objects.create(key='jane', name='Jane Smith')
        Tag.objects.create(key='django', name='Django')
        Tag.objects.create(key='python', name='Python')

        deserialized_obj = self.deserialize('article', 'django.md')
        deserialized_obj.save()
        obj = deserialized_obj.object

        self.assertEqual(obj.key, 'django')
        self.assertEqual(obj.content_format, '.md')
        self.assertEqual(obj.content, 'This is an article about *Django*.\n')
        self.assertEqual(obj.title, 'All about Django')
        self.assertEqual(obj.author.key, 'jane')
        self.assertEqual([tag.key for tag in obj.tags.all()], ['django'])

    def test_deserialization_with_invalid_yaml_without_content(self):
        with self.assertRaises(serializers.base.DeserializationError):
            self.deserialize('author', 'invalid_yaml.yml')

    def test_deserialization_with_invalid_yaml_with_content(self):
        with self.assertRaises(serializers.base.DeserializationError):
            self.deserialize('article', 'invalid_yaml.md')

    def test_deserialization_with_invalid_object_without_content(self):
        with self.assertRaises(serializers.base.DeserializationError):
            self.deserialize('author', 'invalid_object.yml')

    def test_deserialization_with_invalid_object_with_content(self):
        with self.assertRaises(serializers.base.DeserializationError):
            self.deserialize('article', 'invalid_object.md')

    def test_deserialization_with_missing_content_with_content(self):
        with self.assertRaises(serializers.base.DeserializationError):
            self.deserialize('article', 'invalid_missing_content.md')


class TestSerialization(DjangoPagesTestCase):
    @classmethod
    def setUpTestData(cls):
        cls.create_model_instances()

    def serialize(self, obj, content_format):
        serializer = Serializer()
        return serializer.serialize([obj], use_natural_foreign_keys=True)

    def test_serialization_without_content(self):
        # We use author2 here since it has a foreign key another author
        actual = self.serialize(self.author2, 'yml')
        with open(get_test_file_path('author', 'john.yml')) as f:
            expected = f.read()
        self.assertEqual(actual, expected)

    def test_serialization_with_content(self):
        actual = self.serialize(self.article1, 'md')
        with open(get_test_file_path('article', 'django.md')) as f:
            expected = f.read()
        self.assertEqual(actual, expected)


class TestLoadFromFile(DjangoPagesTestCase):
    @classmethod
    def setUpClass(cls):
        super(TestLoadFromFile, cls).setUpClass()
        set_up_dumped_data()

    def test_load_from_file_without_content(self):
        Author.objects.create(key='jane', name='Jane Smith')
        Tag.objects.create(key='django', name='Django')
        Tag.objects.create(key='python', name='Python')

        path = get_path('author', 'john.yml')
        load_from_file([path])
        obj = Author.objects.get(key='john')

        self.assertEqual(obj.key, 'john')
        self.assertEqual(obj.name, 'John Jones')
        self.assertEqual(obj.editor.key, 'jane')
        self.assertEqual([tag.key for tag in obj.tags.all()], ['django', 'python'])

    def test_load_from_file_with_content(self):
        Author.objects.create(key='jane', name='Jane Smith')
        Tag.objects.create(key='django', name='Django')
        Tag.objects.create(key='python', name='Python')

        path = get_path('article', 'django.md')
        load_from_file([path])
        obj = Article.objects.get(key='django')

        self.assertEqual(obj.key, 'django')
        self.assertEqual(obj.content_format, '.md')
        self.assertEqual(obj.content, 'This is an article about *Django*.\n')
        self.assertEqual(obj.title, 'All about Django')
        self.assertEqual(obj.author.key, 'jane')
        self.assertEqual([tag.key for tag in obj.tags.all()], ['django'])

    def test_fk_forward_references(self):
        Tag.objects.create(key='django', name='Django')
        Tag.objects.create(key='python', name='Python')

        paths = [
            get_path('author', 'john.yml'),
            get_path('author', 'jane.yml'),
        ]
        load_from_file(paths)

        obj = Author.objects.get(key='john')
        self.assertEqual(obj.editor.key, 'jane')

    def test_m2m_forward_references(self):
        paths = [
            get_path('author', 'jane.yml'),
            get_path('tag', 'django.yml'),
            get_path('tag', 'python.yml'),
        ]
        load_from_file(paths)

        obj = Author.objects.get(key='jane')
        self.assertEqual([tag.key for tag in obj.tags.all()], ['django', 'python'])


class TestDumpToFile(DjangoPagesTestCase):
    @classmethod
    def setUpTestData(cls):
        cls.create_model_instances()

    def setUp(self):
        clear_dumped_data()

    def test_dump_to_file_without_content(self):
        # We use author2 here since it has a foreign key another author
        self.author2.dump_to_file()
        self.check_dumped_output_correct('author', 'john.yml')

    def test_dump_to_file_with_content(self):
        self.article1.dump_to_file()
        self.check_dumped_output_correct('article', 'django.md')


class TestDumpPages(DjangoPagesTestCase):
    @classmethod
    def setUpTestData(cls):
        cls.create_model_instances()

    def setUp(self):
        clear_dumped_data()

    def test_dumppages(self):
        management.call_command('dumppages')
        self.check_dumped_output_correct('author', 'jane.yml')
        self.check_dumped_output_correct('author', 'john.yml')
        self.check_dumped_output_correct('tag', 'django.yml')
        self.check_dumped_output_correct('tag', 'python.yml')
        self.check_dumped_output_correct('article', 'django.md')
        self.check_dumped_output_correct('article', 'python.md')

    def test_dumppages_removes_existing_files(self):
        path = get_path('article', 'flask.md')
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, 'w'):
            pass

        management.call_command('dumppages')
        self.assertFalse(os.path.exists(path))


class TestLoadPages(DjangoPagesTestCase):
    @classmethod
    def setUpClass(cls):
        super(TestLoadPages, cls).setUpClass()
        set_up_dumped_data(valid_only=True)

    def test_loadpages(self):
        self.assertEqual(Article.objects.count(), 0)
        self.assertEqual(Author.objects.count(), 0)
        self.assertEqual(Tag.objects.count(), 0)

        management.call_command('loadpages', verbosity=0)

        self.assertEqual(Article.objects.count(), 2)
        self.assertEqual(Author.objects.count(), 2)
        self.assertEqual(Tag.objects.count(), 2)

        obj = Author.objects.get(key='john')
        self.assertEqual(obj.key, 'john')
        self.assertEqual(obj.name, 'John Jones')
        self.assertEqual(obj.editor.key, 'jane')
        self.assertEqual([tag.key for tag in obj.tags.all()], ['django', 'python'])

        obj = Article.objects.get(key='django')
        self.assertEqual(obj.key, 'django')
        self.assertEqual(obj.content_format, '.md')
        self.assertEqual(obj.content, 'This is an article about *Django*.\n')
        self.assertEqual(obj.title, 'All about Django')
        self.assertEqual(obj.author.key, 'jane')
        self.assertEqual([tag.key for tag in obj.tags.all()], ['django'])


# This needs to subclass TransactionTestCase because of some interaction
# between threading, SQLite, and some code in TestCase, in a way that I don't
# have time to care about right now... but I don't think it matters.
#
# If future-me cares, a django.db.utils.OperationalError is raised with message
# "database table is locked: tests_article", but this gets swallowed up by
# Django.  To see the error, drop into pdb in django.core.handlers.BaseHandler.
# handle_uncaught_exception
class TestBuildSite(TransactionTestCase):
    @classmethod
    def setUpClass(cls):
        super(TestBuildSite, cls).setUpClass()
        set_up_dumped_data(valid_only=True)

    def assertDirectoriesEqual(self, path1, path2):
        diff = dircmp(path1, path2)

        self.assertTrue(
            len(diff.diff_files) == 0,
            'The following files in {} and {} did not match: {}'.format(path1, path2, diff.diff_files)
        )
        self.assertTrue(
            len(diff.left_only) == 0,
            'The following files were unexpectedly present in {}: {}'.format(path1, diff.left_only)
        )
        self.assertTrue(
            len(diff.right_only) == 0,
            'The following files were not present in {}: {}'.format(path1, diff.right_only)
        )

        for common_dir in diff.common_dirs:
            new_path1 = os.path.join(path1, common_dir)
            new_path2 = os.path.join(path2, common_dir)
            self.assertDirectoriesEqual(new_path1, new_path2)

    @override_settings(DEBUG=True)  # This is required for static file handling
    def test_buildsite(self):
        management.call_command('buildsite', verbosity=0)
        self.assertDirectoriesEqual('output', os.path.join('tests', 'expected-output'))


class TestServeDynamic(DjangoPagesTestCase):
    def test_get_mtimes(self):
        set_up_dumped_data(valid_only=True)

        for ix, path in enumerate(valid_data_paths):
            t = 1400000000 + ix  # seconds since epoch
            os.utime(path, (t, t))

        mtimes = serve.get_mtimes()

        self.assertEqual(len(mtimes), len(valid_data_paths))

        for ix, path in enumerate(valid_data_paths):
            t = 1400000000 + ix  # seconds since epoch
            self.assertEqual(mtimes[path], t)

    def test_compare_mtimes(self):
        old_mtimes = {
            'unchanged': 1234,
            'changed': 2345,
            'missing': 3456,
        }

        new_mtimes = {
            'unchanged': 1234,
            'changed': 4567,
            'added': 5678,
        }

        changed_paths, missing_paths = serve.compare_mtimes(old_mtimes, new_mtimes)
        self.assertEqual(set(changed_paths), {'changed', 'added'})
        self.assertEqual(set(missing_paths), {'missing'})

    def test_load_changed_when_nothing_has_changed(self):
        # Test that no exceptions are raised
        serve.load_changed([])

    def test_remove_missing(self):
        self.create_model_instances()
        article_id = self.article2.pk
        serve.remove_missing([valid_data_paths[-1]])
        with self.assertRaises(ObjectDoesNotExist):
            Article.objects.get(pk=article_id)


# This needs to subclass TransactionTestCase for same reason as TestBuildSite.
class TestServeDynamic2(TransactionTestCase):
    def test_serve(self):
        set_up_dumped_data(valid_only=True)
        management.call_command('loadpages', verbosity=0)

        port = get_free_port()

        Thread(
            target=management.call_command,
            args=('serve', port),
            daemon=True,
        ).start()

        wait_for_server(port)

        rsp = requests.get('http://localhost:{}/articles/django/'.format(port))
        self.assertTrue(rsp.ok)
        self.assertIn('This is an article about <em>Django</em>.', rsp.text)

        path = get_path('article', 'django.md')

        with open(path) as f:
            contents = f.read()

        with open(path, 'w') as f:
            f.write(contents.replace('*Django*', '**Django**'))

        sleep(0.5)

        rsp = requests.get('http://localhost:{}/articles/django/'.format(port))
        self.assertTrue(rsp.ok)
        self.assertIn('This is an article about <strong>Django</strong>.', rsp.text)

        os.remove(path)

        sleep(0.5)

        rsp = requests.get('http://localhost:{}/articles/django/'.format(port))
        self.assertEqual(rsp.status_code, 404)
