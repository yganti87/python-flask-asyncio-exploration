import uuid
import time
from datetime import datetime
import threading
import os
import sys
from concurrent.futures import ThreadPoolExecutor
from base_async_task_manager import BaseAsyncTaskManager

class ThreadPoolBasedAsyncTaskManager(BaseAsyncTaskManager):
    def __init__(self, max_workers=4):
        super().__init__()
        self._executor = None
        self._max_workers = max_workers
        self._start_thread_pool()
    
    def get_manager_type(self) -> str:
        return "thread_pool"
    
    def _start_thread_pool(self):
        """Start a thread pool for handling async tasks."""
        print(f"DEBUG: _start_thread_pool called, _running={self._running}")
        
        if self._running:
            self._print_async('info', f"Thread pool already running (PID: {os.getpid()})")
            return
            
        try:
            self._executor = ThreadPoolExecutor(
                max_workers=self._max_workers,
                thread_name_prefix=f"AsyncWorker-{os.getpid()}"
            )
            self._running = True
            self._print_async('info', f"Thread pool started with {self._max_workers} workers (PID: {os.getpid()})")
            print(f"DEBUG: Thread pool created: {self._executor}")
        except Exception as e:
            self._print_async('error', f"Failed to start thread pool: {e}")
            print(f"DEBUG: Thread pool error: {type(e).__name__}: {e}")
            import traceback
            traceback.print_exc()
            raise
    
    def trigger_async_task(self, request_uuid: str, user_data: dict = None):
        """
        Trigger an async task for the given request UUID.
        This method is non-blocking and returns immediately.
        """
        print(f"DEBUG: trigger_async_task called for UUID: {request_uuid}")
        print(f"DEBUG: _running={self._running}, _executor={self._executor}")
        
        if not self._running or not self._executor:
            self._print_async('warning', "Thread pool not ready, restarting...")
            self._start_thread_pool()
            
            # Check again after restart
            print(f"DEBUG: After restart - _running={self._running}, _executor={self._executor}")
            if not self._running or not self._executor:
                self._print_async('error', "Thread pool still not ready after restart")
                raise RuntimeError("Thread pool failed to start")
        
        try:
            print(f"DEBUG: About to submit task to thread pool")
            # Submit the task to the thread pool
            future = self._executor.submit(
                self._execute_long_running_task,
                request_uuid,
                user_data
            )
            print(f"DEBUG: Task submitted successfully, future: {future}")
            
            # Add a callback to handle task completion
            future.add_done_callback(
                lambda f: self._handle_task_completion(request_uuid, f)
            )
            print(f"DEBUG: Callback added successfully")
            
            # Simple increment without lock (gevent-friendly)
            self._active_tasks += 1
            
            self._print_async('info', f"Async task triggered for request UUID: {request_uuid} (PID: {os.getpid()}, Active: {self._active_tasks})")
            return request_uuid
        except Exception as e:
            self._print_async('error', f"Failed to trigger async task for UUID {request_uuid}: {e}")
            print(f"DEBUG: Exception details: {type(e).__name__}: {e}")
            import traceback
            traceback.print_exc()
            # Try to restart the thread pool
            self._restart_thread_pool()
            raise
    
    def _restart_thread_pool(self):
        """Restart the thread pool if it's not working properly."""
        self._print_async('info', "Restarting thread pool...")
        self.shutdown()
        time.sleep(0.1)  # Regular sleep since we're using thread pool
        self._start_thread_pool()
    
    def get_status(self):
        """Get the current status of the async task manager."""
        status = super().get_status()
        status["max_workers"] = self._max_workers
        return status
    
    def shutdown(self):
        """Shutdown the async task manager."""
        if self._running and self._executor:
            try:
                self._print_async('info', f"Shutting down thread pool (PID: {os.getpid()}, Active tasks: {self._active_tasks})")
                self._running = False
                
                # Shutdown executor gracefully
                self._executor.shutdown(wait=True)
                
                self._print_async('info', f"ThreadPoolBasedAsyncTaskManager shutdown complete (PID: {os.getpid()})")
            except Exception as e:
                self._print_async('error', f"Error during shutdown: {e}") 