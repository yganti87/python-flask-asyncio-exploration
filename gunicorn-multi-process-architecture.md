# Gunicorn Multi-Process Architecture and Async Tasks

## Overview

This document explains how Gunicorn's multi-process architecture works, how requests are routed, how Flask applications are initialized in each worker, and best practices for running async tasks in this environment.

## Gunicorn Process Architecture

### Master Process
- **Role**: Orchestrates and manages worker processes
- **Responsibilities**:
  - Spawns and monitors worker processes
  - Handles graceful shutdowns and restarts
  - Manages worker lifecycle
  - Routes incoming requests to available workers
  - Handles signals (SIGTERM, SIGINT, etc.)

### Worker Processes
- **Role**: Execute the actual Flask application code
- **Characteristics**:
  - Each worker is a separate OS process (not threads)
  - Workers are completely isolated from each other
  - Each worker has its own memory space
  - Workers can run on different CPU cores
  - Workers are stateless and independent

## Request Routing

### How Requests Are Distributed

1. **Master Process Reception**: The master process accepts incoming HTTP connections
2. **Load Balancing**: Requests are distributed among available workers using various strategies:
   - **Round Robin** (default): Requests are distributed sequentially
   - **Random**: Requests are assigned randomly
   - **Least Connections**: Requests go to the worker with fewest active connections
3. **Worker Assignment**: The master process forwards the request to a selected worker
4. **Worker Processing**: The assigned worker processes the request through the Flask application
5. **Response Return**: The worker sends the response back through the master process

### Request Isolation
- Each request is handled by exactly one worker
- Workers cannot share request state directly
- No shared memory between workers (unless explicitly configured)
- Each worker maintains its own connection pools, caches, etc.

## Flask Application Initialization

### Worker Startup Sequence

1. **Process Fork**: Master process forks a new worker process
2. **Environment Setup**: Worker inherits environment variables and file descriptors
3. **Application Import**: Worker imports the Flask application module
4. **Application Factory**: If using an app factory pattern, the factory is called
5. **Configuration Loading**: Application configuration is loaded
6. **Extensions Initialization**: Flask extensions are initialized
7. **Database Connections**: Database connections and pools are established
8. **Ready State**: Worker signals it's ready to accept requests

### Key Initialization Points

```python
# This code runs in EACH worker process
def create_app():
    app = Flask(__name__)
    
    # This runs once per worker process
    print(f"Initializing Flask app in worker PID: {os.getpid()}")
    
    # Initialize extensions, databases, etc.
    db.init_app(app)
    
    return app
```

### Common Initialization Patterns

#### 1. Application Factory Pattern
```python
# app.py
def create_app():
    app = Flask(__name__)
    # Configuration and setup
    return app

# gunicorn.conf.py
def on_starting(server):
    print("Master process starting")

def on_reload(server):
    print("Master process reloading")

def worker_int(worker):
    print(f"Worker {worker.pid} received INT signal")

def worker_abort(worker):
    print(f"Worker {worker.pid} received ABORT signal")
```

#### 2. Global State Management
```python
# Avoid this - shared across all workers
global_cache = {}

# Better - per-worker state
class WorkerState:
    def __init__(self):
        self.cache = {}
        self.connections = {}

worker_state = WorkerState()
```

## Flask in Multi-Worker Environment

### Flask Application Lifecycle

1. **Single Application Instance**: Each worker has its own Flask application instance
2. **Request Context**: Flask creates a new request context for each HTTP request
3. **Application Context**: Flask maintains an application context during request processing
4. **Thread Safety**: Flask is thread-safe within a single worker process

### Flask Extensions and Multi-Worker Considerations

#### Database Connections
```python
# Good: Connection pooling per worker
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

def create_app():
    app = Flask(__name__)
    app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
        'pool_size': 10,
        'pool_recycle': 3600,
        'pool_pre_ping': True
    }
    db.init_app(app)
    return app
```

#### Session Management
```python
# Use external session storage (Redis, database)
app.config['SESSION_TYPE'] = 'redis'
app.config['SESSION_REDIS'] = redis.from_url('redis://localhost:6379')
```

#### Caching
```python
# Use external cache (Redis, Memcached)
from flask_caching import Cache

cache = Cache(config={
    'CACHE_TYPE': 'redis',
    'CACHE_REDIS_URL': 'redis://localhost:6379'
})
```

## Async Tasks in Multi-Worker Environment

### Challenges with Async Tasks

1. **Process Isolation**: Workers cannot share asyncio event loops
2. **Event Loop Lifecycle**: Each worker needs its own event loop
3. **Task Persistence**: Long-running tasks are lost when workers restart
4. **Resource Management**: Each worker manages its own async resources

### Best Practices for Async Tasks

#### 1. Thread Pool Approach (Recommended)
```python
import threading
from concurrent.futures import ThreadPoolExecutor
import time

class ThreadPoolAsyncTaskManager:
    def __init__(self, max_workers=4):
        self._executor = ThreadPoolExecutor(max_workers=max_workers)
        self._active_tasks = 0
        self._running = True
    
    def trigger_async_task(self, request_uuid, user_data=None):
        future = self._executor.submit(self._execute_long_running_task, 
                                     request_uuid, user_data)
        self._active_tasks += 1
        return request_uuid
    
    def _execute_long_running_task(self, request_uuid, user_data):
        try:
            # Simulate long-running work
            time.sleep(10)
            print(f"Task completed for {request_uuid}")
        finally:
            self._active_tasks = max(0, self._active_tasks - 1)
```

#### 2. Gevent Approach (Alternative)
```python
import gevent
from gevent.pool import Pool

class GeventAsyncTaskManager:
    def __init__(self, max_workers=4):
        self._pool = Pool(max_workers)
        self._active_tasks = 0
    
    def trigger_async_task(self, request_uuid, user_data=None):
        greenlet = self._pool.spawn(self._execute_long_running_task, 
                                   request_uuid, user_data)
        self._active_tasks += 1
        return request_uuid
```

#### 3. External Task Queue (Production Recommended)
```python
# Use Celery, RQ, or similar for production
from celery import Celery

celery = Celery('tasks', broker='redis://localhost:6379/0')

@celery.task
def long_running_task(request_uuid, user_data):
    # Task implementation
    pass

# In Flask route
@app.route('/trigger-task')
def trigger_task():
    task = long_running_task.delay(request_uuid, user_data)
    return {'task_id': task.id}
```

### Async Task Manager Factory Pattern

```python
import os
from threading import Lock

class AsyncTaskManagerFactory:
    _instances = {}
    _lock = Lock()
    
    @classmethod
    def get_manager(cls, manager_type='thread_pool'):
        current_pid = os.getpid()
        
        with cls._lock:
            if current_pid not in cls._instances:
                if manager_type == 'thread_pool':
                    cls._instances[current_pid] = ThreadPoolAsyncTaskManager()
                elif manager_type == 'gevent':
                    cls._instances[current_pid] = GeventAsyncTaskManager()
            
            return cls._instances[current_pid]
```

## Configuration Best Practices

### Gunicorn Configuration
```python
# gunicorn.conf.py
import multiprocessing

# Worker configuration
workers = multiprocessing.cpu_count() * 2 + 1
worker_class = 'gevent'  # or 'sync' for thread-based
worker_connections = 1000

# Timeout settings
timeout = 30
keepalive = 2

# Process naming
proc_name = 'flask-app'

# Logging
accesslog = '-'
errorlog = '-'
loglevel = 'info'

# Graceful shutdown
graceful_timeout = 30
```

### Environment-Specific Settings
```python
# Development
if os.environ.get('FLASK_ENV') == 'development':
    workers = 1
    reload = True
    loglevel = 'debug'

# Production
if os.environ.get('FLASK_ENV') == 'production':
    workers = multiprocessing.cpu_count() * 2 + 1
    preload_app = True
    max_requests = 1000
    max_requests_jitter = 100
```

## Monitoring and Debugging

### Worker Process Monitoring
```python
import psutil
import os

def get_worker_info():
    current_pid = os.getpid()
    process = psutil.Process(current_pid)
    
    return {
        'pid': current_pid,
        'cpu_percent': process.cpu_percent(),
        'memory_info': process.memory_info()._asdict(),
        'num_threads': process.num_threads(),
        'connections': len(process.connections())
    }
```

### Health Checks
```python
@app.route('/health')
def health_check():
    return {
        'status': 'healthy',
        'worker_pid': os.getpid(),
        'active_tasks': async_task_manager._active_tasks
    }
```

## Common Pitfalls and Solutions

### 1. Shared State Issues
```python
# ❌ Bad: Global variables shared across workers
global_counter = 0

# ✅ Good: Per-worker state
class WorkerState:
    def __init__(self):
        self.counter = 0

worker_state = WorkerState()
```

### 2. Database Connection Issues
```python
# ❌ Bad: Single connection shared across workers
db_connection = create_db_connection()

# ✅ Good: Connection pool per worker
db_pool = create_connection_pool()
```

### 3. File Locking Issues
```python
# ❌ Bad: File locks across processes
with open('data.txt', 'r+') as f:
    fcntl.flock(f.fileno(), fcntl.LOCK_EX)
    # Process file

# ✅ Good: Use external coordination (Redis, database)
import redis
r = redis.Redis()
with r.lock('file_lock', timeout=10):
    # Process file
```

### 4. Async Task Persistence
```python
# ❌ Bad: In-memory task storage
active_tasks = {}

# ✅ Good: External task storage
def store_task_status(task_id, status):
    redis_client.set(f"task:{task_id}", status)

def get_task_status(task_id):
    return redis_client.get(f"task:{task_id}")
```

## Performance Considerations

### Worker Count Optimization
- **CPU-bound applications**: `workers = cpu_count * 2 + 1`
- **I/O-bound applications**: `workers = cpu_count * 4 + 1`
- **Memory-constrained**: Reduce worker count based on available RAM

### Memory Management
- Monitor memory usage per worker
- Implement memory limits and recycling
- Use external caching for shared data

### Connection Pooling
- Configure database connection pools per worker
- Use connection pooling for external services
- Implement proper connection cleanup

## Security Considerations

### Process Isolation
- Workers are isolated by default
- Sensitive data should not be shared between workers
- Use secure external storage for sensitive information

### File Permissions
- Ensure proper file permissions for log files
- Use secure temporary directories
- Implement proper cleanup of temporary files

## Conclusion

Understanding Gunicorn's multi-process architecture is crucial for building scalable Flask applications. Key takeaways:

1. **Process Isolation**: Each worker is completely independent
2. **Request Routing**: Master process distributes requests among workers
3. **State Management**: Avoid shared state between workers
4. **Async Tasks**: Use thread pools or external task queues
5. **Monitoring**: Implement proper health checks and monitoring
6. **Configuration**: Tune worker count and timeouts for your use case

For production applications, consider using external task queues (Celery, RQ) for long-running async tasks, as they provide better reliability, monitoring, and scalability than in-process solutions. 