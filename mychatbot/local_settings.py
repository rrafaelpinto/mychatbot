import os


DEBUG = os.environ.get('DJANGO_DEBUG', 'False').lower() in {'1', 'true', 'yes'}

ALLOWED_HOSTS = [
    '161.35.114.168',
    'resumebot.info',
    'www.resumebot.info',
    'localhost',
    '127.0.0.1',
]

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': 'resumebot',
        'USER': 'postgres',
        'PASSWORD': os.environ.get('POSTGRES_PASSWORD', ''),
        'HOST': 'localhost',
        'PORT': '5432',
    }
}
