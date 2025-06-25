from enum import Enum
import os
from gevent_async_task_manager import GeventBasedAsyncTaskManager
from thread_pool_async_task_manager import ThreadPoolBasedAsyncTaskManager
from async_task_manager import AsyncTaskManager

class TaskManagerType(Enum):
    GEVENT = "gevent"
    THREAD_POOL = "thread_pool"
    ASYNCIO = "asyncio"

class AsyncTaskManagerFactory:
    """Factory for creating different types of async task managers."""
    
    _instances = {}  # Process-specific instances
    _task_managers = {}  # Process-specific task managers
    
    @classmethod
    def get_instance(cls):
        """Get the singleton instance of the factory for the current process."""
        pid = os.getpid()
        print(f"DEBUG: get_instance called, pid={pid}")
        print(f"DEBUG: _instances={cls._instances}")
        if pid not in cls._instances:
            cls._instances[pid] = cls()
        return cls._instances[pid]
    
    def __init__(self):
        # Don't create task manager in __init__ - create it lazily
        self._task_manager = None
        self._manager_type = TaskManagerType.GEVENT  # Default to thread pool
    
    def get_task_manager(self):
        """Get the current task manager instance, creating it if necessary."""
        pid = os.getpid()
        print(f"DEBUG: get_task_manager called, pid={pid}")
        print(f"DEBUG: _task_managers={self._task_managers}")
        if pid not in self._task_managers:
            print(f"DEBUG: Creating new task manager for PID {pid}")
            self._task_managers[pid] = self.create_task_manager(self._manager_type)
        return self._task_managers[pid]
    
    def set_task_manager(self, manager_type: TaskManagerType = TaskManagerType.GEVENT, **kwargs):
        """Set a new task manager instance."""
        pid = os.getpid()
        
        # Shutdown existing task manager if it exists
        if pid in self._task_managers and self._task_managers[pid]:
            self._task_managers[pid].shutdown()
        
        # Create new task manager
        self._manager_type = manager_type
        self._task_managers[pid] = self.create_task_manager(manager_type, **kwargs)
        print(f"DEBUG: Set new task manager for PID {pid}: {manager_type.value}")
        return self._task_managers[pid]
    
    @staticmethod
    def create_task_manager(manager_type: TaskManagerType = TaskManagerType.GEVENT, **kwargs):
        """
        Create and return an async task manager of the specified type.
        
        Args:
            manager_type: Type of task manager to create (default: GEVENT)
            **kwargs: Additional arguments to pass to the task manager constructor
            
        Returns:
            An instance of the specified async task manager
        """
        print(f"DEBUG: Creating task manager of type: {manager_type.value}")
        if manager_type == TaskManagerType.GEVENT:
            return GeventBasedAsyncTaskManager(**kwargs)
        elif manager_type == TaskManagerType.THREAD_POOL:
            return ThreadPoolBasedAsyncTaskManager(**kwargs)
        elif manager_type == TaskManagerType.ASYNCIO:
            return AsyncTaskManager(**kwargs)
        else:
            raise ValueError(f"Unknown task manager type: {manager_type}")
    
    @staticmethod
    def create_task_manager_by_name(manager_name: str, **kwargs):
        """
        Create and return an async task manager by name.
        
        Args:
            manager_name: Name of the task manager ("gevent", "thread_pool", "asyncio")
            **kwargs: Additional arguments to pass to the task manager constructor
            
        Returns:
            An instance of the specified async task manager
        """
        try:
            manager_type = TaskManagerType(manager_name.lower())
            return AsyncTaskManagerFactory.create_task_manager(manager_type, **kwargs)
        except ValueError:
            raise ValueError(f"Unknown task manager name: {manager_name}. Available types: {[t.value for t in TaskManagerType]}")
    
    def __getattr__(self, name):
        """Delegate attribute access to the task manager instance."""
        task_manager = self.get_task_manager()
        return getattr(task_manager, name)
    
    def shutdown(self):
        """Shutdown all task managers for the current process."""
        pid = os.getpid()
        if pid in self._task_managers and self._task_managers[pid]:
            print(f"DEBUG: Shutting down task manager for PID {pid}")
            self._task_managers[pid].shutdown()
            del self._task_managers[pid]

# Don't create a global instance - let each worker create its own
# The factory will be accessed through get_instance() when needed 