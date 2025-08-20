"""
WSGI config for DCPlant project.

It exposes the WSGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/5.0/howto/deployment/wsgi/
"""

import os
from django.core.wsgi import get_wsgi_application

# Set default settings module based on environment
settings_module = os.environ.get('DJANGO_SETTINGS_MODULE', 'core.settings.local')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', settings_module)

application = get_wsgi_application()

# Add whitenoise for static files serving in production
if settings_module == 'core.settings.production':
    try:
        from whitenoise import WhiteNoise
        application = WhiteNoise(
            application,
            root=os.path.join(os.path.dirname(os.path.dirname(__file__)), 'staticfiles')
        )
        application.add_files(
            os.path.join(os.path.dirname(os.path.dirname(__file__)), 'media'), 
            prefix='/media/'
        )
    except ImportError:
        pass
