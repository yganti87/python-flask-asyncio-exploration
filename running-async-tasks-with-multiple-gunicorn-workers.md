# Running Async Tasks with Multiple Gunicorn Workers

## Overview

When running Flask applications with async tasks using gunicorn with multiple workers, you encounter unique challenges related to process isolation, resource contention, and event loop management. This guide explains the issues and provides best practices to ensure reliable async task execution.

## The Core Problem

When you run Flask with gunicorn using multiple workers, each worker process is a **separate Python process** that runs independently:

```python
# Each worker process gets its own copy of the AsyncTaskManager
worker_process_1 = AsyncTaskManager()  # PID: 1234
worker_process_2 = AsyncTaskManager()  # PID: 1235  
worker_process_3 = AsyncTaskManager()  # PID: 1236
worker_process_4 = AsyncTaskManager()  # PID: 1237
```

Each worker creates its own event loop in its own thread, but they're completely isolated from each other.

## Race Conditions in Multi-Worker Environments

### 1. **File System Contention**

**The Problem:**
```python
# Multiple workers trying to write to the same log file simultaneously
worker_1: logger.info("Task started")  # Tries to write to async_tasks.log
worker_2: logger.info("Task started")  # Tries to write to async_tasks.log  
worker_3: logger.info("Task started")  # Tries to write to async_tasks.log
worker_4: logger.info("Task started")  # Tries to write to async_tasks.log
```

**What Happens:**
```python
# In the logging configuration:
logging.basicConfig(
    handlers=[
        logging.FileHandler('async_tasks.log'),  # Single file, multiple writers
        logging.StreamHandler()
    ]
)
```

**Race Condition:**
- Worker 1 opens file for writing
- Worker 2 tries to open same file → **File lock contention**
- Worker 3 tries to write → **Blocked waiting for lock**
- Worker 4 tries to write → **Blocked waiting for lock**

**Result:** Event loop thread gets blocked waiting for file I/O, causing the entire worker to hang.

### 2. **Event Loop Thread Safety Issues**

**The Problem:**
```python
# Original problematic code:
def trigger_async_task(self, request_uuid: str, user_data: dict = None):
    # This can be called from multiple threads simultaneously
    future = asyncio.run_coroutine_threadsafe(
        self._long_running_async_task(request_uuid, user_data),
        self._loop  # What if _loop is None or being modified?
    )
```

**Race Condition Scenario:**
```python
# Timeline of events:
Time 1: Worker starts, creates event loop
Time 2: Request comes in, calls trigger_async_task()
Time 3: Another request comes in, calls trigger_async_task()
Time 4: Worker gets killed by gunicorn (timeout)
Time 5: Worker restarts, _loop is None
Time 6: Request tries to use _loop → CRASH!

# Or worse:
Time 1: Worker 1: _loop = asyncio.new_event_loop()
Time 2: Worker 2: _loop = asyncio.new_event_loop()  # Different process
Time 3: Worker 1: asyncio.set_event_loop(_loop)     # Sets global state
Time 4: Worker 2: asyncio.set_event_loop(_loop)     # Overwrites global state!
```

### 3. **Memory and Resource Contention**

**Shared Memory Issues:**
```python
# Each worker loads the same modules into memory
worker_1: import asyncio, threading, logging  # Memory: 50MB
worker_2: import asyncio, threading, logging  # Memory: 50MB  
worker_3: import asyncio, threading, logging  # Memory: 50MB
worker_4: import asyncio, threading, logging  # Memory: 50MB

# Total: 200MB for same code!
```

**Event Loop Memory Leaks:**
```python
# If event loops aren't properly cleaned up:
def _long_running_async_task(self, request_uuid: str, user_data: dict = None):
    # Each task holds references to objects
    await asyncio.sleep(5)
    # If worker dies abruptly, these references aren't cleaned up
    # Memory accumulates across worker restarts
```

### 4. **Thread Pool Contention**

**The Problem:**
```python
# asyncio uses a shared thread pool for blocking operations
import asyncio

async def blocking_operation():
    # This uses the default thread pool
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, some_blocking_function)

# Multiple workers = multiple thread pools competing for CPU
worker_1: ThreadPoolExecutor(max_workers=4)  # 4 threads
worker_2: ThreadPoolExecutor(max_workers=4)  # 4 threads  
worker_3: ThreadPoolExecutor(max_workers=4)  # 4 threads
worker_4: ThreadPoolExecutor(max_workers=4)  # 4 threads

# Total: 16 threads competing for CPU cores!
```

### 5. **Signal Handler Conflicts**

**The Problem:**
```python
# Each worker tries to register signal handlers
def signal_handler(signum, frame):
    cleanup()
    sys.exit(0)

signal.signal(signal.SIGINT, signal_handler)   # Worker 1
signal.signal(signal.SIGINT, signal_handler)   # Worker 2  
signal.signal(signal.SIGINT, signal_handler)   # Worker 3
signal.signal(signal.SIGINT, signal_handler)   # Worker 4

# What happens when Ctrl+C is pressed?
# Which worker's signal handler runs first?
# Do all workers exit or just one?
```

## How These Cause Event Loops to Hang

### 1. **Deadlock Scenarios**

```python
# Scenario: File I/O Deadlock
def _long_running_async_task(self, request_uuid: str, user_data: dict = None):
    # This runs in the event loop thread
    logger.info(f"Starting task {request_uuid}")  # Blocks waiting for file lock
    
    # Meanwhile, another worker is holding the file lock
    # Event loop thread is blocked → No other tasks can run
    # Worker appears "hung" even though it's just waiting
```

### 2. **Resource Starvation**

```python
# Scenario: Memory Starvation
worker_1: Creates 1000 async tasks → Memory usage: 500MB
worker_2: Creates 1000 async tasks → Memory usage: 500MB  
worker_3: Creates 1000 async tasks → Memory usage: 500MB
worker_4: Creates 1000 async tasks → Memory usage: 500MB

# Total: 2GB memory usage
# System runs out of memory → Workers get killed by OOM killer
# Event loops never get chance to complete tasks
```

### 3. **Thread Pool Exhaustion**

```python
# Scenario: Thread Pool Deadlock
async def blocking_operation():
    # This needs a thread from the pool
    await loop.run_in_executor(None, time.sleep, 10)

# If all threads in the pool are busy:
# - New async tasks can't get threads
# - Event loop can't schedule new work
# - Worker appears "hung"
```

## Real-World Example

Here's what was likely happening in your case:

```python
# Timeline of the race condition:
Time 1: Worker 1 starts, creates event loop
Time 2: Worker 2 starts, creates event loop  
Time 3: Request to Worker 1 → triggers async task
Time 4: Request to Worker 2 → triggers async task
Time 5: Both workers try to write to async_tasks.log simultaneously
Time 6: File lock contention → Worker 1 blocks
Time 7: Worker 1's event loop thread is blocked
Time 8: Worker 1 can't process new requests → appears "hung"
Time 9: Gunicorn kills Worker 1 due to timeout
Time 10: Worker 1's async tasks are lost forever
```

## Best Practices to Prevent Event Loop Hanging

### 1. **Use Process-Specific Resources**

**❌ Bad: Shared Resources**
```python
# All workers share the same log file
logging.basicConfig(
    handlers=[
        logging.FileHandler('async_tasks.log'),  # Shared file
        logging.StreamHandler()
    ]
)
```

**✅ Good: Process-Specific Resources**
```python
# Each worker gets its own log file
logging.basicConfig(
    handlers=[
        logging.FileHandler(f'async_tasks_{os.getpid()}.log'),  # Process-specific
        logging.StreamHandler()
    ]
)
```

### 2. **Implement Proper State Management**

**❌ Bad: No State Tracking**
```python
def trigger_async_task(self, request_uuid: str, user_data: dict = None):
    # No check if event loop is ready
    future = asyncio.run_coroutine_threadsafe(
        self._long_running_async_task(request_uuid, user_data),
        self._loop  # Could be None!
    )
```

**✅ Good: State-Aware Management**
```python
def trigger_async_task(self, request_uuid: str, user_data: dict = None):
    if not self._running or not self._loop:
        # Check state before using resources
        self._restart_event_loop()
    
    try:
        future = asyncio.run_coroutine_threadsafe(
            self._long_running_async_task(request_uuid, user_data),
            self._loop
        )
    except Exception as e:
        # Handle resource contention gracefully
        self._restart_event_loop()
        raise
```

### 3. **Implement Automatic Recovery**

**❌ Bad: No Recovery Mechanism**
```python
def _start_event_loop(self):
    def run_event_loop():
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        self._loop.run_forever()  # What if this fails?
```

**✅ Good: Robust Recovery**
```python
def _start_event_loop(self):
    if self._running:
        return  # Prevent multiple starts
        
    def run_event_loop():
        try:
            self._loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self._loop)
            self._running = True
            logger.info(f"Event loop started in thread {threading.current_thread().ident} for process {os.getpid()}")
            self._loop.run_forever()
        except Exception as e:
            logger.error(f"Error in event loop: {e}")
        finally:
            self._running = False

def _restart_event_loop(self):
    """Restart the event loop if it's not working properly."""
    logger.info("Restarting event loop...")
    self.shutdown()
    time.sleep(0.1)
    self._start_event_loop()
```

### 4. **Use Proper Cleanup Mechanisms**

**❌ Bad: No Cleanup**
```python
# Event loops and threads are left hanging
# Memory leaks accumulate
# Resources aren't released
```

**✅ Good: Comprehensive Cleanup**
```python
def shutdown(self):
    """Shutdown the async task manager."""
    if self._loop and self._running:
        try:
            self._loop.call_soon_threadsafe(self._loop.stop)
            self._running = False
            if self._loop_thread and self._loop_thread.is_alive():
                self._loop_thread.join(timeout=5)
            logger.info(f"AsyncTaskManager shutdown complete (PID: {os.getpid()})")
        except Exception as e:
            logger.error(f"Error during shutdown: {e}")

# Register cleanup with Flask
def cleanup():
    """Cleanup function to ensure proper shutdown of async task manager."""
    print("Shutting down async task manager...")
    async_task_manager.shutdown()

atexit.register(cleanup)
```

### 5. **Limit Resource Usage**

**❌ Bad: Unlimited Resources**
```python
# No limits on concurrent tasks
# No memory monitoring
# No timeout handling
```

**✅ Good: Resource Limits**
```python
class AsyncTaskManager:
    def __init__(self, max_concurrent_tasks=100):
        self._max_concurrent_tasks = max_concurrent_tasks
        self._active_tasks = 0
        self._semaphore = asyncio.Semaphore(max_concurrent_tasks)
    
    async def _long_running_async_task(self, request_uuid: str, user_data: dict = None):
        async with self._semaphore:  # Limit concurrent tasks
            self._active_tasks += 1
            try:
                # Add timeout to prevent infinite hanging
                await asyncio.wait_for(self._do_work(request_uuid, user_data), timeout=300)
            finally:
                self._active_tasks -= 1
```

### 6. **Use Non-Blocking I/O**

**❌ Bad: Blocking Operations in Event Loop**
```python
async def _long_running_async_task(self, request_uuid: str, user_data: dict = None):
    # This blocks the event loop!
    time.sleep(10)  # Blocking!
    
    # This also blocks!
    with open('file.txt', 'w') as f:
        f.write('data')  # Blocking I/O!
```

**✅ Good: Non-Blocking Operations**
```python
async def _long_running_async_task(self, request_uuid: str, user_data: dict = None):
    # Use asyncio.sleep instead of time.sleep
    await asyncio.sleep(10)  # Non-blocking!
    
    # Use asyncio for file I/O
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, self._write_file, 'file.txt', 'data')

def _write_file(self, filename, data):
    # This runs in a thread pool, not blocking the event loop
    with open(filename, 'w') as f:
        f.write(data)
```

### 7. **Monitor and Log Everything**

**❌ Bad: No Visibility**
```python
# No way to see what's happening
# No debugging information
# No performance metrics
```

**✅ Good: Comprehensive Monitoring**
```python
def trigger_async_task(self, request_uuid: str, user_data: dict = None):
    logger.info(f"Async task triggered for request UUID: {request_uuid} (PID: {os.getpid()})")
    
    # Log resource usage
    import psutil
    process = psutil.Process()
    logger.info(f"Memory usage: {process.memory_info().rss / 1024 / 1024:.2f} MB")
    logger.info(f"Active tasks: {self._active_tasks}")
    
    # Add timing information
    start_time = time.time()
    future = asyncio.run_coroutine_threadsafe(...)
    
    # Monitor task completion
    future.add_done_callback(
        lambda f: self._log_completion(request_uuid, start_time, f)
    )
```

## Production Recommendations

### 1. **Use a Proper Task Queue**

For production systems, consider using:
- **Celery** with Redis/RabbitMQ
- **RQ** (Redis Queue)
- **Apache Airflow**
- **Temporal**

These provide:
- Persistence across worker restarts
- Task retry mechanisms
- Distributed coordination
- Better monitoring and observability

### 2. **Gunicorn Configuration**

```python
# gunicorn.conf.py
bind = "0.0.0.0:8000"
workers = 4
worker_class = "sync"
worker_connections = 1000
timeout = 30
keepalive = 2
max_requests = 1000
max_requests_jitter = 100
preload_app = True

# Add worker lifecycle hooks
def on_starting(server):
    """Called just after the server is started."""
    pass

def on_reload(server):
    """Called to reload the server configuration."""
    pass

def worker_int(worker):
    """Called just after a worker has been initialized."""
    pass

def pre_fork(server, worker):
    """Called just before a worker has been forked."""
    pass

def post_fork(server, worker):
    """Called just after a worker has been forked."""
    pass

def post_worker_init(worker):
    """Called just after a worker has initialized the application."""
    pass

def worker_abort(worker):
    """Called when a worker received the SIGABRT signal."""
    pass
```

### 3. **Health Checks and Monitoring**

```python
@app.route('/health')
def health_check():
    """Health check endpoint that doesn't trigger async tasks."""
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.now().isoformat(),
        'pid': os.getpid(),
        'active_tasks': async_task_manager._active_tasks
    })

@app.route('/metrics')
def metrics():
    """Metrics endpoint for monitoring."""
    import psutil
    process = psutil.Process()
    
    return jsonify({
        'memory_usage_mb': process.memory_info().rss / 1024 / 1024,
        'cpu_percent': process.cpu_percent(),
        'active_tasks': async_task_manager._active_tasks,
        'event_loop_running': async_task_manager._running
    })
```

## Summary

The key to preventing event loop hanging in multi-worker environments is:

1. **Isolate resources** per worker process
2. **Implement proper state management** and recovery
3. **Use non-blocking I/O** operations
4. **Monitor and log** everything
5. **Set resource limits** and timeouts
6. **Handle cleanup** properly
7. **Consider using a proper task queue** for production

By following these best practices, you can ensure that your async tasks run reliably even in complex multi-worker environments. 