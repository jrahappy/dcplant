from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from accounts.models import Organization, UserProfile
from cases.models import Patient, Category, Case, Comment
from datetime import date, datetime, timedelta
import random


class Command(BaseCommand):
    help = 'Creates sample cases and patients for testing'

    def handle(self, *args, **options):
        # Get or create organizations
        hq, _ = Organization.objects.get_or_create(
            name='Headquarters',
            defaults={'org_type': 'HQ', 'email': 'hq@dcplant.com'}
        )
        
        branch_a, _ = Organization.objects.get_or_create(
            name='Branch A',
            defaults={'org_type': 'BRANCH', 'email': 'branch-a@dcplant.com'}
        )
        
        # Get or create users
        admin_user = User.objects.filter(is_superuser=True).first()
        if not admin_user:
            admin_user = User.objects.create_superuser(
                'admin', 'admin@dcplant.com', 'admin123'
            )
        
        # Ensure admin has profile
        if not hasattr(admin_user, 'profile'):
            UserProfile.objects.create(
                user=admin_user,
                organization=hq,
                role='HQ_ADMIN'
            )
        
        # Create dentist user
        dentist_user, created = User.objects.get_or_create(
            username='dentist1',
            defaults={
                'email': 'dentist@branch-a.com',
                'first_name': 'John',
                'last_name': 'Smith'
            }
        )
        if created:
            dentist_user.set_password('dentist123')
            dentist_user.save()
            UserProfile.objects.create(
                user=dentist_user,
                organization=branch_a,
                role='DENTIST',
                professional_type='DDS'
            )
        
        # Create categories
        categories = [
            {'name': 'General Dentistry', 'slug': 'general-dentistry'},
            {'name': 'Orthodontics', 'slug': 'orthodontics'},
            {'name': 'Endodontics', 'slug': 'endodontics'},
            {'name': 'Periodontics', 'slug': 'periodontics'},
            {'name': 'Oral Surgery', 'slug': 'oral-surgery'},
        ]
        
        for cat_data in categories:
            Category.objects.get_or_create(**cat_data)
        
        # Create sample patients
        patients_data = [
            {
                'mrn': 'MRN001',
                'first_name': 'Alice',
                'last_name': 'Johnson',
                'date_of_birth': date(1985, 3, 15),
                'gender': 'F',
                'email': 'alice@example.com',
                'phone': '+1234567890',
                'organization': branch_a,
                'consent_given': True,
                'consent_date': datetime.now(),
                'created_by': dentist_user
            },
            {
                'mrn': 'MRN002',
                'first_name': 'Bob',
                'last_name': 'Williams',
                'date_of_birth': date(1992, 7, 22),
                'gender': 'M',
                'email': 'bob@example.com',
                'phone': '+1234567891',
                'organization': branch_a,
                'consent_given': True,
                'consent_date': datetime.now(),
                'created_by': dentist_user
            },
            {
                'mrn': 'MRN003',
                'first_name': 'Carol',
                'last_name': 'Davis',
                'date_of_birth': date(1978, 11, 5),
                'gender': 'F',
                'email': 'carol@example.com',
                'organization': hq,
                'consent_given': True,
                'consent_date': datetime.now(),
                'created_by': admin_user
            },
        ]
        
        for patient_data in patients_data:
            patient, created = Patient.objects.get_or_create(
                mrn=patient_data['mrn'],
                defaults=patient_data
            )
            if created:
                self.stdout.write(self.style.SUCCESS(f'Created patient: {patient}'))
        
        # Create sample cases
        cases_data = [
            {
                'patient': Patient.objects.get(mrn='MRN001'),
                'category': Category.objects.get(slug='general-dentistry'),
                'chief_complaint': 'Severe tooth pain in upper right molar',
                'clinical_findings': 'Deep cavity visible on tooth #3, positive percussion test',
                'diagnosis': 'Irreversible pulpitis tooth #3',
                'treatment_plan': 'Root canal therapy followed by crown placement',
                'prognosis': 'Good with proper treatment',
                'status': 'ACTIVE',
                'priority': 'HIGH',
                'organization': branch_a,
                'created_by': dentist_user,
                'assigned_to': dentist_user,
            },
            {
                'patient': Patient.objects.get(mrn='MRN002'),
                'category': Category.objects.get(slug='orthodontics'),
                'chief_complaint': 'Crooked teeth affecting smile',
                'clinical_findings': 'Class II malocclusion with crowding in lower anterior',
                'diagnosis': 'Malocclusion Class II Division 1',
                'treatment_plan': 'Traditional braces treatment for 18-24 months',
                'prognosis': 'Excellent with patient compliance',
                'status': 'IN_REVIEW',
                'priority': 'MEDIUM',
                'organization': branch_a,
                'created_by': dentist_user,
                'is_shared': True,
            },
            {
                'patient': Patient.objects.get(mrn='MRN003'),
                'category': Category.objects.get(slug='periodontics'),
                'chief_complaint': 'Bleeding gums when brushing',
                'clinical_findings': 'Moderate gingivitis with 4-5mm pockets',
                'diagnosis': 'Chronic periodontitis',
                'treatment_plan': 'Scaling and root planing, improved oral hygiene',
                'prognosis': 'Good with maintenance',
                'status': 'ACTIVE',
                'priority': 'MEDIUM',
                'organization': hq,
                'created_by': admin_user,
            },
        ]
        
        for case_data in cases_data:
            # Check if similar case exists
            existing_case = Case.objects.filter(
                patient=case_data['patient'],
                chief_complaint=case_data['chief_complaint']
            ).first()
            
            if not existing_case:
                case = Case.objects.create(**case_data)
                self.stdout.write(self.style.SUCCESS(f'Created case: {case}'))
                
                # Add sample comments
                Comment.objects.create(
                    case=case,
                    author=case_data['created_by'],
                    content='Initial examination completed. Patient advised of treatment options.',
                    visibility='TEAM'
                )
                
                if case_data.get('is_shared'):
                    case.share_with_branches.add(hq)
                    Comment.objects.create(
                        case=case,
                        author=admin_user,
                        content='Interesting case. Consider using new orthodontic technique discussed in last meeting.',
                        visibility='SHARED'
                    )
        
        self.stdout.write(self.style.SUCCESS('Sample data created successfully!'))