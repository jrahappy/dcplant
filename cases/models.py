from django.db import models
from django.contrib.auth.models import User
from django.core.validators import RegexValidator
from accounts.models import Organization
from datetime import datetime
import uuid
import os
import re


class Patient(models.Model):
    GENDER_CHOICES = [
        ("M", "Male"),
        ("F", "Female"),
        ("O", "Other"),
    ]

    mrn = models.CharField(max_length=50, unique=True, help_text="Chart Number")
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    date_of_birth = models.DateField()
    gender = models.CharField(max_length=1, choices=GENDER_CHOICES)
    email = models.EmailField(blank=True)
    phone = models.CharField(
        max_length=20, blank=True, validators=[RegexValidator(r"^\+?1?\d{9,15}$")]
    )
    address = models.TextField(blank=True)
    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, related_name="patients"
    )
    medical_history = models.JSONField(default=dict, blank=True)
    allergies = models.TextField(blank=True)
    insurance_info = models.JSONField(default=dict, blank=True)
    consent_given = models.BooleanField(default=False)
    consent_date = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, related_name="created_patients"
    )

    class Meta:
        ordering = ["last_name", "first_name"]
        indexes = [
            models.Index(fields=["mrn"]),
            models.Index(fields=["organization", "last_name"]),
        ]

    def __str__(self):
        return f"{self.last_name}, {self.first_name} (CN: {self.mrn})"

    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}"

    @property
    def age(self):
        from datetime import date

        today = date.today()
        return (
            today.year
            - self.date_of_birth.year
            - (
                (today.month, today.day)
                < (self.date_of_birth.month, self.date_of_birth.day)
            )
        )


class Category(models.Model):
    name = models.CharField(max_length=100)
    slug = models.SlugField(unique=True)
    description = models.TextField(blank=True)
    parent = models.ForeignKey(
        "self", on_delete=models.CASCADE, null=True, blank=True, related_name="children"
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name_plural = "Categories"
        ordering = ["name"]

    def __str__(self):
        if self.parent:
            return f"{self.parent.name} > {self.name}"
        return self.name


class Case(models.Model):
    STATUS_CHOICES = [
        ("DRAFT", "Draft"),
        ("ACTIVE", "Active"),
        ("IN_REVIEW", "In Review"),
        ("COMPLETED", "Completed"),
        ("ARCHIVED", "Archived"),
    ]

    PRIORITY_CHOICES = [
        ("LOW", "Low"),
        ("MEDIUM", "Medium"),
        ("HIGH", "High"),
        ("URGENT", "Urgent"),
    ]

    case_number = models.CharField(max_length=50, unique=True, editable=False)
    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name="cases")
    category = models.ForeignKey(
        Category,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="cases",
    )
    title = models.CharField(max_length=255)
    chief_complaint = models.TextField()
    clinical_findings = models.TextField(null=True, blank=True)
    diagnosis = models.TextField(null=True, blank=True)
    treatment_plan = models.TextField(null=True, blank=True)
    prognosis = models.TextField(blank=True)

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="DRAFT")
    priority = models.CharField(
        max_length=10, choices=PRIORITY_CHOICES, default="MEDIUM"
    )

    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, related_name="cases"
    )
    created_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, related_name="created_cases"
    )
    assigned_to = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="assigned_cases",
    )

    tags = models.JSONField(default=list, blank=True)
    metadata = models.JSONField(default=dict, blank=True)

    is_shared = models.BooleanField(default=False)
    share_with_branches = models.ManyToManyField(
        Organization, blank=True, related_name="shared_cases"
    )
    is_deidentified = models.BooleanField(default=False)
    is_secret = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["case_number"]),
            models.Index(fields=["status", "priority"]),
            models.Index(fields=["organization", "created_at"]),
        ]

    def save(self, *args, **kwargs):
        if not self.case_number:
            self.case_number = self.generate_case_number()
        super().save(*args, **kwargs)

    def generate_case_number(self):

        prefix = self.organization.name[:3].upper()
        timestamp = datetime.now().strftime("%Y%m%d")
        random_suffix = str(uuid.uuid4())[:6].upper()
        return f"{prefix}-{timestamp}-{random_suffix}"

    def __str__(self):
        return f"Case {self.case_number} - {self.patient.full_name}"


class CaseOpinion(models.Model):
    STATUS_CHOICES = [
        ("DRAFT", "Draft"),
        ("PUBLISHED", "Published"),
    ]
    case = models.ForeignKey(Case, on_delete=models.CASCADE, related_name="opinions")
    author = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, related_name="case_opinions"
    )
    content = models.TextField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="DRAFT")
    is_deleted = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Opinion on {self.case.case_number} by {self.author.username}"


def case_image_upload_path(instance, filename):
    """
    Custom upload path function that organizes files by case ID.
    Files will be stored in: cases/case_<case_id>/<filename>
    """
    # Get the case ID - instance is a CaseImageItem which has caseimage.case
    if hasattr(instance, "caseimage") and instance.caseimage:
        case_id = instance.caseimage.case.id if instance.caseimage.case else "unknown"
    else:
        case_id = "unknown"

    # Preserve the original filename
    return f"cases/case_{case_id}/{filename}"


class CaseImageManager(models.Manager):
    def get_dicom_series_sorted(self, case):
        """Get DICOM images for a case sorted by order field in ascending order"""
        return self.filter(case=case, is_dicom=True).order_by("order")


class CaseImage(models.Model):
    """Represents an upload transaction/batch - a group of related files"""

    case = models.ForeignKey(Case, on_delete=models.CASCADE, related_name="images")
    title = models.CharField(max_length=200, help_text="Name of this upload batch")
    description = models.TextField(
        blank=True, help_text="Description of this upload batch"
    )

    # Upload transaction metadata
    uploaded_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, related_name="uploaded_images"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = CaseImageManager()

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.title} - {self.case.case_number}"

    @property
    def item_count(self):
        """Get the count of CaseImageItems in this CaseImage"""
        return self.items.count()

    @property
    def first_item(self):
        """Get the first CaseImageItem for preview purposes"""
        return self.items.first()


class CaseImageItem(models.Model):
    """Individual file within a CaseImage upload batch"""

    IMAGE_TYPE_CHOICES = [
        ("PHOTO", "Photograph"),
        ("PANO", "Panoramic"),
        ("CBCT", "CBCT"),
        ("IOXray", "Intraoral X-Ray"),
        ("3DScan", "3D Scan"),
        ("PDF", "PDF Document"),
        ("ZIP", "ZIP Archive"),
        ("OTHER", "Other"),
    ]

    caseimage = models.ForeignKey(
        CaseImage, on_delete=models.CASCADE, related_name="items"
    )
    image = models.FileField(upload_to=case_image_upload_path)

    # File-specific metadata
    image_type = models.CharField(
        max_length=20, choices=IMAGE_TYPE_CHOICES, default="PHOTO"
    )
    is_dicom = models.BooleanField(default=False)
    is_primary = models.BooleanField(default=False)
    metadata = models.JSONField(default=dict, blank=True)
    order = models.IntegerField(default=0, help_text="Sort order within the batch")

    class Meta:
        ordering = ["order"]

    @property
    def filename(self):
        """Get the filename without path"""
        return os.path.basename(self.image.name)

    @property
    def dicom_sort_info(self):
        """Debug property to show sorting information for DICOM files"""
        return f"{self.filename} -> Sort Order: {self.filename_numeric}"

    @property
    def filename_numeric(self):
        """Extract numeric part from filename for sorting DICOM series in ascending order"""

        filename = self.filename

        # Common DICOM filename patterns:
        # - IMG0001.dcm, IMG0002.dcm
        # - slice_001.dcm, slice_002.dcm
        # - 1.dcm, 2.dcm, 10.dcm
        # - IM-0001-0001.dcm
        # - CT.1.2.840.113619.2.55.3.604688119.969.1369219458.364.4.dcm (instance number at end)

        # Remove file extension
        name_without_ext = filename.rsplit(".", 1)[0]

        # Try to find all numbers in the filename
        numbers = re.findall(r"\d+", name_without_ext)

        if numbers:
            # For DICOM files, typically the most relevant number for ordering is:
            # 1. The last significant number before extension
            # 2. Or the largest standalone number

            # If filename ends with a number, use that (most common pattern)
            if re.search(r"\d+$", name_without_ext):
                last_num = re.findall(r"\d+$", name_without_ext)[0]
                return int(last_num)

            # Otherwise, look for the most significant number (usually the largest)
            # This handles cases like "IM-0001-0042.dcm" where 42 is the slice
            if len(numbers) > 1:
                # Get the last number which is often the slice/instance number
                return int(numbers[-1])
            else:
                return int(numbers[0])

        # If no numbers found, return 0 to sort at beginning
        return 0

    def save(self, *args, **kwargs):
        # Set order field based on DICOM Instance Number or filename for DICOM files
        if self.is_dicom and not self.pk:  # Only on creation
            # Try to extract Instance Number from DICOM metadata
            if self.metadata and isinstance(self.metadata, dict):
                instance_number = self.metadata.get("instance_number")
                if instance_number:
                    self.order = int(instance_number)
                else:
                    self.order = self.filename_numeric
            else:
                self.order = self.filename_numeric

        super().save(*args, **kwargs)


class Comment(models.Model):
    VISIBILITY_CHOICES = [
        ("PRIVATE", "Private - Only Me"),
        ("TEAM", "Team - My Organization"),
        ("SHARED", "Shared - All Allowed Organizations"),
    ]

    case = models.ForeignKey(Case, on_delete=models.CASCADE, related_name="comments")
    author = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="case_comments"
    )
    content = models.TextField()
    visibility = models.CharField(
        max_length=10, choices=VISIBILITY_CHOICES, default="TEAM"
    )

    parent = models.ForeignKey(
        "self", on_delete=models.CASCADE, null=True, blank=True, related_name="replies"
    )

    mentions = models.ManyToManyField(
        User, blank=True, related_name="mentioned_in_comments"
    )

    attachments = models.JSONField(default=list, blank=True)

    is_edited = models.BooleanField(default=False)
    edited_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["created_at"]

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
        ("CREATED", "Case Created"),
        ("UPDATED", "Case Updated"),
        ("STATUS_CHANGED", "Status Changed"),
        ("ASSIGNED", "Case Assigned"),
        ("COMMENTED", "Comment Added"),
        ("IMAGE_ADDED", "Image Added"),
        ("IMAGE_REMOVED", "Image Removed"),
        ("SHARED", "Case Shared"),
        ("VIEWED", "Case Viewed"),
        ("EXPORTED", "Case Exported"),
    ]

    case = models.ForeignKey(Case, on_delete=models.CASCADE, related_name="activities")
    user = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, related_name="case_activities"
    )
    activity_type = models.CharField(max_length=20, choices=ACTIVITY_TYPES)
    description = models.TextField()
    metadata = models.JSONField(default=dict, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name_plural = "Case Activities"

    def __str__(self):
        return f"{self.activity_type} - {self.case.case_number} by {self.user.username if self.user else 'System'}"
