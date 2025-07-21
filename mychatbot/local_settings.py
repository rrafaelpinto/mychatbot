DEBUG = True

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
        'PASSWORD': 'O!0opimo76!',
        'HOST': 'localhost',
        'PORT': '5432',
    }
}
