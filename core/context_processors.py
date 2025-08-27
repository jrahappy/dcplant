from django.conf import settings


def site_info(request):
    """
    Add site-wide information to all templates.
    """
    return {
        'site_name': 'DCPlant',
        'site_title': 'Dental Case Management Platform',
        'site_description': 'Professional dental case and patient management system',
        'debug': settings.DEBUG,
        'user': request.user,
        'is_authenticated': request.user.is_authenticated if request.user else False,
    }


def theme_context(request):
    """
    Add theme settings to the context for all templates.
    """
    # Get theme from session or use default
    theme = request.session.get('theme', getattr(settings, 'DEFAULT_THEME', 'phoenix'))
    
    # Map theme to template base
    theme_templates = {
        'default': 'base.html',
        'phoenix': 'base_phoenix.html'
    }
    
    return {
        'current_theme': theme,
        'base_template': theme_templates.get(theme, 'base_phoenix.html'),
        'themes': [
            {'id': 'default', 'name': 'Default Bootstrap', 'template': 'base.html'},
            {'id': 'phoenix', 'name': 'Phoenix Theme', 'template': 'base_phoenix.html'}
        ]
    }