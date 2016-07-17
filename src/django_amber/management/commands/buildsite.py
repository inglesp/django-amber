import os
import shutil

import http_crawler
import requests

from django.conf import settings
from django.core.management import call_command
from django.core.management.base import BaseCommand

from django_amber.utils import get_free_port, run_runserver_in_thread


class Command(BaseCommand):
    def handle(self, *args, **kwargs):
        verbosity = kwargs.get('verbosity')
        call_command('loadpages', verbosity=verbosity)

        output_path = os.path.join(settings.BASE_DIR, 'output')
        shutil.rmtree(output_path, ignore_errors=True)

        port = get_free_port()

        run_runserver_in_thread(port)

        for rsp in http_crawler.crawl('http://localhost:{}/'.format(port), follow_external_links=False):
            path = http_crawler.urlparse(rsp.url).path
            segments = path.split('/')
            assert segments[0] == ''
            if segments[-1] == '':
                rel_dir_path = os.path.join(*segments[:-1])
                filename = 'index.html'
            elif '.' in segments[-1]:
                rel_dir_path = os.path.join(*segments[:-1])
                filename = segments[-1]
            else:
                rel_dir_path = os.path.join(*segments)
                filename = 'index.html'

            dir_path = os.path.join(output_path, rel_dir_path)
            os.makedirs(dir_path, exist_ok=True)
            with open(os.path.join(dir_path, filename), 'wb') as f:
                f.write(rsp.content)
