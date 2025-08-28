"""
Production settings override for AWS deployment
"""
from .settings import *

# Disable WhiteNoise compression to avoid permission errors
WHITENOISE_SKIP_COMPRESS_EXTENSIONS = ['jpg', 'jpeg', 'png', 'gif', 'webp', 'zip', 'gz', 'tgz', 'bz2', 'tbz', 'xz', 'br', 'swf', 'flv', 'woff', 'woff2']
WHITENOISE_AUTOREFRESH = False
WHITENOISE_USE_FINDERS = False

# Use standard static files storage instead of compressed
STATICFILES_STORAGE = "whitenoise.storage.CompressedStaticFilesStorage"

# Ensure DEBUG is False
DEBUG = False

# Security settings for production
SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = 'DENY'
SECURE_SSL_REDIRECT = False  # Set to True when HTTPS is configured
SESSION_COOKIE_SECURE = False  # Set to True when HTTPS is configured
CSRF_COOKIE_SECURE = False  # Set to True when HTTPS is configured

# Ensure proper static/media paths
STATIC_ROOT = BASE_DIR / "staticfiles"
MEDIA_ROOT = BASE_DIR / "media"