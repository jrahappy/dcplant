from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from accounts.models import UserProfile, Organization


class Command(BaseCommand):
    help = 'Ensure all users have profiles'

    def handle(self, *args, **options):
        # Get or create default organization
        default_org, _ = Organization.objects.get_or_create(
            name='Default Organization',
            defaults={
                'org_type': 'BRANCH',
                'address': 'Default Address',
                'phone': '000-000-0000'
            }
        )
        
        users_without_profile = User.objects.filter(profile__isnull=True)
        count = 0
        
        for user in users_without_profile:
            UserProfile.objects.create(
                user=user,
                organization=default_org,
                role='STAFF'
            )
            count += 1
            self.stdout.write(f'Created profile for user: {user.username}')
        
        self.stdout.write(
            self.style.SUCCESS(f'Successfully created {count} user profiles')
        )