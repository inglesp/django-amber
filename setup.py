from setuptools import find_packages, setup

import os
import re


def read(*parts):
    here = os.path.abspath(os.path.dirname(__file__))
    with open(os.path.join(here, *parts)) as f:
        return f.read()

VERSION = re.search(
    "^__version__ = '(.*)'$",
    read('src', 'django_amber', '__init__.py'),
    re.MULTILINE
).group(1)

if __name__ == '__main__':
    setup(
        name='django-amber',
        version=VERSION,
        description='A Django-powered static site generator',
        long_description=read('README.md'),
        packages=find_packages(where='src'),
        package_dir={'': 'src'},
        install_requires=['Django', 'http-crawler', 'requests', 'PyYAML'],
        url='http://github.com/inglesp/django-amber',
        author='Peter Inglesby',
        author_email='peter.inglesby@gmail.com',
        license='License :: OSI Approved :: MIT License',
    )
