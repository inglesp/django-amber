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

SERIALIZATION_MODULES = {
    'md': 'django_pages.serializer',
}
