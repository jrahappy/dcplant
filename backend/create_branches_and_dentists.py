"""
Script to create 3 branch offices and 1 dentist user for each branch
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

def create_branches_and_dentists():
    """Create 3 branch offices with 1 dentist each"""
    
    branches_data = [
        {
            'name': 'DCPlant Downtown Branch',
            'address': '123 Main Street, Downtown, City 10001',
            'phone': '555-0101',
            'email': 'downtown@dcplant.com',
            'dentist': {
                'username': 'dr.smith',
                'email': 'dr.smith@dcplant.com',
                'first_name': 'John',
                'last_name': 'Smith',
                'password': 'DentistPass123!'
            }
        },
        {
            'name': 'DCPlant Westside Branch',
            'address': '456 West Avenue, Westside, City 10002',
            'phone': '555-0102',
            'email': 'westside@dcplant.com',
            'dentist': {
                'username': 'dr.johnson',
                'email': 'dr.johnson@dcplant.com',
                'first_name': 'Emily',
                'last_name': 'Johnson',
                'password': 'DentistPass123!'
            }
        },
        {
            'name': 'DCPlant Northside Branch',
            'address': '789 North Boulevard, Northside, City 10003',
            'phone': '555-0103',
            'email': 'northside@dcplant.com',
            'dentist': {
                'username': 'dr.williams',
                'email': 'dr.williams@dcplant.com',
                'first_name': 'Michael',
                'last_name': 'Williams',
                'password': 'DentistPass123!'
            }
        }
    ]
    
    with transaction.atomic():
        for branch_data in branches_data:
            # Create or get the branch organization
            branch, created = Organization.objects.get_or_create(
                name=branch_data['name'],
                defaults={
                    'org_type': 'BRANCH',
                    'address': branch_data['address'],
                    'phone': branch_data['phone'],
                    'email': branch_data['email'],
                    'is_active': True
                }
            )
            
            if created:
                print(f"[+] Created branch: {branch.name}")
            else:
                print(f"[-] Branch already exists: {branch.name}")
            
            # Create dentist user
            dentist_data = branch_data['dentist']
            
            # Check if user already exists
            if User.objects.filter(username=dentist_data['username']).exists():
                user = User.objects.get(username=dentist_data['username'])
                print(f"  [-] Dentist user already exists: {dentist_data['username']}")
            else:
                user = User.objects.create_user(
                    username=dentist_data['username'],
                    email=dentist_data['email'],
                    password=dentist_data['password'],
                    first_name=dentist_data['first_name'],
                    last_name=dentist_data['last_name']
                )
                print(f"  [+] Created dentist user: {dentist_data['username']}")
            
            # Create or update user profile
            profile, profile_created = UserProfile.objects.get_or_create(
                user=user,
                defaults={
                    'organization': branch,
                    'role': 'DENTIST',
                    'phone': branch_data['phone'],
                    'professional_type': 'DDS',
                    'license_number': f'DEN-{user.username.upper().replace(".", "")}-2025',
                    'is_active': True
                }
            )
            
            if not profile_created:
                # Update existing profile
                profile.organization = branch
                profile.role = 'DENTIST'
                profile.professional_type = 'DDS'
                profile.save()
                print(f"  [-] Updated profile for: {user.get_full_name()}")
            else:
                print(f"  [+] Created profile for: {user.get_full_name()}")
            
            print(f"    Role: {profile.get_role_display()}")
            print(f"    Professional Type: {profile.get_professional_type_display()}")
            print(f"    License: {profile.license_number}")
            print()
    
    print("\n" + "="*50)
    print("Summary of Created Branches and Dentists:")
    print("="*50)
    
    for branch_data in branches_data:
        dentist_data = branch_data['dentist']
        print(f"\nBranch: {branch_data['name']}")
        print(f"  Dentist: Dr. {dentist_data['first_name']} {dentist_data['last_name']}")
        print(f"  Username: {dentist_data['username']}")
        print(f"  Password: {dentist_data['password']}")
        print(f"  Email: {dentist_data['email']}")
    
    print("\n" + "="*50)
    print("All dentists can login with password: DentistPass123!")
    print("="*50)

if __name__ == '__main__':
    print("Creating branches and dentist users...\n")
    create_branches_and_dentists()
    print("\nDone!")