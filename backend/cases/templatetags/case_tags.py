from django import template

register = template.Library()


@register.filter
def is_admin(user):
    """Check if user has admin privileges"""
    if user.is_staff or user.is_superuser:
        return True
    if hasattr(user, 'profile') and user.profile.is_admin:
        return True
    return False


@register.filter
def has_profile(user):
    """Check if user has a profile"""
    return hasattr(user, 'profile')