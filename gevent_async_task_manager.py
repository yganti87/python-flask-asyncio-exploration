# Monkey patch for gevent compatibility - MUST be at the very top
import gevent.monkey
gevent.monkey.patch_all()

import gevent
from gevent.pool import Pool
import os
import sys
from base_async_task_manager import BaseAsyncTaskManager

class GeventBasedAsyncTaskManager(BaseAsyncTaskManager):
    """Async task manager using gevent greenlets for background task execution."""
    
    def __init__(self, max_workers=4):
        super().__init__()
        self._max_workers = max_workers
        self._pool = None
        self._pid = None
        self._start_gevent_pool()
    
    def get_manager_type(self) -> str:
        return "gevent"
    
    def _start_gevent_pool(self):
        """Start a gevent pool for handling async tasks."""
        current_pid = os.getpid()
        print(f"DEBUG: _start_gevent_pool called, _running={self._running}, current_pid={current_pid}, _pid={self._pid}")
        
        # Check if we're in a new process (forked from master)
        if self._pid is not None and self._pid != current_pid:
            print(f"DEBUG: Process changed from {self._pid} to {current_pid}, reinitializing pool")
            self._running = False
            self._pool = None
        
        print(f"DEBUG: _running={self._running}, _pool={self._pool}")
        if self._running:
            self._print_async('info', f"Gevent pool already running (PID: {current_pid})")
        else:
            try:
                print(f"DEBUG: Creating gevent pool with {self._max_workers} workers (PID: {current_pid})")
                self._pool = Pool()
                self._running = True
                self._pid = current_pid
                self._print_async('info', f"Gevent pool started with {self._max_workers} workers (PID: {current_pid})")
                print(f"DEBUG: Gevent pool created: {self._pool}")
            except Exception as e:
                self._print_async('error', f"Failed to start gevent pool: {e}")
                print(f"DEBUG: Gevent pool error: {type(e).__name__}: {e}")
                import traceback
                traceback.print_exc()
                raise
    
    def trigger_async_task(self, request_uuid: str, user_data: dict = None):
        """
        Trigger an async task for the given request UUID.
        This method is non-blocking and returns immediately.
        """
        current_pid = os.getpid()
        print(f"DEBUG: trigger_async_task called for UUID: {request_uuid} (PID: {current_pid})")
        print(f"DEBUG: _running={self._running}, _pool={self._pool}, _pid={self._pid}, current_pid={current_pid}")
        
        
        try:
            print(f"DEBUG: About to submit task to gevent pool (PID: {current_pid})")
            # Submit the task to the gevent pool
            greenlet = self._pool.spawn(
                self._execute_long_running_task,
                request_uuid,
                user_data
            )
            print(f"DEBUG: Task submitted successfully, greenlet: {greenlet} (PID: {current_pid})")
            
            # Add a callback to handle task completion
            greenlet.link(lambda g: self._handle_task_completion(request_uuid, g))
            print(f"DEBUG: Callback added successfully (PID: {current_pid})")
            
            # Simple increment without lock (gevent-friendly)
            self._active_tasks += 1
            
            self._print_async('info', f"Async task triggered for request UUID: {request_uuid} (PID: {current_pid}, Active: {self._active_tasks})")
            return request_uuid
        except Exception as e:
            self._print_async('error', f"Failed to trigger async task for UUID {request_uuid}: {e}")
            print(f"DEBUG: Exception details: {type(e).__name__}: {e} (PID: {current_pid})")
            import traceback
            traceback.print_exc()
            raise
    
    def _restart_gevent_pool(self):
        """Restart the gevent pool if it's not working properly."""
        current_pid = os.getpid()
        self._print_async('info', "Restarting gevent pool...")
        self.shutdown()
        gevent.sleep(0.1)  # Non-blocking sleep
        print(f"DEBUG: Restarting gevent pool (PID: {current_pid})")
        self._start_gevent_pool()
    
    def _handle_task_completion(self, request_uuid: str, greenlet):
        """Handle the completion of an async task."""
        current_pid = os.getpid()
        try:
            # For gevent greenlets, we need to handle the result differently
            if greenlet.successful():
                result = greenlet.value
            else:
                # If the greenlet failed, get the exception
                result = greenlet.exception
            
            # Simple decrement without lock (gevent-friendly)
            self._active_tasks = max(0, self._active_tasks - 1)
            self._print_async('info', f"Task completion handled for request UUID: {request_uuid} (PID: {current_pid}, Active: {self._active_tasks})")
        except Exception as e:
            # Simple decrement without lock (gevent-friendly)
            self._active_tasks = max(0, self._active_tasks - 1)
            self._print_async('error', f"Task completion error for request UUID: {request_uuid} (PID: {current_pid}): {str(e)}")
    
    def get_status(self):
        """Get the current status of the async task manager."""
        status = super().get_status()
        status["max_workers"] = self._max_workers
        return status
    
    def shutdown(self):
        """Shutdown the async task manager."""
        current_pid = os.getpid()
        if self._running and self._pool:
            try:
                self._print_async('info', f"Shutting down gevent pool (PID: {current_pid}, Active tasks: {self._active_tasks})")
                self._running = False
                
                # Kill all greenlets in the pool
                self._pool.kill()
                
                self._print_async('info', f"GeventBasedAsyncTaskManager shutdown complete (PID: {current_pid})")
            except Exception as e:
                self._print_async('error', f"Error during shutdown: {e}") 