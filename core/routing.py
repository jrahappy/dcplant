"""
WebSocket routing configuration for DCPlant.
Define your WebSocket URL patterns here.
"""

from django.urls import re_path, path
from channels.routing import URLRouter

# Import your WebSocket consumers here
from core import consumers

websocket_urlpatterns = [
    # WebSocket URL patterns
    path('ws/notifications/', consumers.NotificationConsumer.as_asgi()),
    re_path(r'ws/cases/(?P<case_id>\w+)/$', consumers.CaseUpdateConsumer.as_asgi()),
    path('ws/chat/<str:room_name>/', consumers.ChatConsumer.as_asgi()),
]

# You can also organize routes by app if needed
# from cases.routing import websocket_urlpatterns as cases_ws_patterns
# from dashboard.routing import websocket_urlpatterns as dashboard_ws_patterns
# 
# websocket_urlpatterns = []
# websocket_urlpatterns += cases_ws_patterns
# websocket_urlpatterns += dashboard_ws_patterns