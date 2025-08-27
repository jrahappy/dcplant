from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from accounts.models import UserProfile, Organization


class Command(BaseCommand):
    help = 'Create sample users with different roles'

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
        
        # Sample users to create
        users_data = [
            {
                'username': 'dr.smith',
                'email': 'dr.smith@example.com',
                'password': 'password123',
                'first_name': 'John',
                'last_name': 'Smith',
                'role': 'DENTIST',
                'professional_type': 'DDS',
                'license_number': 'DDS-12345'
            },
            {
                'username': 'dr.johnson',
                'email': 'dr.johnson@example.com',
                'password': 'password123',
                'first_name': 'Emily',
                'last_name': 'Johnson',
                'role': 'DENTIST',
                'professional_type': 'DMD',
                'license_number': 'DMD-67890'
            },
            {
                'username': 'dr.williams',
                'email': 'dr.williams@example.com',
                'password': 'password123',
                'first_name': 'Michael',
                'last_name': 'Williams',
                'role': 'DENTIST',
                'professional_type': 'DDS',
                'license_number': 'DDS-11111'
            },
            {
                'username': 'assistant1',
                'email': 'assistant1@example.com',
                'password': 'password123',
                'first_name': 'Sarah',
                'last_name': 'Brown',
                'role': 'ASSISTANT',
                'professional_type': 'RDA',
                'license_number': 'RDA-22222'
            },
            {
                'username': 'frontdesk1',
                'email': 'frontdesk1@example.com',
                'password': 'password123',
                'first_name': 'Lisa',
                'last_name': 'Davis',
                'role': 'FRONT_DESK',
                'professional_type': 'ADMIN',
                'license_number': ''
            },
            {
                'username': 'branch_admin',
                'email': 'branch_admin@example.com',
                'password': 'password123',
                'first_name': 'Robert',
                'last_name': 'Miller',
                'role': 'BRANCH_ADMIN',
                'professional_type': 'ADMIN',
                'license_number': ''
            }
        ]
        
        created_count = 0
        for user_data in users_data:
            username = user_data['username']
            
            # Check if user already exists
            if User.objects.filter(username=username).exists():
                self.stdout.write(f'User {username} already exists, skipping...')
                continue
            
            # Create user
            user = User.objects.create_user(
                username=username,
                email=user_data['email'],
                password=user_data['password'],
                first_name=user_data['first_name'],
                last_name=user_data['last_name']
            )
            
            # Create or update profile
            profile, created = UserProfile.objects.get_or_create(
                user=user,
                defaults={
                    'organization': default_org,
                    'role': user_data['role'],
                    'professional_type': user_data['professional_type'],
                    'license_number': user_data['license_number']
                }
            )
            
            if not created:
                # Update existing profile
                profile.role = user_data['role']
                profile.professional_type = user_data['professional_type']
                profile.license_number = user_data['license_number']
                profile.save()
            
            created_count += 1
            self.stdout.write(
                self.style.SUCCESS(
                    f'Created user: {username} ({user_data["first_name"]} {user_data["last_name"]}) - {user_data["role"]}'
                )
            )
        
        self.stdout.write(
            self.style.SUCCESS(f'\nSuccessfully created {created_count} users')
        )
        
        # Display summary
        self.stdout.write('\n' + '='*50)
        self.stdout.write('User Summary:')
        self.stdout.write('='*50)
        
        # Show dentists
        dentists = User.objects.filter(profile__role='DENTIST')
        self.stdout.write(f'\nDentists ({dentists.count()}):')
        for dentist in dentists:
            self.stdout.write(f'  - {dentist.username}: {dentist.get_full_name()}')
        
        # Show other staff
        other_roles = ['ASSISTANT', 'FRONT_DESK', 'BRANCH_ADMIN']
        for role in other_roles:
            users = User.objects.filter(profile__role=role)
            if users.exists():
                role_display = dict(UserProfile.ROLE_CHOICES).get(role, role)
                self.stdout.write(f'\n{role_display} ({users.count()}):')
                for user in users:
                    self.stdout.write(f'  - {user.username}: {user.get_full_name()}')
        
        self.stdout.write('\n' + '='*50)
        self.stdout.write('All users can login with password: password123')
        self.stdout.write('='*50)