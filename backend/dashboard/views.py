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


@login_required
def dashboard_home(request):
    """Main dashboard view with theme support"""
    from cases.utils import ensure_user_profile
    
    profile = ensure_user_profile(request.user)
    user_org = profile.organization
    
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
    
    # Get statistics
    total_cases = Case.objects.filter(organization=user_org).count()
    active_cases = Case.objects.filter(
        organization=user_org,
        status__in=['OPEN', 'IN_PROGRESS']
    ).count()
    total_patients = Patient.objects.filter(organization=user_org).count()
    
    # Recent cases
    recent_cases = Case.objects.filter(organization=user_org).select_related(
        'patient', 'category', 'assigned_to'
    ).order_by('-created_at')[:5]
    
    # Recent activities
    recent_activities = CaseActivity.objects.filter(
        case__organization=user_org
    ).select_related('case', 'user').order_by('-created_at')[:10]
    
    # Case statistics by status
    case_stats = Case.objects.filter(organization=user_org).values(
        'status'
    ).annotate(count=Count('id'))
    
    # Format status display
    for stat in case_stats:
        stat['status'] = dict(Case.STATUS_CHOICES).get(stat['status'], stat['status'])
    
    context = {
        'total_cases': total_cases,
        'active_cases': active_cases,
        'total_patients': total_patients,
        'recent_cases': recent_cases,
        'recent_activities': recent_activities,
        'case_stats': case_stats,
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
    """List all users in the organization (admin only)"""
    from cases.utils import ensure_user_profile
    
    profile = ensure_user_profile(request.user)
    
    if not (profile.is_admin or request.user.is_staff):
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