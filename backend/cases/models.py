from django.db import models
from django.contrib.auth.models import User
from django.core.validators import RegexValidator
from accounts.models import Organization
import uuid


class Patient(models.Model):
    GENDER_CHOICES = [
        ('M', 'Male'),
        ('F', 'Female'),
        ('O', 'Other'),
    ]
    
    mrn = models.CharField(
        max_length=50, 
        unique=True,
        help_text="Medical Record Number"
    )
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    date_of_birth = models.DateField()
    gender = models.CharField(max_length=1, choices=GENDER_CHOICES)
    email = models.EmailField(blank=True)
    phone = models.CharField(
        max_length=20,
        blank=True,
        validators=[RegexValidator(r'^\+?1?\d{9,15}$')]
    )
    address = models.TextField(blank=True)
    organization = models.ForeignKey(
        Organization, 
        on_delete=models.CASCADE,
        related_name='patients'
    )
    medical_history = models.JSONField(default=dict, blank=True)
    allergies = models.TextField(blank=True)
    insurance_info = models.JSONField(default=dict, blank=True)
    consent_given = models.BooleanField(default=False)
    consent_date = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='created_patients'
    )
    
    class Meta:
        ordering = ['last_name', 'first_name']
        indexes = [
            models.Index(fields=['mrn']),
            models.Index(fields=['organization', 'last_name']),
        ]
    
    def __str__(self):
        return f"{self.last_name}, {self.first_name} (MRN: {self.mrn})"
    
    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}"
    
    @property
    def age(self):
        from datetime import date
        today = date.today()
        return today.year - self.date_of_birth.year - (
            (today.month, today.day) < (self.date_of_birth.month, self.date_of_birth.day)
        )


class Category(models.Model):
    name = models.CharField(max_length=100)
    slug = models.SlugField(unique=True)
    description = models.TextField(blank=True)
    parent = models.ForeignKey(
        'self',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='children'
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name_plural = "Categories"
        ordering = ['name']
    
    def __str__(self):
        if self.parent:
            return f"{self.parent.name} > {self.name}"
        return self.name


class Case(models.Model):
    STATUS_CHOICES = [
        ('DRAFT', 'Draft'),
        ('ACTIVE', 'Active'),
        ('IN_REVIEW', 'In Review'),
        ('COMPLETED', 'Completed'),
        ('ARCHIVED', 'Archived'),
    ]
    
    PRIORITY_CHOICES = [
        ('LOW', 'Low'),
        ('MEDIUM', 'Medium'),
        ('HIGH', 'High'),
        ('URGENT', 'Urgent'),
    ]
    
    case_number = models.CharField(
        max_length=50,
        unique=True,
        editable=False
    )
    patient = models.ForeignKey(
        Patient,
        on_delete=models.CASCADE,
        related_name='cases'
    )
    category = models.ForeignKey(
        Category,
        on_delete=models.SET_NULL,
        null=True,
        related_name='cases'
    )
    chief_complaint = models.TextField()
    clinical_findings = models.TextField()
    diagnosis = models.TextField()
    treatment_plan = models.TextField()
    prognosis = models.TextField(blank=True)
    
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='DRAFT'
    )
    priority = models.CharField(
        max_length=10,
        choices=PRIORITY_CHOICES,
        default='MEDIUM'
    )
    
    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name='cases'
    )
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='created_cases'
    )
    assigned_to = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='assigned_cases'
    )
    
    tags = models.JSONField(default=list, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    
    is_shared = models.BooleanField(default=False)
    share_with_branches = models.ManyToManyField(
        Organization,
        blank=True,
        related_name='shared_cases'
    )
    is_deidentified = models.BooleanField(default=False)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['case_number']),
            models.Index(fields=['status', 'priority']),
            models.Index(fields=['organization', 'created_at']),
        ]
    
    def save(self, *args, **kwargs):
        if not self.case_number:
            self.case_number = self.generate_case_number()
        super().save(*args, **kwargs)
    
    def generate_case_number(self):
        from datetime import datetime
        prefix = self.organization.name[:3].upper()
        timestamp = datetime.now().strftime('%Y%m%d')
        random_suffix = str(uuid.uuid4())[:6].upper()
        return f"{prefix}-{timestamp}-{random_suffix}"
    
    def __str__(self):
        return f"Case {self.case_number} - {self.patient.full_name}"


class CaseImage(models.Model):
    IMAGE_TYPE_CHOICES = [
        ('PHOTO', 'Photograph'),
        ('XRAY', 'X-Ray'),
        ('CBCT', 'CBCT Scan'),
        ('MRI', 'MRI'),
        ('CT', 'CT Scan'),
        ('DICOM', 'DICOM'),
        ('DIAGRAM', 'Diagram'),
        ('OTHER', 'Other'),
    ]
    
    case = models.ForeignKey(
        Case,
        on_delete=models.CASCADE,
        related_name='images'
    )
    image = models.FileField(
        upload_to='cases/images/%Y/%m/%d/'
    )
    image_type = models.CharField(
        max_length=20,
        choices=IMAGE_TYPE_CHOICES,
        default='PHOTO'
    )
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    taken_date = models.DateField(null=True, blank=True)
    
    metadata = models.JSONField(default=dict, blank=True)
    is_primary = models.BooleanField(default=False)
    is_deidentified = models.BooleanField(default=False)
    is_dicom = models.BooleanField(default=False)
    
    uploaded_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='uploaded_images'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-is_primary', '-created_at']
    
    def __str__(self):
        return f"{self.title} - {self.case.case_number}"
    
    def save(self, *args, **kwargs):
        # Ensure only one primary image per case
        if self.is_primary:
            CaseImage.objects.filter(
                case=self.case,
                is_primary=True
            ).exclude(pk=self.pk).update(is_primary=False)
        super().save(*args, **kwargs)


class Comment(models.Model):
    VISIBILITY_CHOICES = [
        ('PRIVATE', 'Private - Only Me'),
        ('TEAM', 'Team - My Organization'),
        ('SHARED', 'Shared - All Allowed Organizations'),
    ]
    
    case = models.ForeignKey(
        Case,
        on_delete=models.CASCADE,
        related_name='comments'
    )
    author = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='case_comments'
    )
    content = models.TextField()
    visibility = models.CharField(
        max_length=10,
        choices=VISIBILITY_CHOICES,
        default='TEAM'
    )
    
    parent = models.ForeignKey(
        'self',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='replies'
    )
    
    mentions = models.ManyToManyField(
        User,
        blank=True,
        related_name='mentioned_in_comments'
    )
    
    attachments = models.JSONField(default=list, blank=True)
    
    is_edited = models.BooleanField(default=False)
    edited_at = models.DateTimeField(null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['created_at']
    
    def __str__(self):
        return f"Comment by {self.author.username} on {self.case.case_number}"
    
    def save(self, *args, **kwargs):
        if self.pk:  # If updating existing comment
            old_comment = Comment.objects.get(pk=self.pk)
            if old_comment.content != self.content:
                self.is_edited = True
                from django.utils import timezone
                self.edited_at = timezone.now()
        super().save(*args, **kwargs)


class CaseActivity(models.Model):
    """Track all activities on a case for audit trail"""
    ACTIVITY_TYPES = [
        ('CREATED', 'Case Created'),
        ('UPDATED', 'Case Updated'),
        ('STATUS_CHANGED', 'Status Changed'),
        ('ASSIGNED', 'Case Assigned'),
        ('COMMENTED', 'Comment Added'),
        ('IMAGE_ADDED', 'Image Added'),
        ('IMAGE_REMOVED', 'Image Removed'),
        ('SHARED', 'Case Shared'),
        ('VIEWED', 'Case Viewed'),
        ('EXPORTED', 'Case Exported'),
    ]
    
    case = models.ForeignKey(
        Case,
        on_delete=models.CASCADE,
        related_name='activities'
    )
    user = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='case_activities'
    )
    activity_type = models.CharField(
        max_length=20,
        choices=ACTIVITY_TYPES
    )
    description = models.TextField()
    metadata = models.JSONField(default=dict, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-created_at']
        verbose_name_plural = "Case Activities"
    
    def __str__(self):
        return f"{self.activity_type} - {self.case.case_number} by {self.user.username if self.user else 'System'}"
