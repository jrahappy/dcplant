from django.contrib import admin
from django.utils.html import format_html
from .models import Patient, Category, Case, CaseImage, Comment, CaseActivity


class CaseImageInline(admin.TabularInline):
    model = CaseImage
    extra = 0
    fields = ("image", "image_type", "title", "is_primary", "is_deidentified")
    readonly_fields = ("uploaded_by", "created_at")


class CommentInline(admin.TabularInline):
    model = Comment
    extra = 0
    fields = ("author", "content", "visibility", "created_at")
    readonly_fields = ("created_at",)


class CaseActivityInline(admin.TabularInline):
    model = CaseActivity
    extra = 0
    fields = ("activity_type", "user", "description", "created_at")
    readonly_fields = ("activity_type", "user", "description", "created_at")
    can_delete = False


@admin.register(Patient)
class PatientAdmin(admin.ModelAdmin):
    list_display = (
        "mrn",
        "full_name",
        "age",
        "gender",
        "organization",
        "consent_given",
        "created_at",
    )
    list_filter = ("gender", "consent_given", "organization", "created_at")
    search_fields = ("mrn", "first_name", "last_name", "email", "phone")
    readonly_fields = ("created_at", "updated_at", "created_by", "age")
    fieldsets = (
        (
            "Basic Information",
            {
                "fields": (
                    "mrn",
                    "first_name",
                    "last_name",
                    "date_of_birth",
                    "gender",
                    "age",
                )
            },
        ),
        ("Contact Information", {"fields": ("email", "phone", "address")}),
        (
            "Medical Information",
            {"fields": ("medical_history", "allergies", "insurance_info")},
        ),
        ("Consent", {"fields": ("consent_given", "consent_date")}),
        ("Organization", {"fields": ("organization", "created_by")}),
        (
            "Timestamps",
            {"fields": ("created_at", "updated_at"), "classes": ("collapse",)},
        ),
    )

    def save_model(self, request, obj, form, change):
        if not obj.created_by:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)

    def full_name(self, obj):
        return obj.full_name

    full_name.short_description = "Name"


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "parent", "is_active", "created_at")
    list_filter = ("is_active", "parent", "created_at")
    search_fields = ("name", "description")
    prepopulated_fields = {"slug": ("name",)}
    ordering = ("name",)


@admin.register(Case)
class CaseAdmin(admin.ModelAdmin):
    list_display = (
        "case_number",
        "patient_name",
        "category",
        "status_badge",
        "priority_badge",
        "organization",
        "assigned_to",
        "created_at",
    )
    list_filter = (
        "status",
        "priority",
        "category",
        "organization",
        "is_shared",
        "is_deidentified",
        "created_at",
    )
    search_fields = (
        "case_number",
        "patient__first_name",
        "patient__last_name",
        "patient__mrn",
        "chief_complaint",
        "diagnosis",
    )
    readonly_fields = ("case_number", "created_at", "updated_at", "completed_at")
    inlines = [CaseImageInline, CommentInline, CaseActivityInline]
    filter_horizontal = ("share_with_branches",)
    raw_id_fields = ("patient", "created_by", "assigned_to")

    fieldsets = (
        (
            "Case Information",
            {"fields": ("case_number", "patient", "category", "status", "priority")},
        ),
        (
            "Clinical Details",
            {
                "fields": (
                    "chief_complaint",
                    "clinical_findings",
                    "diagnosis",
                    "treatment_plan",
                    "prognosis",
                )
            },
        ),
        ("Assignment", {"fields": ("organization", "created_by", "assigned_to")}),
        (
            "Sharing",
            {
                "fields": ("is_shared", "share_with_branches", "is_deidentified"),
                "classes": ("collapse",),
            },
        ),
        ("Metadata", {"fields": ("tags", "metadata"), "classes": ("collapse",)}),
        (
            "Timestamps",
            {
                "fields": ("created_at", "updated_at", "completed_at"),
                "classes": ("collapse",),
            },
        ),
    )

    def save_model(self, request, obj, form, change):
        if not obj.created_by:
            obj.created_by = request.user
        if not obj.organization and hasattr(request.user, "profile"):
            obj.organization = request.user.profile.organization

        # Log activity
        if change:
            CaseActivity.objects.create(
                case=obj,
                user=request.user,
                activity_type="UPDATED",
                description=f"Case updated via admin panel",
            )
        else:
            obj.save()
            CaseActivity.objects.create(
                case=obj,
                user=request.user,
                activity_type="CREATED",
                description=f"Case created via admin panel",
            )
            return

        super().save_model(request, obj, form, change)

    def patient_name(self, obj):
        return obj.patient.full_name

    patient_name.short_description = "Patient"

    def status_badge(self, obj):
        colors = {
            "DRAFT": "gray",
            "ACTIVE": "blue",
            "IN_REVIEW": "orange",
            "COMPLETED": "green",
            "ARCHIVED": "black",
        }
        color = colors.get(obj.status, "gray")
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 10px; '
            'border-radius: 3px; font-weight: bold;">{}</span>',
            color,
            obj.get_status_display(),
        )

    status_badge.short_description = "Status"

    def priority_badge(self, obj):
        colors = {
            "LOW": "#28a745",
            "MEDIUM": "#ffc107",
            "HIGH": "#fd7e14",
            "URGENT": "#dc3545",
        }
        color = colors.get(obj.priority, "#6c757d")
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 10px; '
            'border-radius: 3px; font-weight: bold;">{}</span>',
            color,
            obj.get_priority_display(),
        )

    priority_badge.short_description = "Priority"


@admin.register(CaseImage)
class CaseImageAdmin(admin.ModelAdmin):
    list_display = (
        "title",
        "filename",
        "image_type",
        "is_primary",
        "is_deidentified",
        "uploaded_by",
        "order",
    )
    list_filter = ("image_type", "is_primary", "is_deidentified", "created_at")
    search_fields = ("title", "description", "case__case_number")
    readonly_fields = ("uploaded_by", "created_at", "updated_at")
    raw_id_fields = ("case",)

    def save_model(self, request, obj, form, change):
        if not obj.uploaded_by:
            obj.uploaded_by = request.user
        super().save_model(request, obj, form, change)

        # Log activity
        CaseActivity.objects.create(
            case=obj.case,
            user=request.user,
            activity_type="IMAGE_ADDED" if not change else "UPDATED",
            description=f'Image "{obj.title}" {"added" if not change else "updated"}',
        )


@admin.register(Comment)
class CommentAdmin(admin.ModelAdmin):
    list_display = ("case", "author", "visibility", "parent", "is_edited", "created_at")
    list_filter = ("visibility", "is_edited", "created_at")
    search_fields = ("content", "case__case_number", "author__username")
    readonly_fields = ("is_edited", "edited_at", "created_at", "updated_at")
    raw_id_fields = ("case", "author", "parent")
    filter_horizontal = ("mentions",)

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)

        # Log activity
        if not change:
            CaseActivity.objects.create(
                case=obj.case,
                user=request.user,
                activity_type="COMMENTED",
                description=f"Comment added",
            )


@admin.register(CaseActivity)
class CaseActivityAdmin(admin.ModelAdmin):
    list_display = (
        "case",
        "activity_type",
        "user",
        "description",
        "ip_address",
        "created_at",
    )
    list_filter = ("activity_type", "created_at")
    search_fields = ("case__case_number", "user__username", "description")
    readonly_fields = (
        "case",
        "user",
        "activity_type",
        "description",
        "metadata",
        "ip_address",
        "created_at",
    )

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
