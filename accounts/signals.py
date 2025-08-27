from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.auth.models import User
from .models import UserProfile, Organization


@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    """Create a UserProfile when a new user is created"""
    if created:
        # Check if profile already exists
        if not hasattr(instance, 'profile'):
            # Get or create default organization
            default_org, _ = Organization.objects.get_or_create(
                name='Default Organization',
                defaults={
                    'org_type': 'BRANCH',
                    'address': 'Default Address',
                    'phone': '000-000-0000'
                }
            )
            
            # Create user profile with valid role
            UserProfile.objects.get_or_create(
                user=instance,
                defaults={
                    'organization': default_org,
                    'role': 'READ_ONLY'  # Default role
                }
            )


@receiver(post_save, sender=User)
def save_user_profile(sender, instance, **kwargs):
    """Save the UserProfile when the user is saved"""
    if hasattr(instance, 'profile'):
        instance.profile.save()