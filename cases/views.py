from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Q
from django.core.paginator import Paginator
from django.http import JsonResponse, HttpResponseForbidden, FileResponse, HttpResponse
from django.utils import timezone
from django.views.decorators.http import require_http_methods
from django.conf import settings as django_settings
from .models import Case, Patient, Category, Comment, CaseImage, CaseActivity
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
from PIL import Image as PILImage
import io
import zipfile
import tempfile
import shutil
from datetime import datetime


# Case CRUD Views
@login_required
def case_list(request):
    """List all cases with filters"""
    profile = ensure_user_profile(request.user)
    user_org = profile.organization

    # Get cases from user's organization AND shared cases from other organizations
    from django.db.models import Q
    cases = Case.objects.filter(
        Q(organization=user_org) | Q(share_with_branches=user_org)
    ).distinct().select_related(
        "patient", "category", "assigned_to", "created_by"
    )

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

        # Status filter
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
    from django.db.models import Q
    case = get_object_or_404(
        Case.objects.filter(
            Q(pk=pk) & (Q(organization=user_org) | Q(share_with_branches=user_org))
        ).distinct()
    )

    # Log view activity
    CaseActivity.objects.create(
        case=case,
        user=request.user,
        activity_type="VIEWED",
        description=f"Case viewed by {request.user.get_full_name() or request.user.username}",
        ip_address=request.META.get("REMOTE_ADDR"),
    )

    # Get related data with visibility filtering
    from django.db.models import Q
    
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
    comments = case.comments.filter(comment_filter).select_related("author").prefetch_related(
        "mentions", "replies"
    )
    images = case.images.select_related("uploaded_by").order_by("-is_primary", "order", "-created_at")
    activities = case.activities.select_related("user")[:20]

    # Count DICOM images for series detection
    dicom_count = case.images.filter(is_dicom=True).count()

    # Comment form
    comment_form = CommentForm()

    # Get current theme and select appropriate template
    theme = request.session.get("theme", django_settings.DEFAULT_THEME)
    if theme in ["brite", "brite_sidebar"]:
        template = "cases/case_detail_brite.html"
    else:
        template = "cases/case_detail.html"

    context = {
        "case": case,
        "comments": comments,
        "images": images,
        "activities": activities,
        "comment_form": comment_form,
        "dicom_count": dicom_count,
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
    case = get_object_or_404(Case, pk=pk, organization=profile.organization)

    # Check permissions
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
def case_delete(request, pk):
    """Delete a case"""
    profile = ensure_user_profile(request.user)
    case = get_object_or_404(Case, pk=pk, organization=profile.organization)

    # Check permissions
    if not (
        request.user == case.created_by or profile.is_admin or request.user.is_staff
    ):
        return HttpResponseForbidden("You don't have permission to delete this case.")

    case_number = case.case_number
    case.delete()
    messages.success(request, f"Case {case_number} deleted successfully!")

    return redirect("cases:case_list")


@login_required
@require_http_methods(["GET", "POST"])
def case_share(request, pk):
    """Share a case with other organizations"""
    from accounts.models import Organization
    
    profile = ensure_user_profile(request.user)
    case = get_object_or_404(Case, pk=pk, organization=profile.organization)
    
    # Check permissions - only case creator, admin or staff can share
    if not (request.user == case.created_by or profile.is_admin or request.user.is_staff):
        messages.error(request, "You don't have permission to share this case.")
        return redirect("cases:case_detail", pk=case.pk)
    
    if request.method == "POST":
        # Check if this is an unshare request
        if 'unshare' in request.POST or 'cancel_sharing' in request.POST:
            # Unshare the case completely
            case.share_with_branches.clear()
            case.is_shared = False
            case.save()
            
            CaseActivity.objects.create(
                case=case,
                user=request.user,
                activity_type="SHARED",
                description="Case sharing removed"
            )
            
            messages.success(request, "Case sharing has been cancelled successfully.")
            return redirect("cases:case_detail", pk=case.pk)
        
        # Get selected organizations for sharing
        org_ids = request.POST.getlist('organizations')
        
        if org_ids:
            # Clear existing shares and add new ones
            case.share_with_branches.clear()
            organizations = Organization.objects.filter(id__in=org_ids)
            case.share_with_branches.add(*organizations)
            case.is_shared = True
            case.save()
            
            # Log activity
            CaseActivity.objects.create(
                case=case,
                user=request.user,
                activity_type="SHARED",
                description=f"Case shared with {len(organizations)} organization(s)",
                metadata={"org_ids": org_ids}
            )
            
            messages.success(request, f"Case shared with {len(organizations)} organization(s) successfully!")
        else:
            # No organizations selected
            messages.warning(request, "Please select at least one organization to share with.")
        
        return redirect("cases:case_detail", pk=case.pk)
    
    # GET request - show sharing form
    all_organizations = Organization.objects.exclude(id=profile.organization.id).filter(is_active=True)
    shared_orgs = case.share_with_branches.all()
    
    # Get theme
    theme = request.session.get("theme", django_settings.DEFAULT_THEME)
    template = "cases/case_share_brite.html" if theme in ["brite", "brite_sidebar"] else "cases/case_share.html"
    
    context = {
        "case": case,
        "all_organizations": all_organizations,
        "shared_organizations": shared_orgs,
    }
    
    return render(request, template, context)


# Patient CRUD Views
@login_required
def patient_list(request):
    """List all patients"""
    profile = ensure_user_profile(request.user)
    user_org = profile.organization

    patients = Patient.objects.filter(organization=user_org)

    # Search filter
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
    """Patient detail view"""
    profile = ensure_user_profile(request.user)
    patient = get_object_or_404(Patient, pk=pk, organization=profile.organization)
    cases = patient.cases.select_related("category", "assigned_to")

    # Calculate statistics
    total_cases = cases.count()
    active_cases = cases.filter(status__in=["OPEN", "IN_PROGRESS"]).count()
    completed_cases = cases.filter(status="COMPLETED").count()

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
    from django.db.models import Q
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
    case = get_object_or_404(Case, pk=case_pk, organization=profile.organization)

    if request.method == "POST":
        form = MultipleImageUploadForm(request.POST, request.FILES)

        # Get files from the form
        files = request.FILES.getlist("images")

        if form.is_valid() and files:
            uploaded_count = 0
            errors = []
            title_prefix = form.cleaned_data.get("title_prefix", "") or "Image"

            for index, uploaded_file in enumerate(files, 1):
                try:
                    # Create title for each image
                    if len(files) > 1:
                        title = f"{title_prefix} {index}"
                    else:
                        title = (
                            title_prefix
                            if title_prefix != "Image"
                            else uploaded_file.name.split(".")[0]
                        )

                    # Create CaseImage instance
                    image = CaseImage(
                        case=case,
                        image=uploaded_file,
                        title=title,
                        description=form.cleaned_data.get("description", ""),
                        image_type=form.cleaned_data.get("image_type", "PHOTO"),
                        taken_date=form.cleaned_data.get("taken_date"),
                        is_deidentified=form.cleaned_data.get("is_deidentified", False),
                        uploaded_by=request.user,
                        is_primary=(
                            index == 1
                            and not case.images.filter(is_primary=True).exists()
                        ),
                    )

                    # Check if file is DICOM
                    file_extension = os.path.splitext(uploaded_file.name)[1].lower()
                    if file_extension in [".dcm", ".dicom"]:
                        image.is_dicom = True
                        image.image_type = "DICOM"

                        # Try to extract DICOM metadata
                        try:
                            uploaded_file.seek(0)
                            dicom_data = pydicom.dcmread(
                                io.BytesIO(uploaded_file.read())
                            )
                            metadata = {}

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
                                metadata["instance_number"] = int(dicom_data.InstanceNumber)
                            
                            # Also extract Series and Study UIDs for grouping
                            if hasattr(dicom_data, "SeriesInstanceUID"):
                                metadata["series_uid"] = str(dicom_data.SeriesInstanceUID)
                            if hasattr(dicom_data, "StudyInstanceUID"):
                                metadata["study_uid"] = str(dicom_data.StudyInstanceUID)

                            image.metadata = metadata
                            uploaded_file.seek(0)  # Reset file pointer
                        except Exception as e:
                            print(f"Error reading DICOM metadata: {e}")

                    image.save()
                    uploaded_count += 1

                except Exception as e:
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
    case = get_object_or_404(Case, pk=case_pk, organization=profile.organization)
    
    # Sort all images: primary first, then by order (for DICOM), then by created date
    # DICOM images will be sorted by their Instance Number (order field)
    # Non-DICOM images will be sorted by created date
    images = case.images.select_related("uploaded_by").order_by(
        "-is_primary",  # Primary images first
        "is_dicom",      # Non-DICOM images before DICOM
        "order",         # Sort by Instance Number (affects DICOM images)
        "-created_at"    # Then by creation date (affects non-DICOM)
    )

    # Calculate statistics
    dicom_count = case.images.filter(is_dicom=True).count()
    photo_count = case.images.filter(image_type="PHOTO").count()
    deidentified_count = case.images.filter(is_deidentified=True).count()

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
        "deidentified_count": deidentified_count,
    }
    return render(request, template, context)


@login_required
def dicom_viewer(request, pk):
    """View DICOM images with web viewer"""
    profile = ensure_user_profile(request.user)
    image = get_object_or_404(CaseImage, pk=pk)

    # Check permissions
    if image.case.organization != profile.organization:
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
def dicom_to_jpg(request, pk):
    """Convert DICOM to JPG for preview"""
    profile = ensure_user_profile(request.user)
    image = get_object_or_404(CaseImage, pk=pk)

    # Check permissions
    if image.case.organization != profile.organization:
        return HttpResponseForbidden("You don't have permission to view this image.")

    try:
        # Read DICOM file
        dicom_path = image.image.path
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
    case = get_object_or_404(Case, pk=pk, organization=profile.organization)

    # Get all DICOM images for this case, sorted by order field
    # dicom_images = CaseImage.objects.get_dicom_series_sorted(case)
    dicom_images = CaseImage.objects.filter(case=case, is_dicom=True).order_by("order")

    # print(dicom_images)

    if not dicom_images.exists():
        messages.warning(request, "No DICOM images found for this case.")
        return redirect("cases:case_detail", pk=case.pk)

    # Prepare image URLs for the viewer
    image_urls = [img.image.url for img in dicom_images]

    # print(image_urls)

    # Log activity
    CaseActivity.objects.create(
        case=case,
        user=request.user,
        activity_type="VIEWED",
        description=f"Viewed DICOM series ({dicom_images.count()} slices)",
        ip_address=request.META.get("REMOTE_ADDR"),
    )

    context = {
        "case": case,
        "dicom_images": dicom_images,
        "image_urls": image_urls,
        "total_slices": dicom_images.count(),
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

    # Check permissions
    if not (
        request.user == image.uploaded_by or profile.is_admin or request.user.is_staff
    ):
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
        return HttpResponseForbidden("You don't have permission to delete DICOM series for this case.")
    
    # Get all DICOM images for this case
    dicom_images = case.images.filter(is_dicom=True)
    dicom_count = dicom_images.count()
    
    if dicom_count > 0:
        # Delete all DICOM images
        dicom_images.delete()
        
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
    case = get_object_or_404(Case, pk=pk, organization=profile.organization)

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
    case = get_object_or_404(Case, pk=pk, organization=profile.organization)

    # Get all images for this case
    all_images = case.images.all().order_by("is_dicom", "image")

    if not all_images.exists():
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
            # Add case information file
            case_info = f"""DCPlant - Complete Image Export
Case Number: {case.case_number}
Patient: {case.patient.full_name}
MRN: {case.patient.mrn}
Export Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
Total Images: {all_images.count()}
DICOM Files: {all_images.filter(is_dicom=True).count()}
Regular Images: {all_images.filter(is_dicom=False).count()}
Exported by: {request.user.get_full_name() or request.user.username}

Image Files:
"""

            dicom_count = 0
            image_count = 0

            for image in all_images:
                try:
                    # Read the file
                    file_path = image.image.path
                    if os.path.exists(file_path):
                        # Organize by type
                        if image.is_dicom:
                            dicom_count += 1
                            folder = "DICOM_Files"
                            original_name = os.path.basename(image.image.name)
                            if not original_name.lower().endswith((".dcm", ".dicom")):
                                original_name = f"dicom_{dicom_count:04d}.dcm"
                        else:
                            image_count += 1
                            folder = "Images"
                            original_name = os.path.basename(image.image.name)
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
                        case_info += f"- {zip_path_in_archive} ({file_size_mb:.2f} MB) - {image.title}\n"

                except Exception as e:
                    print(f"Error adding image file {image.id}: {e}")
                    continue

            # Add case information file
            zip_file.writestr("README.txt", case_info)

        # Read the zip file and return as response
        with open(zip_path, "rb") as zip_data:
            response = HttpResponse(zip_data.read(), content_type="application/zip")
            filename = f'case_{case.case_number}_all_images_{datetime.now().strftime("%Y%m%d")}.zip'
            response["Content-Disposition"] = f'attachment; filename="{filename}"'
            return response
