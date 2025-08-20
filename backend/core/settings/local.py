from .base import *

DEBUG = True

ALLOWED_HOSTS = ['*']

INSTALLED_APPS += [
    'django_extensions',
]

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}

EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'

CELERY_BROKER_URL = 'redis://localhost:6379/0'
CELERY_RESULT_BACKEND = 'redis://localhost:6379/0'

CORS_ALLOW_ALL_ORIGINS = True

SECURE_SSL_REDIRECT = False
SESSION_COOKIE_SECURE = False
CSRF_COOKIE_SECURE = False

# File Upload Settings (Override to ensure they're applied)
DATA_UPLOAD_MAX_NUMBER_FILES = 800  # Allow up to 800 files in a single upload
FILE_UPLOAD_MAX_MEMORY_SIZE = 20 * 1024 * 1024  # 20MB per file
DATA_UPLOAD_MAX_MEMORY_SIZE = 900 * 1024 * 1024  # 800MB total upload size

# Theme Settings
DEFAULT_THEME = 'phoenix'  # Options: 'default', 'phoenix'