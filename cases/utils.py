from accounts.models import UserProfile, Organization


def ensure_user_profile(user):
    """
    Ensure that a user has a profile. 
    Creates one with default organization if it doesn't exist.
    """
    if not hasattr(user, 'profile'):
        default_org, _ = Organization.objects.get_or_create(
            name='Default Organization',
            defaults={
                'org_type': 'BRANCH',
                'address': 'Default Address',
                'phone': '000-000-0000'
            }
        )
        UserProfile.objects.create(
            user=user,
            organization=default_org,
            role='STAFF'
        )
    return user.profile