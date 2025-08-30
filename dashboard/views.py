from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth import login, authenticate, logout
from django.contrib.auth.models import User
from django.contrib import messages
from django.db.models import Q, Count
from django.utils import timezone
from datetime import timedelta
from django.core.paginator import Paginator
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.conf import settings as django_settings
from cases.models import Case, Patient, Category, CaseActivity
from blog.models import BlogPost
import json


@login_required
def dashboard_home(request):
    """Main dashboard view with theme support"""
    from cases.utils import ensure_user_profile
    from accounts.models import Organization
    from django.db.models import Q
    
    profile = ensure_user_profile(request.user)
    user_org = profile.organization
    
    # Check if user is from HQ (superuser or HQ organization type)
    is_hq = (user_org.org_type == 'HQ' or 
             profile.role == 'HQ_ADMIN' or 
             request.user.is_superuser)
    
    # Get current theme
    theme = request.session.get('theme', django_settings.DEFAULT_THEME)
    
    # Choose template based on theme
    template_map = {
        'default': 'dashboard/home.html',
        'phoenix': 'dashboard/home_phoenix.html',
        'brite': 'dashboard/home_brite.html',
        'brite_sidebar': 'dashboard/home_brite.html'  # Uses sidebar layout
    }
    # Use brite with sidebar as default
    template = template_map.get(theme, 'dashboard/home_brite.html')
    
    # Get statistics based on user's access level
    if is_hq:
        # HQ users see all organizations' data (excluding draft cases)
        total_cases = Case.objects.exclude(status='DRAFT').count()
        active_cases = Case.objects.filter(
            status__in=['ACTIVE', 'IN_REVIEW']
        ).count()
        total_patients = Patient.objects.all().count()
        total_organizations = Organization.objects.filter(is_active=True).count()
        
        # Recent cases from all organizations (exclude drafts not created by current user)
        recent_cases_filter = ~Q(status="DRAFT") | Q(created_by=request.user)
        recent_cases = Case.objects.filter(recent_cases_filter).select_related(
            'patient', 'category', 'assigned_to', 'organization'
        ).order_by('-created_at')[:10]
        
        # Recent activities from all organizations
        recent_activities = CaseActivity.objects.all().select_related(
            'case', 'user', 'case__organization'
        ).order_by('-created_at')[:5]
        
        # Case statistics by status across all organizations
        case_stats = Case.objects.values('status').annotate(count=Count('id'))
        
        # Organization statistics
        org_stats = Organization.objects.filter(is_active=True).annotate(
            case_count=Count('cases', distinct=True),
            patient_count=Count('patients', distinct=True)
        ).order_by('-case_count')[:5]
        
    else:
        # Regular users see only their organization's data (excluding draft cases)
        total_cases = Case.objects.filter(organization=user_org).exclude(status='DRAFT').count()
        active_cases = Case.objects.filter(
            organization=user_org,
            status__in=['ACTIVE', 'IN_REVIEW']
        ).count()
        total_patients = Patient.objects.filter(organization=user_org).count()
        total_organizations = 1
        
        # Recent cases from user's organization (exclude drafts not created by current user)
        recent_cases_filter = Q(organization=user_org) & (~Q(status="DRAFT") | Q(created_by=request.user))
        recent_cases = Case.objects.filter(recent_cases_filter).select_related(
            'patient', 'category', 'assigned_to'
        ).order_by('-created_at')[:5]
        
        # Recent activities from user's organization
        recent_activities = CaseActivity.objects.filter(
            case__organization=user_org
        ).select_related('case', 'user').order_by('-created_at')[:5]
        
        # Case statistics by status for user's organization
        case_stats = Case.objects.filter(organization=user_org).values(
            'status'
        ).annotate(count=Count('id'))
        
        org_stats = None
    
    # Calculate completed today for branch users
    from datetime import date
    today_start = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)
    today_end = timezone.now().replace(hour=23, minute=59, second=59, microsecond=999999)
    
    if is_hq:
        # For HQ, we don't need completed_today (they see organizations count instead)
        completed_today = None
    else:
        # Count cases that were updated to COMPLETED status today
        completed_today = Case.objects.filter(
            organization=user_org,
            status='COMPLETED',
            updated_at__gte=today_start,
            updated_at__lte=today_end
        ).count()
    
    # Format status display
    for stat in case_stats:
        stat['status'] = dict(Case.STATUS_CHOICES).get(stat['status'], stat['status'])
    
    # Prepare data for status chart
    status_counts = {status[0]: 0 for status in Case.STATUS_CHOICES}
    for stat in case_stats:
        # Get the original status key (before formatting)
        for key, value in Case.STATUS_CHOICES:
            if value == stat['status']:
                status_counts[key] = stat['count']
                break
    
    # Calculate monthly case counts for the last 6 months
    from datetime import datetime, timedelta
    monthly_data = []
    month_labels = []
    
    for i in range(5, -1, -1):
        # Calculate the start of each month
        today = timezone.now()
        month_start = (today - timedelta(days=30*i)).replace(day=1)
        if i == 0:
            month_end = today
        else:
            # Get the first day of next month
            if month_start.month == 12:
                month_end = month_start.replace(year=month_start.year+1, month=1, day=1)
            else:
                month_end = month_start.replace(month=month_start.month+1, day=1)
        
        # Count cases created in this month
        if is_hq:
            month_count = Case.objects.filter(
                created_at__gte=month_start,
                created_at__lt=month_end
            ).count()
        else:
            month_count = Case.objects.filter(
                organization=user_org,
                created_at__gte=month_start,
                created_at__lt=month_end
            ).count()
        
        monthly_data.append(month_count)
        month_labels.append(month_start.strftime('%b'))
    
    context = {
        'total_cases': total_cases,
        'active_cases': active_cases,
        'total_patients': total_patients,
        'total_organizations': total_organizations,
        'recent_cases': recent_cases,
        'recent_activities': recent_activities,
        'case_stats': case_stats,
        'org_stats': org_stats,
        'is_hq': is_hq,
        'completed_today': completed_today if not is_hq else None,
        # Status chart data
        'draft_cases': status_counts.get('DRAFT', 0),
        'open_cases': status_counts.get('ACTIVE', 0),
        'in_review_cases': status_counts.get('IN_REVIEW', 0),
        'completed_cases': status_counts.get('COMPLETED', 0),
        'cancelled_cases': status_counts.get('CANCELLED', 0),
        # Monthly chart data
        'monthly_labels': json.dumps(month_labels),
        'monthly_data': json.dumps(monthly_data),
    }
    return render(request, template, context)


@login_required
def search(request):
    """Global search functionality"""
    from cases.utils import ensure_user_profile
    
    query = request.GET.get('q', '')
    
    if not query:
        return redirect('dashboard:home')
    
    profile = ensure_user_profile(request.user)
    user_org = profile.organization
    
    # Search cases
    cases = Case.objects.filter(
        organization=user_org
    ).filter(
        Q(case_number__icontains=query) |
        Q(patient__first_name__icontains=query) |
        Q(patient__last_name__icontains=query) |
        Q(chief_complaint__icontains=query) |
        Q(diagnosis__icontains=query)
    ).select_related('patient', 'category')[:10]
    
    # Search patients
    patients = Patient.objects.filter(
        organization=user_org
    ).filter(
        Q(mrn__icontains=query) |
        Q(first_name__icontains=query) |
        Q(last_name__icontains=query) |
        Q(email__icontains=query)
    )[:10]
    
    context = {
        'query': query,
        'cases': cases,
        'patients': patients,
    }
    return render(request, 'dashboard/search_results.html', context)


@login_required
def profile(request):
    """User profile view"""
    from cases.utils import ensure_user_profile
    
    if request.method == 'POST':
        user = request.user
        user.first_name = request.POST.get('first_name', '')
        user.last_name = request.POST.get('last_name', '')
        user.email = request.POST.get('email', '')
        user.save()
        
        profile = ensure_user_profile(user)
        profile.phone = request.POST.get('phone', '')
        profile.bio = request.POST.get('bio', '')
        profile.specialty = request.POST.get('specialty', '')
        profile.license_number = request.POST.get('license_number', '')
        
        # Handle avatar upload
        if 'avatar' in request.FILES:
            profile.avatar = request.FILES['avatar']
        
        profile.save()
        
        messages.success(request, 'Profile updated successfully!')
        return redirect('dashboard:profile')
    
    profile = ensure_user_profile(request.user)
    
    # Get current theme and select appropriate template
    theme = request.session.get('theme', django_settings.DEFAULT_THEME)
    if theme in ['brite', 'brite_sidebar']:
        template = 'dashboard/profile_brite.html'
    else:
        template = 'dashboard/profile.html'
    
    return render(request, template, {'profile': profile})


@login_required
def password_change(request):
    """Password change view"""
    from django.contrib.auth import update_session_auth_hash
    from django.contrib.auth.forms import PasswordChangeForm
    
    if request.method == 'POST':
        form = PasswordChangeForm(request.user, request.POST)
        if form.is_valid():
            user = form.save()
            update_session_auth_hash(request, user)  # Keep user logged in
            messages.success(request, 'Your password was successfully updated!')
            return redirect('dashboard:profile')
        else:
            messages.error(request, 'Please correct the error below.')
    else:
        form = PasswordChangeForm(request.user)
    
    # Get current theme
    theme = request.session.get('theme', django_settings.DEFAULT_THEME)
    context = {'form': form}
    
    # For now, just redirect back to profile with a message
    messages.info(request, 'Password change feature coming soon!')
    return redirect('dashboard:profile')


@login_required
def settings(request):
    """User settings view with theme support"""
    from cases.utils import ensure_user_profile
    
    profile = ensure_user_profile(request.user)
    
    # Get current theme and select appropriate template
    theme = request.session.get('theme', django_settings.DEFAULT_THEME)
    if theme == 'phoenix':
        template = 'dashboard/settings_phoenix.html'
    elif theme in ['brite', 'brite_sidebar']:
        template = 'dashboard/settings_brite.html'
    else:
        template = 'dashboard/settings.html'
    
    if request.method == 'POST':
        # Handle settings update
        messages.success(request, 'Settings updated successfully!')
        return redirect('dashboard:settings')
    
    return render(request, template, {'profile': profile})


@login_required
def reports(request):
    """Reports and analytics view (admin only)"""
    from cases.utils import ensure_user_profile
    
    profile = ensure_user_profile(request.user)
    
    if not (profile.is_admin or request.user.is_staff):
        messages.error(request, 'You do not have permission to view reports.')
        return redirect('dashboard:home')
    
    user_org = profile.organization
    
    # Generate report data
    # Cases by status
    cases_by_status = Case.objects.filter(
        organization=user_org
    ).values('status').annotate(count=Count('id'))
    
    # Cases by priority
    cases_by_priority = Case.objects.filter(
        organization=user_org
    ).values('priority').annotate(count=Count('id'))
    
    # Cases by category
    cases_by_category = Case.objects.filter(
        organization=user_org
    ).values('category__name').annotate(count=Count('id'))
    
    # Recent week activity
    week_ago = timezone.now() - timedelta(days=7)
    recent_activities = CaseActivity.objects.filter(
        case__organization=user_org,
        created_at__gte=week_ago
    ).count()
    
    context = {
        'cases_by_status': cases_by_status,
        'cases_by_priority': cases_by_priority,
        'cases_by_category': cases_by_category,
        'recent_activities': recent_activities,
    }
    return render(request, 'dashboard/reports.html', context)


@login_required
def users_list(request):
    """List all users in the organization (superuser only)"""
    from cases.utils import ensure_user_profile
    
    profile = ensure_user_profile(request.user)
    
    if not request.user.is_superuser:
        messages.error(request, 'You do not have permission to view users.')
        return redirect('dashboard:home')
    
    users = User.objects.filter(
        profile__organization=profile.organization
    ).select_related('profile')
    
    context = {
        'users': users,
    }
    return render(request, 'dashboard/users_list.html', context)


def login_view(request):
    """Login view"""
    if request.user.is_authenticated:
        return redirect('dashboard:home')
    
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        user = authenticate(request, username=username, password=password)
        
        if user is not None:
            login(request, user)
            next_url = request.GET.get('next', 'dashboard:home')
            return redirect(next_url)
        else:
            messages.error(request, 'Invalid username or password.')
    
    # Use Brite theme login template
    return render(request, 'auth/login_brite.html')


def signup_view(request):
    """Signup view"""
    if request.user.is_authenticated:
        return redirect('dashboard:home')
    
    if request.method == 'POST':
        username = request.POST.get('username')
        email = request.POST.get('email')
        password1 = request.POST.get('password1')
        password2 = request.POST.get('password2')
        first_name = request.POST.get('first_name', '')
        last_name = request.POST.get('last_name', '')
        
        # Validation
        if password1 != password2:
            messages.error(request, 'Passwords do not match.')
        elif User.objects.filter(username=username).exists():
            messages.error(request, 'Username already exists.')
        elif User.objects.filter(email=email).exists():
            messages.error(request, 'Email already registered.')
        else:
            # Create user
            user = User.objects.create_user(
                username=username,
                email=email,
                password=password1,
                first_name=first_name,
                last_name=last_name
            )
            
            # The signal will create the profile automatically
            
            # Log the user in
            login(request, user)
            messages.success(request, 'Account created successfully!')
            return redirect('dashboard:home')
    
    return render(request, 'auth/signup.html')


@login_required
def logout_view(request):
    """Logout view"""
    logout(request)
    messages.success(request, 'You have been logged out successfully.')
    return redirect('dashboard:login')


@require_POST
@login_required
def switch_theme(request):
    """Switch between themes."""
    theme = request.POST.get('theme', 'brite')
    if theme in ['default', 'phoenix', 'brite']:
        request.session['theme'] = theme
        return JsonResponse({'status': 'success', 'theme': theme})
    return JsonResponse({'status': 'error', 'message': 'Invalid theme'}, status=400)