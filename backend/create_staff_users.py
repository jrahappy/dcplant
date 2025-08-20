"""
Script to create additional staff users for each branch
"""
import os
import sys
import django

# Setup Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings.local')
django.setup()

from django.contrib.auth.models import User
from accounts.models import Organization, UserProfile
from django.db import transaction

def create_staff_users():
    """Create staff users for each branch"""
    
    staff_data = [
        # Downtown Branch Staff
        {
            'branch_name': 'DCPlant Downtown Branch',
            'users': [
                {
                    'username': 'nurse.davis',
                    'email': 'nurse.davis@dcplant.com',
                    'first_name': 'Sarah',
                    'last_name': 'Davis',
                    'password': 'StaffPass123!',
                    'role': 'ASSISTANT',
                    'professional_type': 'RDH'
                },
                {
                    'username': 'receptionist.brown',
                    'email': 'receptionist.brown@dcplant.com',
                    'first_name': 'Lisa',
                    'last_name': 'Brown',
                    'password': 'StaffPass123!',
                    'role': 'FRONT_DESK',
                    'professional_type': 'ADMIN'
                }
            ]
        },
        # Westside Branch Staff
        {
            'branch_name': 'DCPlant Westside Branch',
            'users': [
                {
                    'username': 'nurse.taylor',
                    'email': 'nurse.taylor@dcplant.com',
                    'first_name': 'Amanda',
                    'last_name': 'Taylor',
                    'password': 'StaffPass123!',
                    'role': 'ASSISTANT',
                    'professional_type': 'RDA'
                },
                {
                    'username': 'receptionist.garcia',
                    'email': 'receptionist.garcia@dcplant.com',
                    'first_name': 'Maria',
                    'last_name': 'Garcia',
                    'password': 'StaffPass123!',
                    'role': 'FRONT_DESK',
                    'professional_type': 'ADMIN'
                }
            ]
        },
        # Northside Branch Staff
        {
            'branch_name': 'DCPlant Northside Branch',
            'users': [
                {
                    'username': 'nurse.wilson',
                    'email': 'nurse.wilson@dcplant.com',
                    'first_name': 'Jennifer',
                    'last_name': 'Wilson',
                    'password': 'StaffPass123!',
                    'role': 'ASSISTANT',
                    'professional_type': 'RDH'
                },
                {
                    'username': 'receptionist.martinez',
                    'email': 'receptionist.martinez@dcplant.com',
                    'first_name': 'Carlos',
                    'last_name': 'Martinez',
                    'password': 'StaffPass123!',
                    'role': 'FRONT_DESK',
                    'professional_type': 'ADMIN'
                }
            ]
        }
    ]
    
    with transaction.atomic():
        for branch_staff in staff_data:
            # Get the branch
            try:
                branch = Organization.objects.get(name=branch_staff['branch_name'])
                print(f"\nBranch: {branch.name}")
            except Organization.DoesNotExist:
                print(f"\n[!] Branch not found: {branch_staff['branch_name']}")
                continue
            
            for user_data in branch_staff['users']:
                # Check if user already exists
                if User.objects.filter(username=user_data['username']).exists():
                    user = User.objects.get(username=user_data['username'])
                    print(f"  [-] User already exists: {user_data['username']}")
                else:
                    user = User.objects.create_user(
                        username=user_data['username'],
                        email=user_data['email'],
                        password=user_data['password'],
                        first_name=user_data['first_name'],
                        last_name=user_data['last_name']
                    )
                    print(f"  [+] Created user: {user_data['username']}")
                
                # Create or update user profile
                profile, profile_created = UserProfile.objects.get_or_create(
                    user=user,
                    defaults={
                        'organization': branch,
                        'role': user_data['role'],
                        'phone': branch.phone,
                        'professional_type': user_data['professional_type'],
                        'is_active': True
                    }
                )
                
                if not profile_created:
                    # Update existing profile
                    profile.organization = branch
                    profile.role = user_data['role']
                    profile.professional_type = user_data['professional_type']
                    profile.save()
                    print(f"    [-] Updated profile for: {user.get_full_name()}")
                else:
                    print(f"    [+] Created profile for: {user.get_full_name()}")
                
                print(f"      Role: {profile.get_role_display()}")
                if profile.professional_type:
                    print(f"      Type: {profile.get_professional_type_display()}")
    
    print("\n" + "="*50)
    print("Summary of All Users by Branch:")
    print("="*50)
    
    branches = Organization.objects.filter(org_type='BRANCH').exclude(name='Default Organization')
    for branch in branches:
        print(f"\n{branch.name}:")
        users = UserProfile.objects.filter(organization=branch).select_related('user')
        for profile in users:
            print(f"  - {profile.user.get_full_name()} ({profile.user.username})")
            print(f"    Role: {profile.get_role_display()}")
            print(f"    Email: {profile.user.email}")
    
    print("\n" + "="*50)
    print("Login Credentials:")
    print("="*50)
    print("Dentists: Password = DentistPass123!")
    print("Staff: Password = StaffPass123!")
    print("="*50)

if __name__ == '__main__':
    print("Creating staff users for branches...\n")
    create_staff_users()
    print("\nDone!")