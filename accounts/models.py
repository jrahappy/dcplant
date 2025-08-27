from django.db import models
from django.contrib.auth.models import User
from django.core.validators import RegexValidator

class Organization(models.Model):
    ORG_TYPE_CHOICES = [
        ('HQ', 'Headquarters'),
        ('BRANCH', 'Branch'),
    ]
    
    name = models.CharField(max_length=100)
    org_type = models.CharField(max_length=10, choices=ORG_TYPE_CHOICES)
    address = models.TextField(blank=True)
    phone = models.CharField(
        max_length=20, 
        blank=True,
        validators=[RegexValidator(r'^\+?1?\d{9,15}$')]
    )
    email = models.EmailField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True)
    
    class Meta:
        ordering = ['name']
        
    def __str__(self):
        return f"{self.name} ({self.get_org_type_display()})"


class UserProfile(models.Model):
    ROLE_CHOICES = [
        ('HQ_ADMIN', 'HQ Administrator'),
        ('BRANCH_ADMIN', 'Branch Administrator'),
        ('DENTIST', 'Dentist'),
        ('ASSISTANT', 'Dental Assistant'),
        ('FRONT_DESK', 'Front Desk'),
        ('READ_ONLY', 'Read Only'),
        ('EXTERNAL_GUEST', 'External Guest'),
    ]
    
    PROFESSIONAL_TYPE_CHOICES = [
        ('DDS', 'Doctor of Dental Surgery'),
        ('DMD', 'Doctor of Medicine in Dentistry'),
        ('RDH', 'Registered Dental Hygienist'),
        ('RDA', 'Registered Dental Assistant'),
        ('ADMIN', 'Administrative'),
        ('OTHER', 'Other'),
    ]
    
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name='users')
    role = models.CharField(max_length=20, choices=ROLE_CHOICES)
    professional_type = models.CharField(max_length=20, choices=PROFESSIONAL_TYPE_CHOICES, default='OTHER')
    license_number = models.CharField(max_length=50, blank=True)
    phone = models.CharField(
        max_length=20, 
        blank=True,
        validators=[RegexValidator(r'^\+?1?\d{9,15}$')]
    )
    avatar = models.ImageField(upload_to='avatars/', blank=True, null=True)
    bio = models.TextField(blank=True)
    specialty = models.CharField(max_length=50, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['user__last_name', 'user__first_name']
        
    def __str__(self):
        return f"{self.user.get_full_name()} - {self.role} at {self.organization.name}"
    
    @property
    def is_hq_admin(self):
        return self.role == 'HQ_ADMIN'
    
    @property
    def is_branch_admin(self):
        return self.role == 'BRANCH_ADMIN'
    
    @property
    def is_admin(self):
        return self.role in ['HQ_ADMIN', 'BRANCH_ADMIN']
    
    @property
    def can_approve_plans(self):
        return self.role in ['HQ_ADMIN', 'BRANCH_ADMIN', 'DENTIST']
