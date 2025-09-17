# Gunicorn configuration for production with large file upload support

import multiprocessing
import os

# Server socket
bind = "0.0.0.0:8000"
backlog = 2048

# Worker processes
workers = multiprocessing.cpu_count() * 2 + 1
worker_class = "sync"  # Can use 'gevent' for async if needed
worker_connections = 1000

# Timeout settings for large uploads
timeout = 3600  # 1 hour timeout for large file uploads
graceful_timeout = 3600
keepalive = 5

# Request settings
max_requests = 1000
max_requests_jitter = 50
limit_request_line = 0  # Unlimited request line size
limit_request_fields = 100
limit_request_field_size = 0  # Unlimited field size

# Logging
accesslog = "/var/log/gunicorn/access.log"
errorlog = "/var/log/gunicorn/error.log"
loglevel = "info"
access_log_format = '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s" %(D)s'

# Process naming
proc_name = 'dcplant'

# Server mechanics
daemon = False
pidfile = '/var/run/gunicorn.pid'
user = None
group = None
tmp_upload_dir = '/tmp'

# SSL (if terminating SSL at Gunicorn level)
# keyfile = '/path/to/keyfile'
# certfile = '/path/to/certfile'

# Worker timeout specifically for uploads
def worker_int(worker):
    """Called when a worker receives the INT or QUIT signal"""
    worker.log.info("Worker received signal, gracefully shutting down")

def when_ready(server):
    """Called when the server is ready to accept requests"""
    server.log.info("Server is ready. Spawning workers")

def pre_request(worker, req):
    """Called before a worker processes the request"""
    worker.log.debug("%s %s" % (req.method, req.path))

def post_request(worker, req, environ, resp):
    """Called after a worker processes the request"""
    worker.log.debug("%s %s %s" % (req.method, req.path, resp.status))