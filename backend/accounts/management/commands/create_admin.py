from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from accounts.models import Organization, UserProfile


class Command(BaseCommand):
    help = 'Creates a superuser with HQ organization'

    def add_arguments(self, parser):
        parser.add_argument('--username', type=str, default='admin')
        parser.add_argument('--email', type=str, default='admin@dcplant.com')
        parser.add_argument('--password', type=str, default='changeme123')

    def handle(self, *args, **options):
        username = options['username']
        email = options['email']
        password = options['password']

        if User.objects.filter(username=username).exists():
            self.stdout.write(self.style.WARNING(f'User {username} already exists'))
            return

        # Create HQ organization if it doesn't exist
        hq_org, created = Organization.objects.get_or_create(
            name='Headquarters',
            defaults={
                'org_type': 'HQ',
                'email': 'hq@dcplant.com',
                'phone': '+1234567890'
            }
        )

        # Create superuser
        user = User.objects.create_superuser(username, email, password)
        
        # Create user profile
        UserProfile.objects.create(
            user=user,
            organization=hq_org,
            role='HQ_ADMIN',
            professional_type='ADMIN'
        )

        self.stdout.write(self.style.SUCCESS(f'Successfully created superuser {username} with HQ_ADMIN role'))