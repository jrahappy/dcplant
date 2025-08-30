from django import forms
from django.contrib.auth.models import User
from .models import Case, Patient, Comment, CaseImage, CaseImageItem, Category


class MultipleFileInput(forms.ClearableFileInput):
    allow_multiple_selected = True


class MultipleFileField(forms.FileField):
    def __init__(self, *args, **kwargs):
        kwargs.setdefault(
            "widget",
            MultipleFileInput(
                attrs={
                    "class": "form-control",
                    "accept": "image/*,.dcm,.dicom,application/dicom,.zip,application/zip,.pdf,application/pdf",
                    "multiple": True,
                }
            ),
        )
        super().__init__(*args, **kwargs)

    def clean(self, data, initial=None):
        single_file_clean = super().clean
        if isinstance(data, (list, tuple)):
            result = [single_file_clean(d, initial) for d in data]
        else:
            result = [single_file_clean(data, initial)]
        return result


class PatientForm(forms.ModelForm):
    """Form for creating and updating patients"""

    date_of_birth = forms.DateField(
        widget=forms.DateInput(attrs={"type": "date", "class": "form-control"}),
        required=True,
    )
    consent_given = forms.BooleanField(
        required=False, widget=forms.CheckboxInput(attrs={"class": "form-check-input"})
    )

    class Meta:
        model = Patient
        fields = [
            "mrn",
            "first_name",
            "last_name",
            "date_of_birth",
            "gender",
            "email",
            "phone",
            "address",
            "medical_history",
            "allergies",
            "insurance_info",
            "consent_given",
        ]
        widgets = {
            "mrn": forms.TextInput(
                attrs={"class": "form-control", "placeholder": "MRN-XXXX"}
            ),
            "first_name": forms.TextInput(attrs={"class": "form-control"}),
            "last_name": forms.TextInput(attrs={"class": "form-control"}),
            "gender": forms.Select(attrs={"class": "form-select"}),
            "email": forms.EmailInput(attrs={"class": "form-control"}),
            "phone": forms.TextInput(
                attrs={"class": "form-control", "placeholder": "+1234567890"}
            ),
            "address": forms.Textarea(attrs={"class": "form-control", "rows": 3}),
            "medical_history": forms.Textarea(
                attrs={"class": "form-control", "rows": 4}
            ),
            "allergies": forms.Textarea(attrs={"class": "form-control", "rows": 2}),
            "insurance_info": forms.Textarea(
                attrs={"class": "form-control", "rows": 3}
            ),
        }


class CaseForm(forms.ModelForm):
    """Form for creating and updating cases"""

    class Meta:
        model = Case
        fields = [
            "patient",
            "category",
            "chief_complaint",
            "clinical_findings",
            "diagnosis",
            "treatment_plan",
            "prognosis",
            "status",
            "priority",
            "assigned_to",
            "tags",
            "is_shared",
            "share_with_branches",
            "is_deidentified",
        ]
        widgets = {
            "patient": forms.Select(attrs={"class": "form-select"}),
            "category": forms.Select(attrs={"class": "form-select"}),
            "chief_complaint": forms.Textarea(
                attrs={"class": "form-control", "rows": 3}
            ),
            "clinical_findings": forms.Textarea(
                attrs={"class": "form-control", "rows": 4}
            ),
            "diagnosis": forms.Textarea(attrs={"class": "form-control", "rows": 3}),
            "treatment_plan": forms.Textarea(
                attrs={"class": "form-control", "rows": 4}
            ),
            "prognosis": forms.Textarea(attrs={"class": "form-control", "rows": 3}),
            "status": forms.Select(attrs={"class": "form-select"}),
            "priority": forms.Select(attrs={"class": "form-select"}),
            "assigned_to": forms.Select(attrs={"class": "form-select"}),
            "is_shared": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "share_with_branches": forms.SelectMultiple(
                attrs={"class": "form-select", "size": 3}
            ),
            "is_deidentified": forms.CheckboxInput(attrs={"class": "form-check-input"}),
        }

    def __init__(self, *args, **kwargs):
        user = kwargs.pop("user", None)
        super().__init__(*args, **kwargs)

        if user and hasattr(user, "profile"):
            # Filter patients by organization
            self.fields["patient"].queryset = Patient.objects.filter(
                organization=user.profile.organization
            )
            # Filter assigned users to show only dentists in the organization
            dentist_users = User.objects.filter(
                profile__organization=user.profile.organization, profile__role="DENTIST"
            ).select_related("profile")

            self.fields["assigned_to"].queryset = dentist_users
            # Add empty label for assigned_to
            self.fields["assigned_to"].empty_label = "Select a Dentist"

            # Format the display of dentists to show their full name with title
            self.fields["assigned_to"].label_from_instance = (
                lambda obj: f"Dr. {obj.get_full_name() or obj.username}"
            )

            # Filter share branches excluding current org
            from accounts.models import Organization

            self.fields["share_with_branches"].queryset = Organization.objects.exclude(
                id=user.profile.organization.id
            )


class CommentForm(forms.ModelForm):
    """Form for adding comments to cases"""

    class Meta:
        model = Comment
        fields = ["content", "visibility"]
        widgets = {
            "content": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "rows": 3,
                    "placeholder": "Add your comment here...",
                }
            ),
            "visibility": forms.Select(attrs={"class": "form-select"}),
        }


class CaseImageForm(forms.ModelForm):
    """Form for creating/editing CaseImage groups"""

    class Meta:
        model = CaseImage
        fields = [
            "title",
            "description",
        ]
        widgets = {
            "title": forms.TextInput(attrs={"class": "form-control"}),
            "description": forms.Textarea(attrs={"class": "form-control", "rows": 2}),
        }


class CaseImageItemForm(forms.ModelForm):
    """Form for individual image items within a CaseImage"""
    
    class Meta:
        from .models import CaseImageItem
        model = CaseImageItem
        fields = [
            "image",
            "is_dicom",
            "metadata",
            "order",
        ]
        widgets = {
            "image": forms.FileInput(
                attrs={
                    "class": "form-control",
                    "accept": "image/*,.dcm,.dicom,application/dicom,.zip,application/zip,.pdf,application/pdf",
                }
            ),
            "is_dicom": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "order": forms.NumberInput(attrs={"class": "form-control"}),
        }


class MultipleImageUploadForm(forms.Form):
    """Form for uploading multiple images at once"""

    images = MultipleFileField(
        required=True, help_text="Select multiple files at once using Ctrl/Cmd + Click"
    )
    image_type = forms.ChoiceField(
        choices=CaseImageItem.IMAGE_TYPE_CHOICES,
        widget=forms.Select(attrs={"class": "form-select"}),
        initial="PHOTO",
        help_text="Default type for images (will be auto-detected for DICOM/PDF/ZIP)",
    )
    title_prefix = forms.CharField(
        max_length=150,
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
                "placeholder": 'e.g., "Pre-treatment X-ray"',
            }
        ),
        required=False,
        help_text="Title prefix for all images (number will be added automatically)",
    )
    description = forms.CharField(
        widget=forms.Textarea(
            attrs={
                "class": "form-control",
                "rows": 2,
                "placeholder": "Optional description for all images",
            }
        ),
        required=False,
    )


class CaseFilterForm(forms.Form):
    """Form for filtering cases in list view"""

    search = forms.CharField(
        required=False,
        widget=forms.TextInput(
            attrs={"class": "form-control", "placeholder": "Search cases..."}
        ),
    )
    status = forms.ChoiceField(
        required=False,
        choices=[("", "All Status")] + Case.STATUS_CHOICES,
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    priority = forms.ChoiceField(
        required=False,
        choices=[("", "All Priority")] + Case.PRIORITY_CHOICES,
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    category = forms.ModelChoiceField(
        required=False,
        queryset=Category.objects.filter(is_active=True),
        empty_label="All Categories",
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    assigned_to = forms.ModelChoiceField(
        required=False,
        queryset=User.objects.all(),
        empty_label="All Dentists",
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    date_from = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={"type": "date", "class": "form-control"}),
    )
    date_to = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={"type": "date", "class": "form-control"}),
    )

    def __init__(self, *args, **kwargs):
        user = kwargs.pop("user", None)
        super().__init__(*args, **kwargs)

        if user and hasattr(user, "profile"):
            # Filter assigned_to to show only dentists in the organization
            dentist_users = User.objects.filter(
                profile__organization=user.profile.organization, profile__role="DENTIST"
            ).select_related("profile")

            self.fields["assigned_to"].queryset = dentist_users
            # Format the display of dentists
            self.fields["assigned_to"].label_from_instance = (
                lambda obj: f"Dr. {obj.get_full_name() or obj.username}"
            )


class CategoryForm(forms.ModelForm):
    """Form for creating and updating categories"""

    class Meta:
        model = Category
        fields = ["name", "slug", "description", "parent", "is_active"]
        widgets = {
            "name": forms.TextInput(attrs={"class": "form-control"}),
            "slug": forms.TextInput(attrs={"class": "form-control"}),
            "description": forms.Textarea(attrs={"class": "form-control", "rows": 3}),
            "parent": forms.Select(attrs={"class": "form-select"}),
            "is_active": forms.CheckboxInput(attrs={"class": "form-check-input"}),
        }
