INSTALLED_APPS = [
    'tests',
    'django_pages',
]

SECRET_KEY = '?'

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
    },
}

# TODO remove the need for this
SERIALIZATION_MODULES = {
    'md': 'django_pages.serializer',
    'yml': 'django_pages.serializer',
}
