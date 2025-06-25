import uuid
import time
from datetime import datetime
import os
import sys
import threading
from abc import ABC, abstractmethod

class BaseAsyncTaskManager(ABC):
    """Base class for async task managers with common functionality."""
    
    def __init__(self):
        self._running = False
        self._active_tasks = 0
    
    def _print_async(self, level: str, message: str):
        """Print method that doesn't interfere with the task execution."""
        try:
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            print(f"[{timestamp}] [{level.upper()}] {message}")
        except Exception as e:
            # If printing fails, write to stderr as fallback
            print(f"Print error: {e} - Original message: {message}", file=sys.stderr)
    
    def _execute_long_running_task(self, request_uuid: str, user_data: dict = None):
        """
        Execute the actual long-running task.
        This is the common task execution logic.
        """
        start_time = time.time()
        thread_id = getattr(threading.current_thread(), 'ident', 'unknown') if 'threading' in globals() else 'unknown'
        self._print_async('info', f"Starting async task for request UUID: {request_uuid} (PID: {os.getpid()}, Thread: {thread_id})")
        
        try:
            print(f"Starting async task for request UUID: {request_uuid} (PID: {os.getpid()})")
            # Simulate some work
            time.sleep(5)  # Simulate 5 seconds of work
            
            # Simulate some potential errors (10% chance)
            import random
            if random.random() < 0.1:
                raise Exception(f"Simulated error in async task for UUID: {request_uuid}")
            
            # Simulate more work
            time.sleep(3)
            
            # Log success
            end_time = time.time()
            duration = end_time - start_time
            self._print_async('info',
                f"Async task completed successfully for request UUID: {request_uuid} "
                f"(duration: {duration:.2f}s, PID: {os.getpid()}, Thread: {thread_id}, user_data: {user_data})"
            )
            
            return {"status": "success", "duration": duration, "uuid": request_uuid}
            
        except Exception as e:
            # Log error
            end_time = time.time()
            duration = end_time - start_time
            self._print_async('error',
                f"Async task failed for request UUID: {request_uuid} "
                f"(duration: {duration:.2f}s, PID: {os.getpid()}, Thread: {thread_id}, error: {str(e)})"
            )
            raise
    
    def _handle_task_completion(self, request_uuid: str, future_or_result):
        """Handle the completion of an async task."""
        try:
            # Handle both Future objects and direct results
            if hasattr(future_or_result, 'result'):
                result = future_or_result.result()
            else:
                result = future_or_result
            
            # Simple decrement without lock (gevent-friendly)
            self._active_tasks = max(0, self._active_tasks - 1)
            self._print_async('info', f"Task completion handled for request UUID: {request_uuid} (PID: {os.getpid()}, Active: {self._active_tasks})")
        except Exception as e:
            # Simple decrement without lock (gevent-friendly)
            self._active_tasks = max(0, self._active_tasks - 1)
            self._print_async('error', f"Task completion error for request UUID: {request_uuid} (PID: {os.getpid()}): {str(e)}")
    
    def get_status(self):
        """Get the current status of the async task manager."""
        return {
            "running": self._running,
            "active_tasks": self._active_tasks,
            "pid": os.getpid(),
            "type": self.get_manager_type()
        }
    
    @abstractmethod
    def get_manager_type(self) -> str:
        """Return the type of this async task manager."""
        pass
    
    @abstractmethod
    def trigger_async_task(self, request_uuid: str, user_data: dict = None):
        """
        Trigger an async task for the given request UUID.
        This method is non-blocking and returns immediately.
        """
        pass
    
    @abstractmethod
    def shutdown(self):
        """Shutdown the async task manager."""
        pass 