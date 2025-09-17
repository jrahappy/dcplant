import os
import platform
from celery import Celery

# Set the default Django settings module for the 'celery' program.
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')

app = Celery('dcplant')

# Using a string here means the worker doesn't have to serialize
# the configuration object to child processes.
# - namespace='CELERY' means all celery-related configuration keys
#   should have a `CELERY_` prefix.
app.config_from_object('django.conf:settings', namespace='CELERY')

# Load task modules from all registered Django apps.
app.autodiscover_tasks()

# Configure Celery to use Redis as the broker
# Default to localhost:6379 which is the standard Docker Redis port mapping
REDIS_HOST = os.environ.get('REDIS_HOST', 'localhost')
REDIS_PORT = os.environ.get('REDIS_PORT', '6379')
REDIS_DB = os.environ.get('REDIS_DB', '0')
REDIS_PASSWORD = os.environ.get('REDIS_PASSWORD', '')

if REDIS_PASSWORD:
    REDIS_URL = f'redis://:{REDIS_PASSWORD}@{REDIS_HOST}:{REDIS_PORT}/{REDIS_DB}'
else:
    REDIS_URL = f'redis://{REDIS_HOST}:{REDIS_PORT}/{REDIS_DB}'

app.conf.broker_url = os.environ.get('REDIS_URL', REDIS_URL)
app.conf.result_backend = os.environ.get('REDIS_URL', REDIS_URL)

# Redis connection pool settings
app.conf.broker_connection_retry_on_startup = True
app.conf.broker_connection_retry = True
app.conf.broker_connection_max_retries = 10

# Windows-specific configuration
if platform.system() == 'Windows':
    # Use solo or eventlet pool on Windows to avoid forking issues
    app.conf.worker_pool = 'solo'  # or 'eventlet' if you have eventlet installed
    app.conf.worker_concurrency = 1
    app.conf.task_always_eager = False

    # Disable prefork optimization on Windows
    app.conf.worker_prefetch_multiplier = 1
    app.conf.broker_pool_limit = None
else:
    # Linux/Mac configuration
    app.conf.worker_prefetch_multiplier = 4
    app.conf.worker_max_tasks_per_child = 1000

# General Celery configuration
app.conf.task_track_started = True
app.conf.task_time_limit = 30 * 60  # 30 minutes
app.conf.task_soft_time_limit = 25 * 60  # 25 minutes

# Configure celery-progress
app.conf.result_expires = 60 * 60 * 24  # Results expire after 24 hours

# Serialization settings
app.conf.task_serializer = 'json'
app.conf.result_serializer = 'json'
app.conf.accept_content = ['json']

# Timezone
app.conf.enable_utc = True
app.conf.timezone = 'UTC'


@app.task(bind=True)
def debug_task(self):
    """Debug task for testing Celery setup"""
    print(f'Request: {self.request!r}')
    return 'Celery is working!'