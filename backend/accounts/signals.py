from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.auth.models import User
from .models import UserProfile, Organization


@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    """Create a UserProfile when a new user is created"""
    if created:
        # Get or create default organization
        default_org, _ = Organization.objects.get_or_create(
            name='Default Organization',
            defaults={
                'org_type': 'BRANCH',
                'address': 'Default Address',
                'phone': '000-000-0000'
            }
        )
        
        # Create user profile
        UserProfile.objects.create(
            user=instance,
            organization=default_org,
            role='STAFF'  # Default role
        )


@receiver(post_save, sender=User)
def save_user_profile(sender, instance, **kwargs):
    """Save the UserProfile when the user is saved"""
    if hasattr(instance, 'profile'):
        instance.profile.save()