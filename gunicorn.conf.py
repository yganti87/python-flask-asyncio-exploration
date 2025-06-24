# Gunicorn configuration file for async performance
bind = "0.0.0.0:8000"
workers = 4
worker_class = "gevent"  # Use gevent workers for async performance (more widely supported)
worker_connections = 1000
timeout = 30
keepalive = 2
max_requests = 1000
max_requests_jitter = 50  # Reduced jitter for more predictable behavior
preload_app = True

# Removed worker_tmp_dir for macOS compatibility

# Worker lifecycle hooks for better async task management
def on_starting(server):
    """Called just after the server is started."""
    print("Gunicorn server starting...")

def on_reload(server):
    """Called to reload the server configuration."""
    print("Gunicorn server reloading...")

def worker_int(worker):
    """Called just after a worker has been initialized."""
    print(f"Worker {worker.pid} initialized")

def pre_fork(server, worker):
    """Called just before a worker has been forked."""
    print(f"Pre-forking worker {worker.pid}")

def post_fork(server, worker):
    """Called just after a worker has been forked."""
    print(f"Post-forking worker {worker.pid}")

def post_worker_init(worker):
    """Called just after a worker has initialized the application."""
    print(f"Worker {worker.pid} application initialized")

def worker_abort(worker):
    """Called when a worker received the SIGABRT signal."""
    print(f"Worker {worker.pid} aborted")

def worker_exit(server, worker):
    """Called when a worker exits."""
    print(f"Worker {worker.pid} exited") 