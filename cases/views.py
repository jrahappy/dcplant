import logging
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Q
from django.core.paginator import Paginator
from django.core.files.storage import default_storage
from django.http import JsonResponse, HttpResponseForbidden, FileResponse, HttpResponse
from django.utils import timezone
from django.views.decorators.http import require_http_methods
from django.conf import settings as django_settings
from .models import (
    Case,
    Patient,
    Category,
    Comment,
    CaseImage,
    CaseImageItem,
    CaseActivity,
    CaseOpinion,
)
from .forms import (
    CaseForm,
    PatientForm,
    CommentForm,
    CaseImageForm,
    CaseFilterForm,
    CategoryForm,
    MultipleImageUploadForm,
)
from .utils import ensure_user_profile
import os
import pydicom
from pydicom.pixel_data_handlers.util import apply_voi_lut
from PIL import Image as PILImage
import numpy as np
import io
import zipfile
import tempfile
import shutil
from datetime import datetime
from django.core.mail import send_mail
from django.conf import settings
from django.utils.html import strip_tags
from accounts.models import UserProfile


# temporary logger for this module
def delete_all_activity_logs(request):
    # Only superuser can delete activities
    if not request.user.is_superuser:
        return HttpResponseForbidden("You don't have permission to delete activities.")

    # Delete all activities (logs)
    deleted_count, _ = CaseActivity.objects.all().delete()

    messages.success(request, f"Deleted {deleted_count} case activities (logs).")
    return JsonResponse({"deleted_count": deleted_count})


# Case CRUD Views
@login_required
def case_list(request):
    """List all cases with filters"""
    profile = ensure_user_profile(request.user)
    user_org = profile.organization

    # Get cases from user's organization AND shared cases from other organizations
    # Show draft cases only to their creators

    cases_filter = Q(organization=user_org) | Q(share_with_branches=user_org)
    # Only show draft cases to their creators
    cases_filter &= ~Q(status="DRAFT") | Q(created_by=request.user)

    cases = (
        Case.objects.filter(cases_filter)
        .distinct()
        .select_related("patient", "category", "assigned_to", "created_by")
    )

    # Handle "open" status from sidebar first (shows Active and In Review)
    if request.GET.get("status") == "open":
        cases = cases.filter(status__in=["ACTIVE", "IN_REVIEW"])
        # Remove the status parameter to avoid form validation issues
        request_get = request.GET.copy()
        request_get.pop("status", None)
        filter_form = CaseFilterForm(request_get, user=request.user)
    else:
        # Apply filters
        filter_form = CaseFilterForm(request.GET, user=request.user)

    if filter_form.is_valid():
        # Search filter
        search = filter_form.cleaned_data.get("search")
        if search:
            cases = cases.filter(
                Q(case_number__icontains=search)
                | Q(patient__first_name__icontains=search)
                | Q(patient__last_name__icontains=search)
                | Q(patient__mrn__icontains=search)
                | Q(chief_complaint__icontains=search)
                | Q(diagnosis__icontains=search)
            )

        # Status filter (only if not "open")
        if request.GET.get("status") != "open":
            status = filter_form.cleaned_data.get("status")
            if status:
                cases = cases.filter(status=status)

        # Priority filter
        priority = filter_form.cleaned_data.get("priority")
        if priority:
            cases = cases.filter(priority=priority)

        # Category filter
        category = filter_form.cleaned_data.get("category")
        if category:
            cases = cases.filter(category=category)

        # Assigned to filter
        assigned_to = filter_form.cleaned_data.get("assigned_to")
        if assigned_to:
            cases = cases.filter(assigned_to=assigned_to)

        # Date range filter
        date_from = filter_form.cleaned_data.get("date_from")
        date_to = filter_form.cleaned_data.get("date_to")
        if date_from:
            cases = cases.filter(created_at__date__gte=date_from)
        if date_to:
            cases = cases.filter(created_at__date__lte=date_to)

    # Pagination
    paginator = Paginator(cases, 10)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    # Get current theme and select appropriate template
    theme = request.session.get("theme", django_settings.DEFAULT_THEME)
    if theme == "phoenix":
        template = "cases/case_list_v2.html"
    elif theme in ["brite", "brite_sidebar"]:
        template = "cases/case_list_brite.html"
    else:
        template = "cases/case_list.html"

    context = {
        "page_obj": page_obj,
        "cases": page_obj,  # For compatibility with Phoenix template
        "filter_form": filter_form,
        "total_count": cases.count(),
        "categories": Category.objects.all(),  # For Phoenix filter
    }
    return render(request, template, context)


@login_required
def case_detail(request, pk):
    """Detailed view of a single case"""
    profile = ensure_user_profile(request.user)
    user_org = profile.organization

    # Allow viewing if case belongs to user's org OR is shared with user's org
    # Draft cases can only be viewed by their creators

    case_filter = Q(pk=pk) & (
        Q(organization=user_org) | Q(share_with_branches=user_org)
    )

    # Try to get the case first to check if it's a draft
    try:
        case = Case.objects.get(pk=pk)
        if case.status == "DRAFT" and case.created_by != request.user:
            # Draft case can only be viewed by creator
            raise Case.DoesNotExist
    except Case.DoesNotExist:
        # Case doesn't exist or user doesn't have access
        case = get_object_or_404(Case.objects.filter(case_filter).distinct())

    # Log view activity
    CaseActivity.objects.create(
        case=case,
        user=request.user,
        activity_type="VIEWED",
        description=f"Case viewed by {request.user.get_full_name() or request.user.username}",
        ip_address=request.META.get("REMOTE_ADDR"),
    )

    # Get related data with visibility filtering

    # Build comment visibility filter
    comment_filter = Q()

    # Always show user's own comments
    comment_filter |= Q(author=request.user)

    # Show TEAM comments to users in the same organization
    comment_filter |= Q(visibility="TEAM", case__organization=user_org)

    # Show SHARED comments if user has access to the case
    if case.is_shared or case.organization == user_org:
        comment_filter |= Q(visibility="SHARED")

    # Apply the filter
    comments = (
        case.comments.filter(comment_filter)
        .select_related("author")
        .prefetch_related("mentions", "replies")
    )
    images = (
        case.images.select_related("uploaded_by")
        .prefetch_related("items")
        .order_by("-created_at")
    )
    activities = case.activities.select_related("user")[:20]

    # Get opinions (non-deleted) - show draft opinions only to their authors

    opinions_filter = Q(is_deleted=False)
    opinions_filter &= Q(status="PUBLISHED") | Q(author=request.user)
    opinions = (
        case.opinions.filter(opinions_filter)
        .select_related("author")
        .order_by("-created_at")
    )

    # Count files by type across all CaseImage groups
    from django.db.models import Count

    dicom_count = CaseImageItem.objects.filter(
        caseimage__case=case, is_dicom=True
    ).count()

    # Get file type breakdown
    regular_images_count = CaseImageItem.objects.filter(
        caseimage__case=case,
        image_type__in=["PHOTO", "XRAY", "PANO", "CBCT", "MRI", "CT"],
    ).count()
    pdf_count = CaseImageItem.objects.filter(
        caseimage__case=case, image_type="PDF"
    ).count()

    # Comment form
    comment_form = CommentForm()

    # Get current theme and select appropriate template
    theme = request.session.get("theme", django_settings.DEFAULT_THEME)
    if theme in ["brite", "brite_sidebar"]:
        template = "cases/case_detail_brite.html"
    else:
        template = "cases/case_detail.html"

    # Check if case can be deleted by current user
    has_other_opinions = (
        case.opinions.filter(is_deleted=False).exclude(author=request.user).exists()
    )
    can_delete_case = request.user.is_superuser or (  # Superuser can always delete
        not has_other_opinions
        and (request.user == case.created_by or request.user == request.user.is_staff)
    )  # Others only if no other opinions

    print(
        f"Can delete case: {can_delete_case}, Has other opinions: {has_other_opinions}"
    )

    context = {
        "case": case,
        "comments": comments,
        "images": images,
        "activities": activities,
        "comment_form": comment_form,
        "dicom_count": dicom_count,
        "regular_images_count": regular_images_count,
        "pdf_count": pdf_count,
        "opinions": opinions,
        "can_delete_case": can_delete_case,
        "has_other_opinions": has_other_opinions,
    }
    return render(request, template, context)


@login_required
def case_create(request):
    """Create a new case"""
    profile = ensure_user_profile(request.user)

    if request.method == "POST":
        form = CaseForm(request.POST, user=request.user)
        if form.is_valid():
            case = form.save(commit=False)
            case.organization = profile.organization
            case.created_by = request.user
            case.save()
            form.save_m2m()  # Save many-to-many relationships

            # Log activity
            CaseActivity.objects.create(
                case=case,
                user=request.user,
                activity_type="CREATED",
                description=f"Case created for {case.patient.full_name}",
            )

            messages.success(request, f"Case {case.case_number} created successfully!")
            return redirect("cases:case_detail", pk=case.pk)
    else:
        # Check if patient ID is passed in URL
        initial_data = {}
        patient_id = request.GET.get("patient")
        if patient_id:
            try:
                # Verify patient belongs to user's organization
                patient = Patient.objects.get(
                    pk=patient_id, organization=profile.organization
                )
                initial_data["patient"] = patient.pk
            except Patient.DoesNotExist:
                pass

        form = CaseForm(user=request.user, initial=initial_data)

    # Get current theme and select appropriate template
    theme = request.session.get("theme", django_settings.DEFAULT_THEME)
    if theme in ["brite", "brite_sidebar"]:
        template = "cases/case_form_brite.html"
    else:
        template = "cases/case_form.html"

    context = {
        "form": form,
        "title": "Create New Case",
        "selected_patient_id": request.GET.get(
            "patient"
        ),  # Pass patient ID to template
    }
    return render(request, template, context)


@login_required
def case_update(request, pk):
    """Update an existing case"""
    profile = ensure_user_profile(request.user)
    user_org = profile.organization

    # Get the case - must belong to user's organization (not shared)
    case = get_object_or_404(Case, pk=pk, organization=user_org)

    # Check permissions - shared cases cannot be edited
    if not (
        request.user == case.created_by or profile.is_admin or request.user.is_staff
    ):
        messages.error(request, "You do not have permission to edit this case.")
        return redirect("cases:case_detail", pk=case.pk)

    if request.method == "POST":
        form = CaseForm(request.POST, instance=case, user=request.user)
        if form.is_valid():
            old_status = case.status
            case = form.save()

            # Log activity
            description = "Case updated"
            if old_status != case.status:
                description = f"Status changed from {old_status} to {case.status}"
                CaseActivity.objects.create(
                    case=case,
                    user=request.user,
                    activity_type="STATUS_CHANGED",
                    description=description,
                )
            else:
                CaseActivity.objects.create(
                    case=case,
                    user=request.user,
                    activity_type="UPDATED",
                    description=description,
                )

            messages.success(request, "Case updated successfully!")
            return redirect("cases:case_detail", pk=case.pk)
    else:
        form = CaseForm(instance=case, user=request.user)

    # Get current theme and select appropriate template
    theme = request.session.get("theme", django_settings.DEFAULT_THEME)
    if theme in ["brite", "brite_sidebar"]:
        template = "cases/case_form_brite.html"
    else:
        template = "cases/case_form.html"

    context = {
        "form": form,
        "case": case,
        "object": case,  # For template to know it's an update
        "title": f"Edit Case {case.case_number}",
    }
    return render(request, template, context)


@login_required
@require_http_methods(["POST"])
def case_publish(request, pk):
    """Publish a draft case"""
    profile = ensure_user_profile(request.user)

    # Get the case - only the creator can publish their draft
    case = get_object_or_404(Case, pk=pk, created_by=request.user)

    # Check if it's a draft
    if case.status != "DRAFT":
        messages.warning(request, "This case is already published.")
        return redirect("cases:case_detail", pk=case.pk)

    # Publish the case (set to ACTIVE)
    case.status = "ACTIVE"
    case.save()

    # Log activity
    CaseActivity.objects.create(
        case=case,
        user=request.user,
        activity_type="UPDATED",
        description=f"Published case",
    )

    messages.success(request, f"Case {case.case_number} published successfully!")

    # Redirect based on referrer
    referer = request.META.get("HTTP_REFERER", "")
    if "case_list" in referer or "cases/" in referer:
        return redirect("cases:case_list")
    return redirect("cases:case_detail", pk=case.pk)


@login_required
@require_http_methods(["POST"])
def case_to_draft(request, pk):
    """Revert a case back to draft status"""
    profile = ensure_user_profile(request.user)

    # Get the case - only the creator can revert to draft
    case = get_object_or_404(Case, pk=pk, created_by=request.user)

    # Check if it's already a draft
    if case.status == "DRAFT":
        messages.warning(request, "This case is already a draft.")
        return redirect("cases:case_detail", pk=case.pk)

    # Revert to draft
    case.status = "DRAFT"
    case.save()

    # Log activity
    CaseActivity.objects.create(
        case=case,
        user=request.user,
        activity_type="UPDATED",
        description=f"Reverted case to draft",
    )

    messages.success(
        request, f"Case {case.case_number} reverted to draft successfully!"
    )

    # Redirect based on referrer
    referer = request.META.get("HTTP_REFERER", "")
    if "case_list" in referer or "cases/" in referer:
        return redirect("cases:case_list")
    return redirect("cases:case_detail", pk=case.pk)


@login_required
@require_http_methods(["POST"])
def case_delete(request, pk):
    """Delete a case"""
    profile = ensure_user_profile(request.user)

    # Get the case
    if request.user.is_superuser:
        case = get_object_or_404(Case, pk=pk)
    elif request.user.is_staff:
        case = get_object_or_404(Case, pk=pk)
    else:
        case = get_object_or_404(Case, pk=pk, organization=profile.organization)

    # Check if case has opinions from other authors (excluding deleted opinions)
    has_other_opinions = (
        case.opinions.filter(is_deleted=False).exclude(author=request.user).exists()
    )

    # If case has opinions from other authors, only superuser can delete
    if has_other_opinions and not request.user.is_superuser:
        messages.error(
            request,
            "This case has clinical opinions from other users and cannot be deleted. Only HQ superuser can delete cases with multiple contributors.",
        )
        return redirect("cases:case_detail", pk=case.pk)

    # Check permissions for non-superuser/non-staff users
    if not request.user.is_superuser and not request.user.is_staff:
        if not (request.user == case.created_by or profile.is_admin):
            return HttpResponseForbidden(
                "You don't have permission to delete this case."
            )

    case_number = case.case_number
    case.delete()
    messages.success(request, f"Case {case_number} deleted successfully!")

    return redirect("cases:case_list")


@login_required
@require_http_methods(["POST"])
def add_opinion(request, pk):
    """Add a clinical opinion to a case"""
    profile = ensure_user_profile(request.user)

    # Get the case - staff can add opinions to any case
    if request.user.is_staff:
        case = get_object_or_404(Case, pk=pk)
    else:
        # Check if case belongs to user's org or is shared with them

        case = get_object_or_404(
            Case.objects.filter(
                Q(pk=pk)
                & (
                    Q(organization=profile.organization)
                    | Q(share_with_branches=profile.organization)
                )
            ).distinct()
        )

    # Get the opinion content from POST data
    content = request.POST.get("content", "").strip()
    status = request.POST.get("status", "PUBLISHED")
    case_status = request.POST.get("case_status", "").strip()

    if content:
        # Create the opinion
        opinion = CaseOpinion.objects.create(
            case=case, author=request.user, content=content, status=status
        )

        # Update case status if requested
        if case_status and case_status != case.status:
            old_status = case.get_status_display()
            case.status = case_status
            case.save()

            # Log status change activity
            CaseActivity.objects.create(
                case=case,
                user=request.user,
                activity_type="STATUS_CHANGED",
                description=f"Status changed from {old_status} to {case.get_status_display()}",
            )
            messages.success(
                request,
                f"Clinical opinion added and case status updated to {case.get_status_display()}!",
            )
        else:
            messages.success(request, "Clinical opinion added successfully!")

        # Log opinion activity
        CaseActivity.objects.create(
            case=case,
            user=request.user,
            activity_type="COMMENTED",
            description=f"Added clinical opinion",
        )
    else:
        messages.error(request, "Opinion content cannot be empty.")

    return redirect("cases:case_detail", pk=case.pk)


@login_required
@require_http_methods(["POST"])
def update_opinion(request, pk):
    """Update a clinical opinion"""
    opinion = get_object_or_404(CaseOpinion, pk=pk)
    case = opinion.case

    # Check permissions - only author can edit
    if request.user != opinion.author:
        return HttpResponseForbidden("You don't have permission to edit this opinion.")

    # Get the updated content from POST data
    content = request.POST.get("content", "").strip()
    status = request.POST.get("status", opinion.status)
    case_status = request.POST.get("case_status", "").strip()

    if content:
        # Update the opinion
        opinion.content = content
        opinion.status = status
        opinion.save()

        # Update case status if requested
        if case_status and case_status != case.status:
            old_status = case.get_status_display()
            case.status = case_status
            case.save()

            # Log status change activity
            CaseActivity.objects.create(
                case=case,
                user=request.user,
                activity_type="STATUS_CHANGED",
                description=f"Status changed from {old_status} to {case.get_status_display()}",
            )
            messages.success(
                request,
                f"Clinical opinion updated and case status changed to {case.get_status_display()}!",
            )
        else:
            messages.success(request, "Clinical opinion updated successfully!")

        # Log opinion update activity
        CaseActivity.objects.create(
            case=case,
            user=request.user,
            activity_type="UPDATED",
            description=f"Updated clinical opinion",
        )
    else:
        messages.error(request, "Opinion content cannot be empty.")

    return redirect("cases:case_detail", pk=case.pk)


@login_required
@require_http_methods(["POST"])
def publish_opinion(request, pk):
    """Publish a draft clinical opinion"""
    opinion = get_object_or_404(CaseOpinion, pk=pk)
    case = opinion.case

    # Check permissions - only author can publish their own draft
    if request.user != opinion.author:
        return HttpResponseForbidden(
            "You don't have permission to publish this opinion."
        )

    # Check if it's a draft
    if opinion.status != "DRAFT":
        messages.warning(request, "This opinion is already published.")
        return redirect("cases:case_detail", pk=case.pk)

    # Publish the opinion
    opinion.status = "PUBLISHED"
    opinion.save()

    # Log activity
    CaseActivity.objects.create(
        case=case,
        user=request.user,
        activity_type="UPDATED",
        description=f"Published clinical opinion",
    )

    messages.success(request, "Clinical opinion published successfully!")
    return redirect("cases:case_detail", pk=case.pk)


@login_required
@require_http_methods(["POST"])
def delete_opinion(request, pk):
    """Delete a clinical opinion"""
    opinion = get_object_or_404(CaseOpinion, pk=pk)
    case = opinion.case

    # Check permissions - only author can delete (not even staff)
    if request.user != opinion.author:
        return HttpResponseForbidden(
            "You don't have permission to delete this opinion."
        )

    # Soft delete
    opinion.is_deleted = True
    opinion.save()

    messages.success(request, "Clinical opinion deleted successfully!")
    return redirect("cases:case_detail", pk=case.pk)


@login_required
@require_http_methods(["GET", "POST"])
def case_share(request, pk):
    """Share a case with other organizations"""
    from accounts.models import Organization

    profile = ensure_user_profile(request.user)
    case = get_object_or_404(Case, pk=pk, organization=profile.organization)

    # Check permissions - only case creator, admin or staff can share
    if not (
        request.user == case.created_by or profile.is_admin or request.user.is_staff
    ):
        messages.error(request, "You don't have permission to share this case.")
        return redirect("cases:case_detail", pk=case.pk)

    if request.method == "POST":
        # Check if this is an unshare request
        if "unshare" in request.POST or "cancel_sharing" in request.POST:
            # Unshare the case completely
            case.share_with_branches.clear()
            case.is_shared = False
            case.save()

            CaseActivity.objects.create(
                case=case,
                user=request.user,
                activity_type="SHARED",
                description="Case sharing removed",
            )

            messages.success(request, "Case sharing has been cancelled successfully.")
            return redirect("cases:case_detail", pk=case.pk)

        # Get selected organizations for sharing
        org_ids = request.POST.getlist("organizations")

        if org_ids:
            # Clear existing shares and add new ones
            case.share_with_branches.clear()
            organizations = Organization.objects.filter(id__in=org_ids)
            case.share_with_branches.add(*organizations)
            case.is_shared = True
            case.save()

            # # Send email notifications to HQ dentists
            # from django.core.mail import send_mail
            # from django.conf import settings
            # from django.utils.html import strip_tags
            # from accounts.models import UserProfile

            for org in organizations:
                # Check if this is HQ organization using org_type field
                if org.org_type == "HQ":
                    # Get all dentist users from HQ organization
                    hq_dentists = UserProfile.objects.filter(
                        organization=org,
                        # role='DENTIST',
                        user__is_active=True,
                    ).select_related("user")

                    # Prepare email list
                    dentist_emails = [
                        profile.user.email
                        for profile in hq_dentists
                        if profile.user.email
                    ]

                    if dentist_emails:
                        # Prepare email content
                        subject = f"New Case Shared: {case.case_number} - {case.patient.full_name}"

                        message = f"""
Dear Doctor,

A new case has been shared with your organization.

Case Details:
- Case Number: {case.case_number}
- Patient: {case.patient.full_name}
- Chief Complaint: {strip_tags(case.chief_complaint)[:200]}...
- Priority: {case.get_priority_display()}
- Status: {case.get_status_display()}
- Shared By: {request.user.get_full_name() or request.user.username}
- Organization: {profile.organization.name}

You can view the case at: {request.build_absolute_uri(f'/cases/case/{case.pk}/')}

Best regards,
DCPlant System
                        """

                        html_message = f"""
<html>
<body style="font-family: Arial, sans-serif;">
    <h2 style="color: #a2e436;">New Case Shared with Your Organization</h2>
    <p>Dear Doctor,</p>
    <p>A new case has been shared with your organization.</p>
    
    <div style="background-color: #f5f5f5; padding: 15px; border-left: 4px solid #a2e436; margin: 20px 0;">
        <h3 style="color: #333;">Case Details:</h3>
        <ul style="list-style-type: none; padding: 0;">
            <li><strong>Case Number:</strong> {case.case_number}</li>
            <li><strong>Patient:</strong> {case.patient.full_name}</li>
            <li><strong>Chief Complaint:</strong> {strip_tags(case.chief_complaint)[:200]}...</li>
            <li><strong>Priority:</strong> <span style="color: {'#dc3545' if case.priority == 'URGENT' else '#ffc107' if case.priority == 'HIGH' else '#28a745'};">{case.get_priority_display()}</span></li>
            <li><strong>Status:</strong> {case.get_status_display()}</li>
            <li><strong>Shared By:</strong> {request.user.get_full_name() or request.user.username}</li>
            <li><strong>Organization:</strong> {profile.organization.name}</li>
        </ul>
    </div>
    
    <p style="margin-top: 20px;">
        <a href="{request.build_absolute_uri(f'/cases/case/{case.pk}/')}" 
           style="background-color: #a2e436; color: #000; padding: 10px 20px; text-decoration: none; border-radius: 5px; display: inline-block;">
            View Case Details
        </a>
    </p>
    
    <hr style="border: 1px solid #e0e0e0; margin-top: 30px;">
    <p style="color: #666; font-size: 12px;">
        Best regards,<br>
        DCPlant System<br>
        <em>Dental Case & Patient Management Platform</em>
    </p>
</body>
</html>
                        """

                        try:
                            send_mail(
                                subject=subject,
                                message=message,
                                from_email=settings.DEFAULT_FROM_EMAIL,
                                recipient_list=dentist_emails,
                                html_message=html_message,
                                fail_silently=True,  # Don't break the sharing process if email fails
                            )
                        except Exception as e:
                            # Log the error but don't stop the sharing process
                            logging.error(
                                f"Failed to send email notification: {str(e)}"
                            )

            # Log activity
            CaseActivity.objects.create(
                case=case,
                user=request.user,
                activity_type="SHARED",
                description=f"Case shared with {len(organizations)} organization(s)",
                metadata={"org_ids": org_ids},
            )

            messages.success(
                request,
                f"Case shared with {len(organizations)} organization(s) successfully!",
            )
        else:
            # No organizations selected
            messages.warning(
                request, "Please select at least one organization to share with."
            )

        return redirect("cases:case_detail", pk=case.pk)

    # GET request - show sharing form
    all_organizations = Organization.objects.exclude(id=profile.organization.id).filter(
        is_active=True
    )
    shared_orgs = case.share_with_branches.all()

    # Get theme
    theme = request.session.get("theme", django_settings.DEFAULT_THEME)
    template = (
        "cases/case_share_brite.html"
        if theme in ["brite", "brite_sidebar"]
        else "cases/case_share.html"
    )

    context = {
        "case": case,
        "all_organizations": all_organizations,
        "shared_organizations": shared_orgs,
    }

    return render(request, template, context)


# Patient CRUD Views
@login_required
def patient_list(request):
    """List all patients from user's organization and shared cases"""
    profile = ensure_user_profile(request.user)
    user_org = profile.organization

    # Build the query for patients
    # Get patients from user's organization OR patients with shared cases
    patients = Patient.objects.filter(
        Q(organization=user_org) | Q(cases__share_with_branches=user_org)
    ).distinct()

    # Apply search filter
    search_query = request.GET.get("search", "")
    if search_query:
        patients = patients.filter(
            Q(mrn__icontains=search_query)
            | Q(first_name__icontains=search_query)
            | Q(last_name__icontains=search_query)
            | Q(email__icontains=search_query)
            | Q(phone__icontains=search_query)
        )

    # Pagination
    paginator = Paginator(patients, 15)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    # Add a flag to each patient to indicate if they're from a shared case
    for patient in page_obj:
        patient.is_from_shared_case = (
            patient.organization != user_org
            and patient.cases.filter(share_with_branches=user_org).exists()
        )
        patient.is_own_organization = patient.organization == user_org
        # Add organization name for shared patients
        if patient.is_from_shared_case:
            patient.shared_from_organization = patient.organization.name
        else:
            patient.shared_from_organization = None

    # Get current theme and select appropriate template
    theme = request.session.get("theme", django_settings.DEFAULT_THEME)
    if theme in ["brite", "brite_sidebar"]:
        template = "cases/patient_list_brite.html"
    else:
        template = "cases/patient_list.html"

    context = {
        "page_obj": page_obj,
        "search_query": search_query,
        "total_count": patients.count(),
    }
    return render(request, template, context)


@login_required
def patient_detail(request, pk):
    """Patient detail view - allows viewing patients from shared cases"""
    profile = ensure_user_profile(request.user)
    user_org = profile.organization

    # Check if patient belongs to user's organization OR has cases shared with user's organization
    try:
        patient = Patient.objects.get(pk=pk)

        # Check if user has access to this patient
        has_access = (
            patient.organization == user_org
            or patient.cases.filter(share_with_branches=user_org).exists()
        )

        if not has_access:
            messages.error(request, "You do not have permission to view this patient.")
            return redirect("cases:patient_list")

    except Patient.DoesNotExist:
        messages.error(request, "Patient not found.")
        return redirect("cases:patient_list")

    # Get only cases that the user has access to
    cases = (
        patient.cases.filter(Q(organization=user_org) | Q(share_with_branches=user_org))
        .distinct()
        .select_related("category", "assigned_to")
    )

    # Calculate statistics
    total_cases = cases.count()
    active_cases = cases.filter(status__in=["OPEN", "IN_PROGRESS"]).count()
    completed_cases = cases.filter(status="COMPLETED").count()

    # Add flags for template
    patient.is_from_shared_case = (
        patient.organization != user_org
        and patient.cases.filter(share_with_branches=user_org).exists()
    )
    patient.is_own_organization = patient.organization == user_org
    # Add organization name for shared patients
    if patient.is_from_shared_case:
        patient.shared_from_organization = patient.organization.name
    else:
        patient.shared_from_organization = None

    # Get current theme and select appropriate template
    theme = request.session.get("theme", django_settings.DEFAULT_THEME)
    if theme in ["brite", "brite_sidebar"]:
        template = "cases/patient_detail_brite.html"
    else:
        template = "cases/patient_detail.html"

    context = {
        "patient": patient,
        "cases": cases,
        "total_cases": total_cases,
        "active_cases": active_cases,
        "completed_cases": completed_cases,
    }
    return render(request, template, context)


@login_required
def patient_create(request):
    """Create a new patient"""
    profile = ensure_user_profile(request.user)

    if request.method == "POST":
        form = PatientForm(request.POST)
        if form.is_valid():
            patient = form.save(commit=False)
            patient.organization = profile.organization
            patient.created_by = request.user
            if form.cleaned_data.get("consent_given"):
                patient.consent_date = timezone.now()
            patient.save()

            messages.success(
                request, f"Patient {patient.full_name} created successfully!"
            )
            return redirect("cases:patient_detail", pk=patient.pk)
    else:
        form = PatientForm()

    # Get current theme and select appropriate template
    theme = request.session.get("theme", django_settings.DEFAULT_THEME)
    if theme in ["brite", "brite_sidebar"]:
        template = "cases/patient_form_brite.html"
    else:
        template = "cases/patient_form.html"

    context = {
        "form": form,
        "title": "Add New Patient",
    }
    return render(request, template, context)


@login_required
def patient_update(request, pk):
    """Update patient information"""
    profile = ensure_user_profile(request.user)
    patient = get_object_or_404(Patient, pk=pk, organization=profile.organization)

    if request.method == "POST":
        form = PatientForm(request.POST, instance=patient)
        if form.is_valid():
            patient = form.save(commit=False)
            if form.cleaned_data.get("consent_given") and not patient.consent_date:
                patient.consent_date = timezone.now()
            patient.save()

            messages.success(request, "Patient information updated successfully!")
            return redirect("cases:patient_detail", pk=patient.pk)
    else:
        form = PatientForm(instance=patient)

    # Get current theme and select appropriate template
    theme = request.session.get("theme", django_settings.DEFAULT_THEME)
    if theme in ["brite", "brite_sidebar"]:
        template = "cases/patient_form_brite.html"
    else:
        template = "cases/patient_form.html"

    context = {
        "form": form,
        "patient": patient,
        "object": patient,  # For template to know it's an update
        "title": f"Edit Patient: {patient.full_name}",
    }
    return render(request, template, context)


@login_required
@require_http_methods(["POST"])
def patient_delete(request, pk):
    """Delete a patient"""
    profile = ensure_user_profile(request.user)
    patient = get_object_or_404(Patient, pk=pk, organization=profile.organization)

    # Check if patient has cases
    if patient.cases.exists():
        messages.error(
            request,
            "Cannot delete patient with existing cases. Please delete or reassign cases first.",
        )
        return redirect("cases:patient_detail", pk=patient.pk)

    patient_name = patient.full_name
    patient.delete()
    messages.success(request, f"Patient {patient_name} deleted successfully!")

    return redirect("cases:patient_list")


# Comment Views
@login_required
@require_http_methods(["POST"])
def comment_add(request, case_pk):
    """Add a comment to a case"""
    profile = ensure_user_profile(request.user)
    user_org = profile.organization

    # Allow commenting on cases from user's org OR shared with user's org

    case = get_object_or_404(
        Case.objects.filter(
            Q(pk=case_pk) & (Q(organization=user_org) | Q(share_with_branches=user_org))
        ).distinct()
    )

    form = CommentForm(request.POST)
    if form.is_valid():
        comment = form.save(commit=False)
        comment.case = case
        comment.author = request.user
        comment.save()

        # Log activity
        CaseActivity.objects.create(
            case=case,
            user=request.user,
            activity_type="COMMENTED",
            description="Added a comment",
        )

        messages.success(request, "Comment added successfully!")
    else:
        messages.error(request, "Error adding comment.")

    return redirect("cases:case_detail", pk=case.pk)


@login_required
@require_http_methods(["POST"])
def comment_delete(request, pk):
    """Delete a comment"""
    profile = ensure_user_profile(request.user)
    comment = get_object_or_404(Comment, pk=pk)
    case = comment.case

    # Check permissions
    if not (
        request.user == comment.author or profile.is_admin or request.user.is_staff
    ):
        return HttpResponseForbidden(
            "You don't have permission to delete this comment."
        )

    comment.delete()
    messages.success(request, "Comment deleted successfully!")

    return redirect("cases:case_detail", pk=case.pk)


# Image Upload Views
@login_required
def image_upload(request, case_pk):
    """Upload images to a case - supports multiple files"""
    profile = ensure_user_profile(request.user)
    user_org = profile.organization

    # Allow upload if case belongs to user's org OR is shared with user's org

    case_filter = Q(pk=case_pk) & (
        Q(organization=user_org) | Q(share_with_branches=user_org)
    )
    case = get_object_or_404(Case.objects.filter(case_filter).distinct())

    if request.method == "POST":
        print(f"DEBUG: POST request received")
        print(f"DEBUG: request.FILES: {request.FILES}")
        print(
            f"DEBUG: request.FILES.keys(): {request.FILES.keys() if request.FILES else 'None'}"
        )

        form = MultipleImageUploadForm(request.POST, request.FILES)

        # Get files from the form
        files = request.FILES.getlist("images")
        print(f"DEBUG: Files retrieved from form: {len(files)} files")
        for f in files:
            print(f"DEBUG: File: {f.name}, size: {f.size}")

        if form.is_valid() and files:
            uploaded_count = 0
            errors = []
            title_prefix = form.cleaned_data.get("title_prefix", "") or "Upload"

            # Generate a title for this upload batch/transaction
            from datetime import datetime

            if title_prefix:
                group_title = (
                    f"{title_prefix} - {datetime.now().strftime('%Y%m%d %H:%M')}"
                )
            else:
                group_title = f"Upload - {datetime.now().strftime('%Y%m%d %H:%M')}"

            # Create ONE CaseImage group for this entire upload transaction
            case_image = CaseImage(
                case=case,
                title=group_title,
                description=form.cleaned_data.get("description", "")
                or f"Batch upload of {len(files)} file(s)",
                uploaded_by=request.user,
            )
            case_image.save()

            # Now create CaseImageItems for each file in this group
            print(f"DEBUG: Processing {len(files)} files for CaseImage {case_image.id}")
            for index, uploaded_file in enumerate(files):
                try:
                    print(
                        f"DEBUG: Processing file {index}: {uploaded_file.name}, size: {uploaded_file.size}"
                    )
                    file_extension = os.path.splitext(uploaded_file.name)[1].lower()
                    is_dicom = file_extension in [".dcm", ".dicom"]
                    metadata = {}

                    # Determine file type
                    if file_extension in [".dcm", ".dicom"]:
                        file_type = "DICOM"
                    elif file_extension == ".pdf":
                        file_type = "PDF"
                    elif file_extension == ".zip":
                        file_type = "ZIP"
                    elif file_extension in [".jpg", ".jpeg", ".png", ".gif"]:
                        file_type = form.cleaned_data.get("image_type", "PHOTO")
                    else:
                        file_type = "OTHER"

                    # If DICOM, try to extract metadata
                    if is_dicom:
                        try:
                            uploaded_file.seek(0)
                            dicom_data = pydicom.dcmread(
                                io.BytesIO(uploaded_file.read())
                            )

                            # Extract basic metadata
                            if hasattr(dicom_data, "PatientName"):
                                metadata["patient_name"] = str(dicom_data.PatientName)
                            if hasattr(dicom_data, "StudyDate"):
                                metadata["study_date"] = str(dicom_data.StudyDate)
                            if hasattr(dicom_data, "Modality"):
                                metadata["modality"] = str(dicom_data.Modality)
                            if hasattr(dicom_data, "StudyDescription"):
                                metadata["study_description"] = str(
                                    dicom_data.StudyDescription
                                )

                            # Extract Instance Number for proper ordering
                            if hasattr(dicom_data, "InstanceNumber"):
                                metadata["instance_number"] = int(
                                    dicom_data.InstanceNumber
                                )

                            # Also extract Series and Study UIDs for grouping
                            if hasattr(dicom_data, "SeriesInstanceUID"):
                                metadata["series_uid"] = str(
                                    dicom_data.SeriesInstanceUID
                                )
                            if hasattr(dicom_data, "StudyInstanceUID"):
                                metadata["study_uid"] = str(dicom_data.StudyInstanceUID)

                            uploaded_file.seek(0)  # Reset file pointer
                        except Exception as e:
                            print(f"Error reading DICOM metadata: {e}")

                    # Create the CaseImageItem
                    image_item = CaseImageItem(
                        caseimage=case_image,
                        image=uploaded_file,
                        image_type=file_type,
                        is_dicom=is_dicom,
                        is_primary=(
                            index == 0
                            and not CaseImageItem.objects.filter(
                                caseimage__case=case, is_primary=True
                            ).exists()
                        ),
                        metadata=metadata,
                        order=index,  # Use index for ordering within the group
                    )
                    image_item.save()
                    uploaded_count += 1
                    print(
                        f"DEBUG: Successfully saved CaseImageItem {image_item.id} for file {uploaded_file.name}"
                    )

                except Exception as e:
                    print(f"DEBUG: Error saving file {uploaded_file.name}: {str(e)}")
                    errors.append(f"{uploaded_file.name}: {str(e)}")

            # Log activity if any files were uploaded
            if uploaded_count > 0:
                CaseActivity.objects.create(
                    case=case,
                    user=request.user,
                    activity_type="IMAGE_ADDED",
                    description=f"Added {uploaded_count} image(s)",
                )

                messages.success(
                    request, f"Successfully uploaded {uploaded_count} image(s)!"
                )

                # Show any errors
                for error in errors:
                    messages.error(request, f"Error: {error}")

                return redirect("cases:case_detail", pk=case.pk)
            else:
                messages.error(request, "No files were uploaded successfully.")
        else:
            print(f"DEBUG: Form not valid or no files")
            print(f"DEBUG: form.is_valid(): {form.is_valid()}")
            print(f"DEBUG: form.errors: {form.errors}")
            print(f"DEBUG: files count: {len(files)}")

            if not files:
                messages.error(request, "Please select at least one file to upload.")
            else:
                # Show form errors
                for field, errors in form.errors.items():
                    for error in errors:
                        messages.error(request, f"{field}: {error}")
    else:
        form = MultipleImageUploadForm()

    context = {
        "form": form,
        "case": case,
        "title": f"Upload Images for Case {case.case_number}",
    }

    # Select template based on theme
    theme = getattr(django_settings, "DEFAULT_THEME", "default")
    if theme == "brite":
        template = "cases/image_upload_brite.html"
    else:
        template = "cases/image_upload.html"

    return render(request, template, context)


@login_required
def image_edit(request, pk):
    """Edit a case image"""
    profile = ensure_user_profile(request.user)
    image = get_object_or_404(CaseImage, pk=pk)
    case = image.case

    # Check permissions
    if not (
        request.user == image.uploaded_by or profile.is_admin or request.user.is_staff
    ):
        return HttpResponseForbidden("You don't have permission to edit this image.")

    if request.method == "POST":
        form = CaseImageForm(request.POST, request.FILES, instance=image)
        if form.is_valid():
            image = form.save()

            # Log activity
            CaseActivity.objects.create(
                case=case,
                user=request.user,
                activity_type="UPDATED",
                description=f"Updated image: {image.title}",
            )

            messages.success(request, "Image updated successfully!")
            return redirect("cases:case_detail", pk=case.pk)
    else:
        form = CaseImageForm(instance=image)

    context = {
        "form": form,
        "case": case,
        "image": image,
        "title": f"Edit Image: {image.title}",
    }
    return render(request, "cases/image_form.html", context)


@login_required
def image_list(request, case_pk):
    """List all images for a case"""
    profile = ensure_user_profile(request.user)
    user_org = profile.organization

    # Allow access if case belongs to user's org OR is shared with user's org

    case_filter = Q(pk=case_pk) & (
        Q(organization=user_org) | Q(share_with_branches=user_org)
    )
    case = get_object_or_404(Case.objects.filter(case_filter).distinct())

    # Sort all images by created date
    images = (
        case.images.select_related("uploaded_by")
        .prefetch_related("items")
        .order_by("-created_at")  # Newest first
    )

    # Calculate statistics
    dicom_count = CaseImageItem.objects.filter(
        caseimage__case=case, is_dicom=True
    ).count()
    photo_count = CaseImageItem.objects.filter(
        caseimage__case=case, image_type="PHOTO"
    ).count()
    # Count total image groups instead
    total_groups = case.images.count()

    # Get theme and select appropriate template
    theme = request.session.get("theme", django_settings.DEFAULT_THEME)
    if theme in ["brite", "brite_sidebar"]:
        template = "cases/image_list_brite.html"
    else:
        template = "cases/image_list.html"

    context = {
        "case": case,
        "images": images,
        "dicom_count": dicom_count,
        "photo_count": photo_count,
        "total_groups": total_groups,
    }
    return render(request, template, context)


@login_required
def image_detail(request, pk):
    """View details of a specific CaseImage and its items"""
    profile = ensure_user_profile(request.user)
    image = get_object_or_404(CaseImage, pk=pk)

    # Check permissions - allow access if case belongs to user's org OR is shared with user's org
    user_org = profile.organization
    case = image.case
    has_access = (case.organization == user_org) or (
        case.is_shared and user_org in case.share_with_branches.all()
    )

    if not has_access:
        return HttpResponseForbidden("You don't have permission to view this image.")

    # Get all items for this CaseImage
    items = image.items.all().order_by("order")

    # Calculate statistics for this specific CaseImage
    dicom_count = items.filter(is_dicom=True).count()
    photo_count = items.filter(image_type="PHOTO").count()
    total_items = items.count()

    # Log view activity
    CaseActivity.objects.create(
        case=image.case,
        user=request.user,
        activity_type="VIEWED",
        description=f"Viewed image group: {image.title}",
        ip_address=request.META.get("REMOTE_ADDR"),
    )

    # Get theme and select appropriate template
    theme = request.session.get("theme", django_settings.DEFAULT_THEME)
    if theme in ["brite", "brite_sidebar"]:
        template = "cases/image_detail_brite.html"
    else:
        template = "cases/image_detail.html"

    context = {
        "case": image.case,
        "image": image,
        "items": items,
        "dicom_count": dicom_count,
        "photo_count": photo_count,
        "total_items": total_items,
    }
    return render(request, template, context)


@login_required
def dicom_viewer(request, pk):
    """View DICOM images with web viewer"""
    profile = ensure_user_profile(request.user)
    image = get_object_or_404(CaseImage, pk=pk)

    # Check permissions - allow access if case belongs to user's org OR is shared with user's org
    user_org = profile.organization
    case = image.case
    has_access = (case.organization == user_org) or (
        case.is_shared and user_org in case.share_with_branches.all()
    )

    if not has_access:
        return HttpResponseForbidden("You don't have permission to view this image.")

    # Log view activity
    CaseActivity.objects.create(
        case=image.case,
        user=request.user,
        activity_type="VIEWED",
        description=f"Viewed DICOM image: {image.title}",
        ip_address=request.META.get("REMOTE_ADDR"),
    )

    context = {
        "image": image,
    }
    return render(request, "cases/dicom_viewer_brite.html", context)


@login_required
def dicom_item_thumbnail(request, pk):
    profile = ensure_user_profile(request.user)
    item = get_object_or_404(CaseImageItem, pk=pk)

    # 권한
    user_org = profile.organization
    case = item.caseimage.case
    has_access = (case.organization == user_org) or (
        case.is_shared and user_org in case.share_with_branches.all()
    )
    if not has_access:
        return HttpResponseForbidden("You don't have permission to view this image.")
    if not item.is_dicom:
        return HttpResponse("Not a DICOM file", status=404)

    try:
        # ✅ 원격/로컬 스토리지 모두 동작: 파일 객체로 읽기
        with default_storage.open(item.image.name, "rb") as fh:
            ds = pydicom.dcmread(fh, force=True)  # 일부 파일은 force가 필요할 수 있음

        # 픽셀 배열
        arr = ds.pixel_array  # (압축이면 pylibjpeg/gdcm 설치 필요)
        if arr.ndim == 3 and arr.shape[0] > 1:
            # 멀티프레임이면 첫 프레임 사용(원하면 인덱싱 로직 조정)
            arr = arr[0]

        # VOI LUT/Windowing 적용(있을 때)
        try:
            arr = apply_voi_lut(arr, ds)
        except Exception:
            pass

        # CT 등 Rescale 보정
        slope = float(getattr(ds, "RescaleSlope", 1.0))
        intercept = float(getattr(ds, "RescaleIntercept", 0.0))
        if slope != 1.0 or intercept != 0.0:
            arr = arr.astype(np.float32) * slope + intercept

        # MONOCHROME1은 흑백 반전
        if getattr(ds, "PhotometricInterpretation", "").upper() == "MONOCHROME1":
            arr = arr.max() - arr

        # 0~255 정규화 (0 division 방지)
        arr = arr.astype(np.float32)
        arr -= arr.min()
        peak = arr.max()
        if peak > 0:
            arr = arr / peak
        arr = (arr * 255).astype(np.uint8)

        img = PILImage.fromarray(arr)
        if img.mode != "RGB":
            img = img.convert("RGB")

        # 필요 시 썸네일 크기 지정(주석 해제)
        # img.thumbnail((512, 512), PILImage.Resampling.LANCZOS)

        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=90, optimize=True)
        buf.seek(0)
        return FileResponse(buf, content_type="image/jpeg")

    except Exception as e:
        # 서버 로그로 남기기
        import logging

        logging.getLogger(__name__).exception(
            "DICOM to JPEG failed (item %s): %s", pk, e
        )
        return HttpResponse("Error processing DICOM", status=500)


@login_required
def dicom_to_jpg(request, pk):
    """Convert DICOM to JPG for preview"""
    profile = ensure_user_profile(request.user)
    image = get_object_or_404(CaseImage, pk=pk)

    # Check permissions - allow access if case belongs to user's org OR is shared with user's org
    user_org = profile.organization
    case = image.case
    has_access = (case.organization == user_org) or (
        case.is_shared and user_org in case.share_with_branches.all()
    )

    if not has_access:
        return HttpResponseForbidden("You don't have permission to view this image.")

    # Get the first DICOM item from this CaseImage
    dicom_item = image.items.filter(is_dicom=True).first()
    if not dicom_item:
        return HttpResponse("No DICOM file found", status=404)

    try:
        # Read DICOM file
        dicom_path = dicom_item.image.path
        dicom_data = pydicom.dcmread(dicom_path)

        # Convert to PIL Image
        pixel_array = dicom_data.pixel_array

        # Normalize the image
        if hasattr(dicom_data, "RescaleSlope") and hasattr(
            dicom_data, "RescaleIntercept"
        ):
            pixel_array = (
                pixel_array * dicom_data.RescaleSlope + dicom_data.RescaleIntercept
            )

        # Convert to 8-bit
        pixel_array = (
            (pixel_array - pixel_array.min())
            / (pixel_array.max() - pixel_array.min())
            * 255
        ).astype("uint8")

        # Create PIL Image
        pil_image = PILImage.fromarray(pixel_array)

        # Apply window/level if specified
        if hasattr(dicom_data, "WindowCenter") and hasattr(dicom_data, "WindowWidth"):
            # Apply windowing (simplified)
            pass

        # Convert to RGB
        if pil_image.mode != "RGB":
            pil_image = pil_image.convert("RGB")

        # Save to BytesIO
        img_io = io.BytesIO()
        pil_image.save(img_io, "JPEG", quality=95)
        img_io.seek(0)

        return FileResponse(img_io, content_type="image/jpeg")
    except Exception as e:
        print(f"Error converting DICOM to JPG: {e}")
        # Return a placeholder image or error image
        return JsonResponse({"error": "Failed to convert DICOM to JPG"}, status=500)


@login_required
def dicom_series_viewer(request, pk):
    """View DICOM series (CBCT stack) with advanced viewer"""
    profile = ensure_user_profile(request.user)
    user_org = profile.organization

    # Allow viewing if case belongs to user's org OR is shared with user's org

    case_filter = Q(pk=pk) & (
        Q(organization=user_org) | Q(share_with_branches=user_org)
    )
    case = get_object_or_404(Case.objects.filter(case_filter).distinct())

    # Get all CaseImage groups that contain DICOM files
    # Now we need to get CaseImageItems that are DICOM files
    dicom_image_groups = (
        CaseImage.objects.filter(case=case, items__is_dicom=True)
        .distinct()
        .prefetch_related("items")
    )

    if not dicom_image_groups.exists():
        messages.warning(request, "No DICOM images found for this case.")
        return redirect("cases:case_detail", pk=case.pk)

    # Collect all DICOM items from all groups, sorted by order
    dicom_items = []
    for group in dicom_image_groups:
        dicom_items.extend(group.items.filter(is_dicom=True).order_by("order"))

    if not dicom_items:
        messages.warning(request, "No DICOM image files found for this case.")
        return redirect("cases:case_detail", pk=case.pk)

    # Prepare image URLs for the viewer
    image_urls = [item.image.url for item in dicom_items]

    # Log activity
    CaseActivity.objects.create(
        case=case,
        user=request.user,
        activity_type="VIEWED",
        description=f"Viewed DICOM series ({len(dicom_items)} slices)",
        ip_address=request.META.get("REMOTE_ADDR"),
    )

    # Check if user came from a specific image group
    from_image_id = request.GET.get("from_image")
    from_image = None
    if from_image_id:
        try:
            from_image = CaseImage.objects.get(pk=from_image_id, case=case)
        except CaseImage.DoesNotExist:
            pass

    context = {
        "case": case,
        "dicom_images": dicom_items,
        "image_urls": image_urls,
        "total_slices": len(dicom_items),
        "from_image": from_image,
    }

    # Select template based on theme
    theme = getattr(django_settings, "DEFAULT_THEME", "default")
    if theme == "brite":
        template = "cases/dicom_series_viewer_brite.html"
    else:
        template = "cases/dicom_series_viewer.html"

    return render(request, template, context)


@login_required
@require_http_methods(["POST"])
def image_delete(request, pk):
    """Delete a case image"""
    profile = ensure_user_profile(request.user)
    image = get_object_or_404(CaseImage, pk=pk)
    case = image.case
    user_org = profile.organization

    # First check if user has access to the case
    has_case_access = (case.organization == user_org) or (
        case.is_shared and user_org in case.share_with_branches.all()
    )
    if not has_case_access:
        return HttpResponseForbidden("You don't have access to this case.")

    # Check delete permissions - only uploader or superuser can delete
    if not (request.user == image.uploaded_by or request.user.is_superuser):
        return HttpResponseForbidden("You don't have permission to delete this image.")

    # Log activity
    CaseActivity.objects.create(
        case=case,
        user=request.user,
        activity_type="IMAGE_REMOVED",
        description=f"Removed image: {image.title}",
    )

    image.delete()
    messages.success(request, "Image deleted successfully!")

    return redirect("cases:case_detail", pk=case.pk)


@login_required
@require_http_methods(["POST"])
def delete_dicom_series(request, pk):
    """Delete all DICOM images for a case"""
    profile = ensure_user_profile(request.user)
    case = get_object_or_404(Case, pk=pk, organization=profile.organization)

    # Check permissions
    if not (
        request.user == case.created_by or profile.is_admin or request.user.is_staff
    ):
        return HttpResponseForbidden(
            "You don't have permission to delete DICOM series for this case."
        )

    # Get all CaseImage groups that contain DICOM files
    dicom_image_groups = case.images.filter(items__is_dicom=True).distinct()
    dicom_count = CaseImageItem.objects.filter(
        caseimage__case=case, is_dicom=True
    ).count()

    if dicom_count > 0:
        # Delete all DICOM image groups
        dicom_image_groups.delete()

        # Log activity
        CaseActivity.objects.create(
            case=case,
            user=request.user,
            activity_type="IMAGE_REMOVED",
            description=f"Deleted entire DICOM series ({dicom_count} files)",
        )

        messages.success(request, f"Successfully deleted {dicom_count} DICOM files!")
    else:
        messages.warning(request, "No DICOM files found to delete.")

    return redirect("cases:case_detail", pk=case.pk)


# Category Views
@login_required
def category_list(request):
    """List all categories"""
    categories = Category.objects.all()

    context = {
        "categories": categories,
    }
    return render(request, "cases/category_list.html", context)


@login_required
def category_create(request):
    """Create a new category"""
    profile = ensure_user_profile(request.user)
    if not (profile.is_admin or request.user.is_staff):
        messages.error(request, "You do not have permission to create categories.")
        return redirect("cases:category_list")

    if request.method == "POST":
        form = CategoryForm(request.POST)
        if form.is_valid():
            category = form.save()
            messages.success(request, f"Category {category.name} created successfully!")
            return redirect("cases:category_list")
    else:
        form = CategoryForm()

    context = {
        "form": form,
        "title": "Create New Category",
    }
    return render(request, "cases/category_form.html", context)


# AJAX Views for dynamic operations
@login_required
def ajax_case_status_update(request, pk):
    """AJAX endpoint to update case status"""
    profile = ensure_user_profile(request.user)
    if request.method == "POST":
        case = get_object_or_404(Case, pk=pk, organization=profile.organization)
        new_status = request.POST.get("status")

        if new_status in dict(Case.STATUS_CHOICES):
            old_status = case.status
            case.status = new_status

            if new_status == "COMPLETED":
                case.completed_at = timezone.now()

            case.save()

            # Log activity
            CaseActivity.objects.create(
                case=case,
                user=request.user,
                activity_type="STATUS_CHANGED",
                description=f"Status changed from {old_status} to {new_status}",
            )

            return JsonResponse(
                {
                    "success": True,
                    "status": case.status,
                    "status_display": case.get_status_display(),
                }
            )

    return JsonResponse({"success": False, "error": "Invalid request"})


@login_required
@require_http_methods(["POST"])
def download_dicom_series(request, pk):
    """Download DICOM series as compressed ZIP file"""
    profile = ensure_user_profile(request.user)
    user_org = profile.organization

    # Allow downloading if case belongs to user's org OR is shared with user's org

    case_filter = Q(pk=pk) & (
        Q(organization=user_org) | Q(share_with_branches=user_org)
    )
    case = get_object_or_404(Case.objects.filter(case_filter).distinct())

    # Get all DICOM images for this case, sorted by order field
    dicom_images = CaseImage.objects.get_dicom_series_sorted(case)

    if not dicom_images.exists():
        return JsonResponse(
            {"error": "No DICOM images found for this case"}, status=404
        )

    # Log activity
    CaseActivity.objects.create(
        case=case,
        user=request.user,
        activity_type="DOWNLOADED",
        description=f"Downloaded DICOM series ({dicom_images.count()} files)",
        ip_address=request.META.get("REMOTE_ADDR"),
    )

    # Create temporary directory for processing
    with tempfile.TemporaryDirectory() as temp_dir:
        zip_path = os.path.join(temp_dir, f"case_{case.pk}_dicom_series.zip")

        with zipfile.ZipFile(
            zip_path, "w", zipfile.ZIP_DEFLATED, compresslevel=6
        ) as zip_file:
            # Add case information file
            case_info = f"""DCPlant - DICOM Series Export
Case Number: {case.case_number}
Patient: {case.patient.full_name}
MRN: {case.patient.mrn}
Export Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
Total DICOM Files: {dicom_images.count()}
Exported by: {request.user.get_full_name() or request.user.username}

DICOM Files:
"""

            for idx, image in enumerate(dicom_images, 1):
                try:
                    # Read the DICOM file
                    file_path = image.image.path
                    if os.path.exists(file_path):
                        # Get original filename or create a numbered one
                        original_name = os.path.basename(image.image.name)
                        if not original_name.lower().endswith((".dcm", ".dicom")):
                            original_name = f"slice_{idx:04d}.dcm"

                        # Add to zip with organized naming
                        zip_file.write(file_path, f"DICOM_Series/{original_name}")
                        case_info += f"{idx:3d}. {original_name} - {image.title}\n"

                except Exception as e:
                    print(f"Error adding DICOM file {image.id}: {e}")
                    continue

            # Add case information file
            zip_file.writestr("README.txt", case_info)

        # Read the zip file and return as response
        with open(zip_path, "rb") as zip_data:
            response = HttpResponse(zip_data.read(), content_type="application/zip")
            filename = f'case_{case.case_number}_dicom_series_{datetime.now().strftime("%Y%m%d")}.zip'
            response["Content-Disposition"] = f'attachment; filename="{filename}"'
            return response


@login_required
@require_http_methods(["POST"])
def download_all_images(request, pk):
    """Download all images (DICOM and regular) as compressed ZIP file"""
    profile = ensure_user_profile(request.user)
    user_org = profile.organization

    # Allow downloading if case belongs to user's org OR is shared with user's org

    case_filter = Q(pk=pk) & (
        Q(organization=user_org) | Q(share_with_branches=user_org)
    )
    case = get_object_or_404(Case.objects.filter(case_filter).distinct())

    # Get all image groups for this case
    all_image_groups = (
        case.images.all()
        .prefetch_related("items")
        .order_by("image_type", "-created_at")
    )

    if not all_image_groups.exists():
        return JsonResponse({"error": "No images found for this case"}, status=404)

    # Log activity
    CaseActivity.objects.create(
        case=case,
        user=request.user,
        activity_type="DOWNLOADED",
        description=f"Downloaded all images ({all_images.count()} files)",
        ip_address=request.META.get("REMOTE_ADDR"),
    )

    # Create temporary directory for processing
    with tempfile.TemporaryDirectory() as temp_dir:
        zip_path = os.path.join(temp_dir, f"case_{case.pk}_all_images.zip")

        with zipfile.ZipFile(
            zip_path, "w", zipfile.ZIP_DEFLATED, compresslevel=6
        ) as zip_file:
            # Count total items
            total_items = sum(group.items.count() for group in all_image_groups)
            dicom_items = sum(
                group.items.filter(is_dicom=True).count() for group in all_image_groups
            )

            # Add case information file
            case_info = f"""DCPlant - Complete Image Export
Case Number: {case.case_number}
Patient: {case.patient.full_name}
MRN: {case.patient.mrn}
Export Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
Total Image Groups: {all_image_groups.count()}
Total Files: {total_items}
DICOM Files: {dicom_items}
Regular Images: {total_items - dicom_items}
Exported by: {request.user.get_full_name() or request.user.username}

Image Files:
"""

            dicom_count = 0
            image_count = 0

            for image_group in all_image_groups:
                for item in image_group.items.all():
                    try:
                        # Read the file
                        file_path = item.image.path
                        if os.path.exists(file_path):
                            # Organize by type
                            if item.is_dicom:
                                dicom_count += 1
                                folder = "DICOM_Files"
                                original_name = os.path.basename(item.image.name)
                                if not original_name.lower().endswith(
                                    (".dcm", ".dicom")
                                ):
                                    original_name = f"dicom_{dicom_count:04d}.dcm"
                            else:
                                image_count += 1
                                folder = f"Images/{item.image_type}"
                                original_name = os.path.basename(item.image.name)
                                # Ensure proper extension
                                if "." not in original_name:
                                    ext = ".jpg"  # Default extension
                                    original_name += ext

                            # Add to zip with organized structure
                            zip_path_in_archive = f"{folder}/{original_name}"
                            zip_file.write(file_path, zip_path_in_archive)

                            # Add to case info
                            file_size = os.path.getsize(file_path)
                            file_size_mb = file_size / (1024 * 1024)
                            case_info += f"- {zip_path_in_archive} ({file_size_mb:.2f} MB) - {image_group.title}\n"

                    except Exception as e:
                        print(f"Error adding image file {item.id}: {e}")
                        continue

            # Add case information file
            zip_file.writestr("README.txt", case_info)

        # Stream the zip file as response for large files
        from django.http import FileResponse

        zip_file_handle = open(zip_path, "rb")
        response = FileResponse(
            zip_file_handle, content_type="application/zip", as_attachment=True
        )
        filename = f'case_{case.case_number}_all_images_{datetime.now().strftime("%Y%m%d")}.zip'
        response["Content-Disposition"] = f'attachment; filename="{filename}"'
        # Get file size for Content-Length header
        file_size = os.path.getsize(zip_path)
        response["Content-Length"] = str(file_size)
        return response


@login_required
def check_draft_case(request):
    """API endpoint to check if user has draft cases"""
    profile = ensure_user_profile(request.user)

    # Check for draft cases created by the current user
    draft_case = (
        Case.objects.filter(created_by=request.user, status="DRAFT")
        .order_by("-created_at")
        .first()
    )

    if draft_case:
        return JsonResponse(
            {
                "has_draft": True,
                "case_id": draft_case.pk,
                "case_number": draft_case.case_number,
                "patient_name": (
                    draft_case.patient.full_name if draft_case.patient else "No patient"
                ),
                "created_at": draft_case.created_at.strftime("%Y-%m-%d %H:%M"),
            }
        )
    else:
        return JsonResponse({"has_draft": False})
