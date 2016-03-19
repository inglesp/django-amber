import os
import shutil

from django.conf import settings
from django.contrib.staticfiles.views import serve
from django.core.management import call_command
from django.core.management.base import BaseCommand
from django.http.response import StreamingHttpResponse
from django.test import Client
from django.test.client import ClientHandler
from django.utils.six.moves.urllib.parse import urlparse
from django.utils.six.moves.urllib.request import url2pathname

import lxml.html
import tinycss


# This allows us to set .content on a FileResponse object later on.
del StreamingHttpResponse.content


class Command(BaseCommand):
    def handle(self, *args, **kwargs):
        verbosity = kwargs.get('verbosity')
        call_command('loadpages', verbosity=verbosity)

        output_path = os.path.join(settings.BASE_DIR, 'output')
        shutil.rmtree(output_path, ignore_errors=True)

        for rsp in crawl():
            path = rsp.request['PATH_INFO']
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


def crawl():
    client = Client()
    client.handler = StaticFilesClientHandler(client.handler.enforce_csrf_checks)

    seen = set()
    todo = ['/']

    while todo:
        path = todo.pop()
        rsp = client.get(path)

        if hasattr(rsp, 'streaming_content'):
            rsp.content = b''.join(rsp.streaming_content)

        yield rsp

        if 'text/html' in rsp['content-type']:
            html = rsp.content.decode('utf8')
            links = get_links_from_html(html)
        elif 'text/css' in rsp['content-type']:
            css = rsp.content.decode('utf8')
            links = get_links_from_css(css)
        else:
            continue

        for link in links:
            if urlparse(link).netloc:
                continue
            if link not in seen:
                seen.add(link)
                todo.append(link)


def get_links_from_html(html):
    dom =  lxml.html.fromstring(html)
    return dom.xpath('//@href|//@src')


def get_links_from_css(css):
    links = []
    parser = tinycss.make_parser()
    stylesheet = parser.parse_stylesheet(css)
    for ruleset in stylesheet.rules:
        for declaration in ruleset.declarations:
            for token in declaration.value:
                if token.type == 'URI':
                    links.append(token.value)

    return links


class StaticFilesClientHandler(ClientHandler):
    def __init__(self, *args, **kwargs):
        self.base_url = urlparse(settings.STATIC_URL)
        super(StaticFilesClientHandler, self).__init__(*args, **kwargs)

    def get_response(self, request):
        path = request.path
        if path.startswith(self.base_url[2]) and not self.base_url[1]:
            file_path = url2pathname(path[len(self.base_url[2]):])
            return serve(request, file_path, insecure=True)
        else:
            return super(StaticFilesClientHandler, self).get_response(request)
