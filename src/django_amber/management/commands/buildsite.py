import os
import shutil

import http_crawler

from django.conf import settings
from django.core.management import call_command
from django.core.management.base import BaseCommand

from django_amber.utils import get_free_port, run_runserver_in_process


class Command(BaseCommand):
    def handle(self, *args, **kwargs):
        port = get_free_port()

        p = run_runserver_in_process(port)

        try:
            self.buildsite(port)
        finally:
            p.terminate()

    def buildsite(self, port):
        call_command('loadpages')

        output_path = os.path.join(settings.BASE_DIR, 'output')
        shutil.rmtree(output_path, ignore_errors=True)

        for rsp in http_crawler.crawl('http://localhost:{}/'.format(port)):
            rsp.raise_for_status()

            parsed_url = http_crawler.urlparse(rsp.url)

            if parsed_url.netloc != 'localhost:{}'.format(port):
                # This is an external request, which we don't care about
                continue

            path = parsed_url.path
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

        cname = getattr(settings, 'DJANGO_AMBER_CNAME', None)

        if cname:
            with open(os.path.join(output_path, 'CNAME'), 'w') as f:
                f.write(cname)
