import datetime
from filecmp import dircmp
import glob
from multiprocessing import Process
import os
import signal
import shutil
from time import sleep
import unittest

from django.conf import settings
from django.core import management, serializers
from django.core.exceptions import ObjectDoesNotExist
from django.test import TestCase, TransactionTestCase, override_settings

from django_amber.management.commands import serve
from django.core.management.base import CommandError
from django_amber.models import parse_dump_path
from django_amber.serialization_helpers import dump_to_file, load_from_file
from django_amber.serializer import Deserializer, Serializer
from django_amber.utils import get_free_port, get_with_retries, wait_for_server

from .models import Article, Author, Comment, DateTimeModel, Tag


def get_path(model_name, key):
    base_path = os.path.join(settings.BASE_DIR, 'tests', 'data')
    return _get_path(base_path, model_name, key)


def get_test_file_path(model_name, key):
    base_path = os.path.join(settings.BASE_DIR, 'tests', 'test-files', 'data')
    return _get_path(base_path, model_name, key)


def _get_path(base_path, model_name, key):
    if model_name == 'article':
        language, slug = key.split('/')
        return os.path.join(base_path, 'articles', language, slug + '.md')
    else:
        if model_name == 'comment':
            filename = '{}.md'.format(key)
        else:
            filename = '{}.yml'.format(key)
        return os.path.join(base_path, model_name, filename)


def set_up_dumped_data(valid_only=False):
    clear_dumped_data()

    shutil.copytree(
        os.path.join('tests', 'test-files', 'data'),
        os.path.join('tests', 'data')
    )

    if valid_only:
        for path in glob.glob(os.path.join('tests', 'data', '*', 'invalid_*')):
            os.remove(path)

        for path in glob.glob(os.path.join('tests', 'data', '*', '*', 'invalid_*')):
            os.remove(path)


def clear_dumped_data():
    shutil.rmtree(os.path.join('tests', 'data'), ignore_errors=True)


valid_data_paths = [os.path.abspath(rel_path) for rel_path in [
    'tests/data/author/jane.yml',
    'tests/data/author/john.yml',
    'tests/data/tag/django.yml',
    'tests/data/tag/python.yml',
    'tests/data/articles/en/django.md',
    'tests/data/articles/en/python.md',
    'tests/data/comment/en/django/2016-12-31.md',
    'tests/data/datetimemodel/quoted-fields.yml',
    'tests/data/datetimemodel/quoted-time-field.yml',
    'tests/data/datetimemodel/unquoted-fields.yml',
    'tests/data/datetimemodel/null-fields.yml',
]]


class DjangoPagesTestCase(TestCase):
    @classmethod
    def create_model_instances(cls):
        cls.tag1 = Tag.objects.create(key='django', name='Django')
        cls.tag2 = Tag.objects.create(key='python', name='Python')

        cls.author1 = Author.objects.create(
            key='jane',
            name='Jane Smith'
        )
        cls.author1.tags.add(cls.tag1, cls.tag2)

        cls.author2 = Author.objects.create(
            key='john',
            name='John Jones',
            editor=cls.author1
        )
        cls.author2.tags.add(cls.tag1, cls.tag2)

        cls.article1 = Article.objects.create(
            key='en/django',
            title='All about Django',
            language='en',
            slug='django',
            content='This is an article about *Django*.\n',
            content_format='md',
            author=cls.author1,
        )
        cls.article1.tags.add(cls.tag1)

        cls.article2 = Article.objects.create(
            key='en/python',
            title='All about Python',
            language='en',
            slug='python',
            content='This is an article about *Python*.\n',
            content_format='md',
            author=cls.author2,
        )
        cls.article2.tags.add(cls.tag2)

    def check_dumped_output_correct(self, model_type, key):
        with open(get_path(model_type, key)) as f:
            actual = f.read()

        with open(get_test_file_path(model_type, key)) as f:
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
        self.assertEqual(self.article1.natural_key(), ('en/django',))

    def test_get_by_natural_key_with_content(self):
        self.assertEqual(Article.objects.get_by_natural_key('en/python'), self.article2)

    def test_fields_from_key(self):
        self.assertEqual(Article.fields_from_key('en/django'), {'language': 'en', 'slug': 'django'})

    def test_fields_from_key_with_no_key_structure(self):
        self.assertEqual(Author.fields_from_key('john'), {})

    def test_set_key(self):
        self.article1.key = ''
        self.article1.set_key()
        self.assertEqual(self.article1.key, 'en/django')

    def test_parse_dump_path(self):
        path = os.path.join(settings.BASE_DIR, 'tests', 'data', 'articles', 'en', 'django.md')
        self.assertEqual(parse_dump_path(path), (Article, 'en/django', 'md'))


class TestDeserialization(DjangoPagesTestCase):
    @classmethod
    def setUpClass(cls):
        super(TestDeserialization, cls).setUpClass()
        set_up_dumped_data()

    def deserialize(self, model_name, key):
        path = get_path(model_name, key)
        with open(path, 'rb') as f:
            return next(Deserializer(f))

    def test_deserialization_without_content(self):
        Author.objects.create(key='jane', name='Jane Smith')
        Tag.objects.create(key='django', name='Django')
        Tag.objects.create(key='python', name='Python')

        deserialized_obj = self.deserialize('author', 'john')
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

        deserialized_obj = self.deserialize('article', 'en/django')
        deserialized_obj.save()
        obj = deserialized_obj.object

        self.assertEqual(obj.key, 'en/django')
        self.assertEqual(obj.content_format, 'md')
        self.assertEqual(obj.content, 'This is an article about *Django*.\n')
        self.assertEqual(obj.title, 'All about Django')
        self.assertEqual(obj.slug, 'django')
        self.assertEqual(obj.language, 'en')
        self.assertEqual(obj.author.key, 'jane')
        self.assertEqual([tag.key for tag in obj.tags.all()], ['django'])

    def test_deserialization_where_all_fields_in_key(self):
        Article.objects.create(
            key='en/django',
            language='en',
            slug='django',
        )

        deserialized_obj = self.deserialize('comment', 'en/django/2016-12-31')
        deserialized_obj.save()
        obj = deserialized_obj.object

        self.assertEqual(obj.key, 'en/django/2016-12-31')
        self.assertEqual(obj.content_format, 'md')
        self.assertEqual(obj.content, 'First post!\n')
        self.assertEqual(obj.article.key, 'en/django')

    def test_deserialization_of_datetime_fields(self):
        deserialized_obj = self.deserialize('datetimemodel', 'quoted-fields')
        deserialized_obj.save()
        obj = deserialized_obj.object

        self.assertEqual(obj.key, 'quoted-fields')
        self.assertEqual(obj.date, datetime.date(2016, 12, 30))
        self.assertEqual(obj.time, datetime.time(16, 17, 18))
        self.assertEqual(obj.datetime, datetime.datetime(2016, 12, 30, 16, 17, 18))

    def test_deserialization_of_unquoted_time_field(self):
        deserialized_obj = self.deserialize('datetimemodel', 'unquoted-fields')
        deserialized_obj.save()
        obj = deserialized_obj.object

        self.assertEqual(obj.key, 'unquoted-fields')
        self.assertEqual(obj.date, datetime.date(2016, 12, 30))
        self.assertEqual(obj.time, datetime.time(16, 17, 18))
        self.assertEqual(obj.datetime, datetime.datetime(2016, 12, 30, 16, 17, 18))

    def test_deserialization_of_null_datetime_fields(self):
        deserialized_obj = self.deserialize('datetimemodel', 'null-fields')
        deserialized_obj.save()
        obj = deserialized_obj.object

        self.assertEqual(obj.key, 'null-fields')
        self.assertEqual(obj.date, None)
        self.assertEqual(obj.time, None)
        self.assertEqual(obj.datetime, None)

    def test_deserialization_with_invalid_yaml_without_content(self):
        with self.assertRaises(serializers.base.DeserializationError):
            self.deserialize('author', 'invalid_yaml')

    def test_deserialization_with_invalid_yaml_with_content(self):
        with self.assertRaises(serializers.base.DeserializationError):
            self.deserialize('article', 'en/invalid_yaml')

    def test_deserialization_with_invalid_object_without_content(self):
        with self.assertRaises(serializers.base.DeserializationError):
            self.deserialize('author', 'invalid_object')

    def test_deserialization_with_invalid_object_with_content(self):
        with self.assertRaises(serializers.base.DeserializationError):
            self.deserialize('article', 'en/invalid_object')

    def test_deserialization_with_invalid_object_with_missing_content(self):
        with self.assertRaises(serializers.base.DeserializationError) as cm:
            self.deserialize('article', 'en/invalid_missing_content')
        self.assertEqual(str(cm.exception), 'Missing content')


class TestSerialization(DjangoPagesTestCase):
    @classmethod
    def setUpTestData(cls):
        cls.create_model_instances()

    def serialize(self, obj):
        serializer = Serializer()
        return serializer.serialize([obj], use_natural_foreign_keys=True)

    def test_serialization_without_content(self):
        # We use author2 here since it has a foreign key another author
        actual = self.serialize(self.author2)
        with open(get_test_file_path('author', 'john')) as f:
            expected = f.read()
        self.assertEqual(actual, expected)

    def test_serialization_with_content(self):
        actual = self.serialize(self.article1)
        with open(get_test_file_path('article', 'en/django')) as f:
            expected = f.read()
        self.assertEqual(actual, expected)

    def test_serialization_of_datetime_fields(self):
        m = DateTimeModel.objects.create(
            date=datetime.date(2016, 12, 30),
            time=datetime.time(16, 17, 18),
            datetime=datetime.datetime(2016, 12, 30, 16, 17, 18),
        )
        actual = self.serialize(m)
        with open(get_test_file_path('datetimemodel', 'quoted-time-field')) as f:
            expected = f.read()
        self.assertEqual(actual, expected)

    def test_serialization_of_null_datetime_fields(self):
        m = DateTimeModel.objects.create(
            date=None,
            time=None,
            datetime=None,
        )
        actual = self.serialize(m)
        self.assertEqual(actual, '{}\n')


class TestLoadFromFile(DjangoPagesTestCase):
    @classmethod
    def setUpClass(cls):
        super(TestLoadFromFile, cls).setUpClass()
        set_up_dumped_data()

    def test_load_from_file_without_content(self):
        Author.objects.create(key='jane', name='Jane Smith')
        Tag.objects.create(key='django', name='Django')
        Tag.objects.create(key='python', name='Python')

        path = get_path('author', 'john')
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

        path = get_path('article', 'en/django')
        load_from_file([path])
        obj = Article.objects.get(key='en/django')

        self.assertEqual(obj.key, 'en/django')
        self.assertEqual(obj.content_format, 'md')
        self.assertEqual(obj.content, 'This is an article about *Django*.\n')
        self.assertEqual(obj.title, 'All about Django')
        self.assertEqual(obj.slug, 'django')
        self.assertEqual(obj.language, 'en')
        self.assertEqual(obj.author.key, 'jane')
        self.assertEqual([tag.key for tag in obj.tags.all()], ['django'])

    def test_fk_forward_references(self):
        Tag.objects.create(key='django', name='Django')
        Tag.objects.create(key='python', name='Python')

        paths = [
            get_path('author', 'john'),
            get_path('author', 'jane'),
        ]
        load_from_file(paths)

        obj = Author.objects.get(key='john')
        self.assertEqual(obj.editor.key, 'jane')

    def test_m2m_forward_references(self):
        paths = [
            get_path('author', 'jane'),
            get_path('tag', 'django'),
            get_path('tag', 'python'),
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
        dump_to_file(self.author2)
        self.check_dumped_output_correct('author', 'john')

    def test_dump_to_file_with_content(self):
        dump_to_file(self.article1)
        self.check_dumped_output_correct('article', 'en/django')

    def test_dump_to_file_with_key_not_set(self):
        self.article1.key = ''
        dump_to_file(self.article1)
        self.check_dumped_output_correct('article', 'en/django')


class TestDumpPages(DjangoPagesTestCase):
    @classmethod
    def setUpTestData(cls):
        cls.create_model_instances()

    def setUp(self):
        clear_dumped_data()

    def test_dumppages(self):
        management.call_command('dumppages')
        self.check_dumped_output_correct('author', 'jane')
        self.check_dumped_output_correct('author', 'john')
        self.check_dumped_output_correct('tag', 'django')
        self.check_dumped_output_correct('tag', 'python')
        self.check_dumped_output_correct('article', 'en/django')
        self.check_dumped_output_correct('article', 'en/python')

    def test_dumppages_removes_existing_files(self):
        path = get_path('article', 'en/flask')
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, 'w'):
            pass

        management.call_command('dumppages')
        self.assertFalse(os.path.exists(path))


class TestLoadPages(DjangoPagesTestCase):
    @classmethod
    def setUpClass(cls):
        super(TestLoadPages, cls).setUpClass()

    def test_loadpages(self):
        set_up_dumped_data(valid_only=True)

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

        obj = Article.objects.get(key='en/django')
        self.assertEqual(obj.key, 'en/django')
        self.assertEqual(obj.content_format, 'md')
        self.assertEqual(obj.content, 'This is an article about *Django*.\n')
        self.assertEqual(obj.title, 'All about Django')
        self.assertEqual(obj.slug, 'django')
        self.assertEqual(obj.language, 'en')
        self.assertEqual(obj.author.key, 'jane')
        self.assertEqual([tag.key for tag in obj.tags.all()], ['django'])

        obj = Comment.objects.get(key= 'en/django/2016-12-31')
        self.assertEqual(obj.key, 'en/django/2016-12-31')
        self.assertEqual(obj.content_format, 'md')
        self.assertEqual(obj.content, 'First post!\n')
        self.assertEqual(obj.article.key, 'en/django')

    def test_loadpages_with_invalid_data(self):
        set_up_dumped_data()

        self.assertEqual(Article.objects.count(), 0)
        self.assertEqual(Author.objects.count(), 0)
        self.assertEqual(Tag.objects.count(), 0)

        with self.assertRaises(CommandError):
            management.call_command('loadpages', verbosity=0)

    def test_loadpages_with_dotfile_in_dump_dir(self):
        set_up_dumped_data(valid_only=True)

        path = get_path('article', 'en/.django') + '.swp'
        with open(path, 'wb') as f:
            # This is the opening of a Vim swap file
            f.write(b'\x62\x30\x56\x49\x4d\x20\x37\x2e\x33\x00\x00\x00\x00\x10\x00\x00')

        management.call_command('loadpages', verbosity=0)


# This needs to subclass TransactionTestCase instead of TestCase, because
# TestCase executes all database statements inside a transaction, meaning that
# the objects that loadpages creates won't be visible to runserver.
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

    @override_settings(DJANGO_AMBER_CNAME='amber.example.com')
    @override_settings(DEBUG=True)  # This is required for static file handling
    def test_buildsite_with_cname(self):
        management.call_command('buildsite', verbosity=0)
        path = os.path.join('output', 'CNAME')
        with open(path) as f:
            self.assertEqual('amber.example.com', f.read())

    @override_settings(DEBUG=True)  # This is required for static file handling
    def test_buildsite_without_cname(self):
        del settings.DJANGO_AMBER_CNAME
        management.call_command('buildsite', verbosity=0)
        path = os.path.join('output', 'CNAME')
        self.assertFalse(os.path.exists(path))


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

        article_id = self.article1.pk
        serve.remove_missing([valid_data_paths[4]])
        with self.assertRaises(ObjectDoesNotExist):
            Article.objects.get(pk=article_id)


# This needs to subclass TransactionTestCase for same reason as TestBuildSite.
class TestServeDynamic2(TransactionTestCase):
    @unittest.removeHandler  # This allows us send SIGINT to the serve process
    def test_serve(self):
        set_up_dumped_data(valid_only=True)

        port = get_free_port()

        p = Process(
            target=management.call_command,
            args=('serve', port),
        )

        p.start()

        wait_for_server(port)

        try:
            self._test_serve(port)
        finally:
            os.kill(p.pid, signal.SIGINT)

    def _test_serve(self, port):
        rsp = get_with_retries('http://localhost:{}/articles/en/django/'.format(port))
        self.assertTrue(rsp.ok)
        self.assertIn('This is an article about <em>Django</em>.', rsp.text)

        path = get_path('article', 'en/django')

        with open(path) as f:
            contents = f.read()

        with open(path, 'w') as f:
            f.write(contents.replace('*Django*', '**Django**'))

        sleep(0.5)

        rsp = get_with_retries('http://localhost:{}/articles/en/django/'.format(port))
        self.assertTrue(rsp.ok)
        self.assertIn('This is an article about <strong>Django</strong>.', rsp.text)

        os.remove(path)

        sleep(0.5)

        rsp = get_with_retries('http://localhost:{}/articles/en/django/'.format(port))
        self.assertEqual(rsp.status_code, 404)
