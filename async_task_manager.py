import asyncio
import uuid
import time
from datetime import datetime
import threading
import os
import sys
from concurrent.futures import ThreadPoolExecutor
import queue

# Import the async task managers from their respective files
from thread_pool_async_task_manager import ThreadPoolBasedAsyncTaskManager
from gevent_async_task_manager import GeventBasedAsyncTaskManager

# Remove logging setup and use print statements instead
print(f"AsyncTaskManager initialized for process {os.getpid()}")

class AsyncTaskManager:
    def __init__(self):
        self._loop = None
        self._loop_thread = None
        self._running = False
        self._active_tasks = 0
        # Use a simple counter instead of threading.Lock for gevent compatibility
        self._start_event_loop()
    
    def _print_async(self, level: str, message: str):
        """Print method that doesn't interfere with the event loop."""
        try:
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            print(f"[{timestamp}] [{level.upper()}] {message}")
        except Exception as e:
            # If printing fails, write to stderr as fallback
            print(f"Print error: {e} - Original message: {message}", file=sys.stderr)
    
    def _start_event_loop(self):
        """Start a dedicated event loop in a separate thread for running async tasks."""
        print(f"DEBUG: _start_event_loop called, _running={self._running}")
        
        if self._running:
            self._print_async('info', f"Event loop already running in thread '{self._loop_thread.name}' (PID: {os.getpid()}, Worker ID: {os.environ.get('GUNICORN_WORKER_ID', 'unknown')})")
            return
            
        def run_event_loop():
            try:
                print(f"DEBUG: run_event_loop started in thread {threading.current_thread().ident}")
                self._loop = asyncio.new_event_loop()
                asyncio.set_event_loop(self._loop)
                self._running = True
                self._print_async('info', f"Event loop started in thread {threading.current_thread().ident} for process {os.getpid()}")
                print(f"DEBUG: About to call run_forever()")
                
                # Add a simple test task to verify the loop is working
                async def test_task():
                    print(f"DEBUG: Test task running in event loop")
                    await asyncio.sleep(1)
                    print(f"DEBUG: Test task completed")
                
                # Schedule the test task
                self._loop.create_task(test_task())
                
                self._loop.run_forever()
                print(f"DEBUG: run_forever() returned")
            except Exception as e:
                self._print_async('error', f"Error in event loop: {e}")
                print(f"DEBUG: Event loop error: {type(e).__name__}: {e}")
                import traceback
                traceback.print_exc()
            finally:
                self._running = False
                self._print_async('info', f"Event loop stopped in thread {threading.current_thread().ident}")
                print(f"DEBUG: Event loop stopped")
        
        self._loop_thread = threading.Thread(target=run_event_loop, daemon=True)
        print(f"DEBUG: Created thread: {self._loop_thread}")
        self._loop_thread.start()
        print(f"DEBUG: Thread started, alive={self._loop_thread.is_alive()}")
        
        # Use a non-blocking wait
        import gevent
        gevent.sleep(0.1)
        print(f"DEBUG: After sleep, thread alive={self._loop_thread.is_alive()}, _running={self._running}")
    
    def trigger_async_task(self, request_uuid: str, user_data: dict = None):
        """
        Trigger an async task for the given request UUID.
        This method is non-blocking and returns immediately.
        """
        print(f"DEBUG: trigger_async_task called for UUID: {request_uuid}")
        print(f"DEBUG: _running={self._running}, _loop={self._loop}")
        
        if not self._running or not self._loop:
            self._print_async('warning', "Event loop not ready, restarting...")
            self._start_event_loop()
            import gevent
            gevent.sleep(0.1)  # Non-blocking sleep for gevent
            
            # Check again after restart
            print(f"DEBUG: After restart - _running={self._running}, _loop={self._loop}")
            if not self._running or not self._loop:
                self._print_async('error', "Event loop still not ready after restart")
                raise RuntimeError("Event loop failed to start")
        
        try:
            print(f"DEBUG: About to submit task to event loop")
            # Submit the async task to the event loop
            future = asyncio.run_coroutine_threadsafe(
                self._long_running_async_task(request_uuid, user_data),
                self._loop
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
            # Try to restart the event loop
            self._restart_event_loop()
            raise
    
    def _restart_event_loop(self):
        """Restart the event loop if it's not working properly."""
        self._print_async('info', "Restarting event loop...")
        self.shutdown()
        import gevent
        gevent.sleep(0.1)  # Non-blocking sleep
        self._start_event_loop()
    
    async def _long_running_async_task(self, request_uuid: str, user_data: dict = None):
        """
        Simulate a long-running async task.
        This is the actual async task that will run in the background.
        """
        start_time = time.time()
        self._print_async('info', f"Starting async task for request UUID: {request_uuid} (PID: {os.getpid()})")
        
        try:
            print(f"Starting async task for request UUID: {request_uuid} (PID: {os.getpid()})")
            # Simulate some async work
            await asyncio.sleep(5)  # Simulate 5 seconds of work
            
            # Simulate some potential errors (10% chance)
            import random
            if random.random() < 0.1:
                raise Exception(f"Simulated error in async task for UUID: {request_uuid}")
            
            # Simulate more async work
            await asyncio.sleep(3)
            
            # Log success using non-blocking method
            end_time = time.time()
            duration = end_time - start_time
            self._print_async('info',
                f"Async task completed successfully for request UUID: {request_uuid} "
                f"(duration: {duration:.2f}s, PID: {os.getpid()}, user_data: {user_data})"
            )
            
        except Exception as e:
            # Log error using non-blocking method
            end_time = time.time()
            duration = end_time - start_time
            self._print_async('error',
                f"Async task failed for request UUID: {request_uuid} "
                f"(duration: {duration:.2f}s, PID: {os.getpid()}, error: {str(e)})"
            )
            raise
    
    def _handle_task_completion(self, request_uuid: str, future):
        """Handle the completion of an async task."""
        try:
            result = future.result()
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
            "type": "asyncio"
        }
    
    def shutdown(self):
        """Shutdown the async task manager."""
        if self._loop and self._running:
            try:
                self._loop.call_soon_threadsafe(self._loop.stop)
                self._running = False
                if self._loop_thread and self._loop_thread.is_alive():
                    # Use non-blocking join for gevent compatibility
                    import gevent
                    gevent.spawn(self._loop_thread.join, timeout=5)
                self._print_async('info', f"AsyncTaskManager shutdown complete (PID: {os.getpid()})")
            except Exception as e:
                self._print_async('error', f"Error during shutdown: {e}")

