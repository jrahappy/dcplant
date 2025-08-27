"""
Test script to demonstrate the new folder structure for CaseImage uploads
"""
import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

from cases.models import Case, Patient, CaseImage, Organization
from django.contrib.auth.models import User
from django.core.files.base import ContentFile
from datetime import date

# Get or create test data
org = Organization.objects.first()
if not org:
    org = Organization.objects.create(
        name="Test Org",
        organization_type="CLINIC"
    )

user = User.objects.first()
if not user:
    user = User.objects.create_user('testuser', 'test@example.com', 'password')

# Create a patient
patient, created = Patient.objects.get_or_create(
    mrn="TEST001",
    defaults={
        'first_name': 'Test',
        'last_name': 'Patient',
        'date_of_birth': date(1990, 1, 1),
        'gender': 'M',
        'organization': org,
        'created_by': user
    }
)

# Create a case
case = Case.objects.create(
    patient=patient,
    chief_complaint="Test for folder structure",
    clinical_findings="Testing new upload path",
    diagnosis="Test diagnosis",
    treatment_plan="Test treatment",
    organization=org,
    created_by=user
)

print(f"Created Case ID: {case.id}")
print(f"Case Number: {case.case_number}")

# Create a test image
test_image = CaseImage(
    case=case,
    image_type="PHOTO",
    title="Test Image",
    description="Testing folder structure by case ID",
    uploaded_by=user
)

# Create a dummy file
dummy_content = b"This is a test image file content"
test_image.image.save('test_image.jpg', ContentFile(dummy_content))

print(f"\nImage saved to: {test_image.image.name}")
print(f"Full path: {test_image.image.path}")
print(f"Expected path: cases/case_{case.id}/test_image.jpg")

# Verify the folder structure
if f"case_{case.id}" in test_image.image.name:
    print("\n✓ SUCCESS: Image saved in case-specific folder!")
else:
    print("\n✗ ERROR: Image not saved in case-specific folder")

# Clean up - optional
# test_image.delete()
# case.delete()
# if created:
#     patient.delete()