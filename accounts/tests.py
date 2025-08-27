from django.test import TestCase
from django.contrib.auth.models import User
from .models import Organization, UserProfile


class OrganizationModelTest(TestCase):
    def test_create_organization(self):
        org = Organization.objects.create(
            name="Main HQ",
            org_type="HQ",
            email="hq@dcplant.com"
        )
        self.assertEqual(str(org), "Main HQ (Headquarters)")
        self.assertTrue(org.is_active)


class UserProfileModelTest(TestCase):
    def setUp(self):
        self.org = Organization.objects.create(
            name="Branch A",
            org_type="BRANCH"
        )
        self.user = User.objects.create_user(
            username="dentist1",
            email="dentist@branch.com",
            first_name="John",
            last_name="Doe"
        )
        
    def test_create_user_profile(self):
        profile = UserProfile.objects.create(
            user=self.user,
            organization=self.org,
            role="DENTIST",
            professional_type="DDS"
        )
        self.assertEqual(str(profile), "John Doe - DENTIST at Branch A")
        self.assertFalse(profile.is_hq_admin)
        self.assertFalse(profile.is_branch_admin)
        self.assertTrue(profile.can_approve_plans)
