from filecmp import dircmp
import glob
import os
import shutil
import time
from unittest.mock import patch

from django.core import management, serializers
from django.core.exceptions import ObjectDoesNotExist
from django.test import TestCase, override_settings

from django_pages.management.commands import serve
from django_pages.python_serializer import Deserializer as PythonDeserializer

from .models import Article, Author, Tag


def get_model_type(model_name):
    return {
        'article': 'pages',
        'author': 'metadata',
        'tag': 'metadata',
    }[model_name]


def get_path(model_name, filename):
    model_type = get_model_type(model_name)
    return os.path.join('tests', model_type, model_name, filename)


def get_test_file_path(model_name, filename):
    model_type = get_model_type(model_name)
    return os.path.join('tests', 'test-files', model_type, model_name, filename)


def set_up_dumped_data(valid_only=False):
    clear_dumped_data()

    for model_type in ['metadata', 'pages']:
        shutil.copytree(
            os.path.join('tests', 'test-files', model_type),
            os.path.join('tests', model_type)
        )

    if valid_only:
        for path in glob.glob(os.path.join('tests', '*', '*', 'invalid_*')):
            os.remove(path)


def clear_dumped_data():
    for model_type in ['metadata', 'pages']:
        shutil.rmtree(os.path.join('tests', model_type), ignore_errors=True)


valid_data_paths = [os.path.abspath(rel_path) for rel_path in [
    'tests/metadata/author/jane.yml',
    'tests/metadata/author/john.yml',
    'tests/metadata/tag/django.yml',
    'tests/metadata/tag/python.yml',
    'tests/pages/article/django.md',
    'tests/pages/article/python.md',
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

    def test_metadata_natural_key(self):
        self.assertEqual(self.author1.natural_key(), ('jane',))

    def test_metadata_get_by_natural_key(self):
        self.assertEqual(Author.objects.get_by_natural_key('john'), self.author2)

    def test_page_natural_key(self):
        self.assertEqual(self.article1.natural_key(), ('django',))

    def test_page_get_by_natural_key(self):
        self.assertEqual(Article.objects.get_by_natural_key('python'), self.article2)


class TestDeserialization(DjangoPagesTestCase):
    @classmethod
    def setUpClass(cls):
        super(TestDeserialization, cls).setUpClass()
        set_up_dumped_data()

    def deserialize(self, model_name, filename):
        path = get_path(model_name, filename)
        with open(path, 'rb') as f:
            return next(serializers.deserialize('md', f))

    def test_metadata_deserialization(self):
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

    def test_page_deserialization(self):
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
            self.deserialize('article', 'invalid_missing_content.md')


class TestSerialization(DjangoPagesTestCase):
    @classmethod
    def setUpTestData(cls):
        cls.create_model_instances()

    def serialize(self, obj, content_format):
        return serializers.serialize(
            content_format,
            [obj],
            use_natural_foreign_keys=True
        )

    def test_metadata_serialization(self):
        # We use author2 here since it has a foreign key another author
        actual = self.serialize(self.author2, 'yml')
        with open(get_test_file_path('author', 'john.yml')) as f:
            expected = f.read()
        self.assertEqual(actual, expected)

    def test_page_serialization(self):
        actual = self.serialize(self.article1, 'md')
        with open(get_test_file_path('article', 'django.md')) as f:
            expected = f.read()
        self.assertEqual(actual, expected)


class TestLoadData(DjangoPagesTestCase):
    @classmethod
    def setUpClass(cls):
        super(TestLoadData, cls).setUpClass()
        set_up_dumped_data()

    def test_metadata_loaddata(self):
        Author.objects.create(key='jane', name='Jane Smith')
        Tag.objects.create(key='django', name='Django')
        Tag.objects.create(key='python', name='Python')

        path = get_path('author', 'john.yml')
        management.call_command('loaddata', path, verbosity=0)
        obj = Author.objects.get(key='john')

        self.assertEqual(obj.key, 'john')
        self.assertEqual(obj.name, 'John Jones')
        self.assertEqual(obj.editor.key, 'jane')
        self.assertEqual([tag.key for tag in obj.tags.all()], ['django', 'python'])

    def test_page_loaddata(self):
        Author.objects.create(key='jane', name='Jane Smith')
        Tag.objects.create(key='django', name='Django')
        Tag.objects.create(key='python', name='Python')

        path = get_path('article', 'django.md')
        management.call_command('loaddata', path, verbosity=0)
        obj = Article.objects.get(key='django')

        self.assertEqual(obj.key, 'django')
        self.assertEqual(obj.content_format, '.md')
        self.assertEqual(obj.content, 'This is an article about *Django*.\n')
        self.assertEqual(obj.title, 'All about Django')
        self.assertEqual(obj.author.key, 'jane')
        self.assertEqual([tag.key for tag in obj.tags.all()], ['django'])


@patch('django.core.serializers.json.PythonDeserializer', PythonDeserializer)
class TestLoadDataForwardReferences(TestCase):
    def test_fk_forward_references(self):
        path = os.path.join('tests', 'test-files', 'forward-references',
                            'forward_reference_fk.json')
        management.call_command('loaddata', path, verbosity=0)
        obj = Author.objects.get(key='john')
        self.assertEqual(obj.editor.key, 'jane')

    def test_m2m_forward_references(self):
        path = os.path.join('tests', 'test-files', 'forward-references',
                            'forward_reference_m2m.json')
        management.call_command('loaddata', path, verbosity=0)
        obj = Author.objects.get(key='john')
        self.assertEqual([tag.key for tag in obj.tags.all()], ['django', 'python'])


class TestDumpToFile(DjangoPagesTestCase):
    @classmethod
    def setUpTestData(cls):
        cls.create_model_instances()

    def setUp(self):
        clear_dumped_data()

    def test_metadata_dump_to_file(self):
        # We use author2 here since it has a foreign key another author
        self.author2.dump_to_file()
        self.check_dumped_output_correct('author', 'john.yml')

    def test_page_dump_to_file(self):
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


class TestBuildSite(DjangoPagesTestCase):
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

    def test_buildsite(self):
        management.call_command('buildsite', verbosity=0)
        diff = self.assertDirectoriesEqual('output', os.path.join('tests', 'expected-output'))


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
