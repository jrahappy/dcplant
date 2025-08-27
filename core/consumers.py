"""
Example WebSocket consumers for DCPlant.
You can move these to their respective apps as needed.
"""

import json
from channels.generic.websocket import AsyncWebsocketConsumer, AsyncJsonWebsocketConsumer
from channels.db import database_sync_to_async
from django.contrib.auth import get_user_model

User = get_user_model()


class NotificationConsumer(AsyncJsonWebsocketConsumer):
    """
    WebSocket consumer for real-time notifications.
    Users connect to their personal notification channel.
    """
    
    async def connect(self):
        """Accept connection if user is authenticated."""
        self.user = self.scope["user"]
        
        if self.user.is_anonymous:
            await self.close()
        else:
            # Add user to their personal notification group
            self.user_group = f"notifications_{self.user.id}"
            await self.channel_layer.group_add(
                self.user_group,
                self.channel_name
            )
            await self.accept()
            
            # Send initial connection confirmation
            await self.send_json({
                "type": "connection",
                "message": "Connected to notification service"
            })
    
    async def disconnect(self, close_code):
        """Remove user from notification group on disconnect."""
        if hasattr(self, 'user_group'):
            await self.channel_layer.group_discard(
                self.user_group,
                self.channel_name
            )
    
    async def receive_json(self, content):
        """Handle incoming WebSocket messages."""
        message_type = content.get('type')
        
        if message_type == 'ping':
            await self.send_json({'type': 'pong'})
    
    # Handler for notification messages sent from Django
    async def notification_message(self, event):
        """Send notification to WebSocket."""
        await self.send_json({
            "type": "notification",
            "message": event["message"],
            "level": event.get("level", "info"),
            "timestamp": event.get("timestamp"),
            "data": event.get("data", {})
        })


class CaseUpdateConsumer(AsyncJsonWebsocketConsumer):
    """
    WebSocket consumer for real-time case updates.
    Multiple users can subscribe to updates for a specific case.
    """
    
    async def connect(self):
        """Accept connection and add to case group."""
        self.user = self.scope["user"]
        self.case_id = self.scope['url_route']['kwargs']['case_id']
        self.case_group = f"case_{self.case_id}"
        
        if self.user.is_anonymous:
            await self.close()
            return
        
        # Check if user has permission to view this case
        if await self.has_case_permission():
            await self.channel_layer.group_add(
                self.case_group,
                self.channel_name
            )
            await self.accept()
            
            # Notify others that someone joined
            await self.channel_layer.group_send(
                self.case_group,
                {
                    "type": "user_joined",
                    "user": self.user.username,
                    "user_id": self.user.id
                }
            )
        else:
            await self.close()
    
    async def disconnect(self, close_code):
        """Remove from case group on disconnect."""
        if hasattr(self, 'case_group'):
            # Notify others that someone left
            await self.channel_layer.group_send(
                self.case_group,
                {
                    "type": "user_left",
                    "user": self.user.username,
                    "user_id": self.user.id
                }
            )
            
            await self.channel_layer.group_discard(
                self.case_group,
                self.channel_name
            )
    
    async def receive_json(self, content):
        """Handle incoming messages."""
        message_type = content.get('type')
        
        if message_type == 'case_update':
            # Broadcast case update to all connected users
            await self.channel_layer.group_send(
                self.case_group,
                {
                    "type": "case_update_message",
                    "message": content.get("message"),
                    "user": self.user.username,
                    "user_id": self.user.id,
                    "data": content.get("data", {})
                }
            )
    
    async def case_update_message(self, event):
        """Send case update to WebSocket."""
        await self.send_json({
            "type": "case_update",
            "message": event["message"],
            "user": event["user"],
            "user_id": event["user_id"],
            "data": event.get("data", {})
        })
    
    async def user_joined(self, event):
        """Notify that a user joined."""
        await self.send_json({
            "type": "user_joined",
            "user": event["user"],
            "user_id": event["user_id"]
        })
    
    async def user_left(self, event):
        """Notify that a user left."""
        await self.send_json({
            "type": "user_left",
            "user": event["user"],
            "user_id": event["user_id"]
        })
    
    @database_sync_to_async
    def has_case_permission(self):
        """Check if user has permission to view this case."""
        # Import here to avoid circular imports
        from cases.models import Case
        
        try:
            case = Case.objects.get(id=self.case_id)
            # Add your permission logic here
            # For example: check if user is assigned to case or is admin
            return (
                self.user.is_staff or 
                case.assigned_to == self.user or
                case.created_by == self.user
            )
        except Case.DoesNotExist:
            return False


class ChatConsumer(AsyncWebsocketConsumer):
    """
    Simple chat consumer for team communication.
    """
    
    async def connect(self):
        """Accept connection and join chat room."""
        self.room_name = self.scope['url_route']['kwargs']['room_name']
        self.room_group_name = f"chat_{self.room_name}"
        self.user = self.scope["user"]
        
        if self.user.is_anonymous:
            await self.close()
            return
        
        # Join room group
        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )
        
        await self.accept()
        
        # Send join message
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'chat_message',
                'message': f"{self.user.username} has joined the chat",
                'user': 'System',
                'message_type': 'join'
            }
        )
    
    async def disconnect(self, close_code):
        """Leave chat room on disconnect."""
        if hasattr(self, 'room_group_name'):
            # Send leave message
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    'type': 'chat_message',
                    'message': f"{self.user.username} has left the chat",
                    'user': 'System',
                    'message_type': 'leave'
                }
            )
            
            # Leave room group
            await self.channel_layer.group_discard(
                self.room_group_name,
                self.channel_name
            )
    
    async def receive(self, text_data):
        """Receive message from WebSocket."""
        text_data_json = json.loads(text_data)
        message = text_data_json['message']
        
        # Send message to room group
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'chat_message',
                'message': message,
                'user': self.user.username,
                'message_type': 'message'
            }
        )
    
    async def chat_message(self, event):
        """Receive message from room group."""
        # Send message to WebSocket
        await self.send(text_data=json.dumps({
            'type': event.get('message_type', 'message'),
            'message': event['message'],
            'user': event['user']
        }))