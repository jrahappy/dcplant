"""
ASGI config for DCPlant project.

It exposes the ASGI callable as a module-level variable named ``application``.
Configured with Django Channels for WebSocket support.

For more information on this file, see
https://docs.djangoproject.com/en/5.0/howto/deployment/asgi/
"""

import os
from django.core.asgi import get_asgi_application
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.auth import AuthMiddlewareStack
from channels.security.websocket import AllowedHostsOriginValidator

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')

# Initialize Django ASGI application early to ensure the AppRegistry
# is populated before importing code that may import ORM models.
django_asgi_app = get_asgi_application()

# Import routing after Django is setup
from core.routing import websocket_urlpatterns

application = ProtocolTypeRouter({
    # HTTP traffic is handled by Django's ASGI application
    "http": django_asgi_app,
    
    # WebSocket traffic is handled by Channels
    "websocket": AllowedHostsOriginValidator(
        AuthMiddlewareStack(
            URLRouter(
                websocket_urlpatterns
            )
        )
    ),
})
