# Monkey patch for gevent compatibility - MUST be at the very top
import gevent.monkey
gevent.monkey.patch_all()

from flask import Flask, jsonify, request
import uuid
import atexit
import signal
import sys
from async_task_manager import async_task_manager
from datetime import datetime
import os

app = Flask(__name__)

def cleanup():
    """Cleanup function to ensure proper shutdown of async task manager."""
    print("Shutting down async task manager...")
    async_task_manager.shutdown()

# Register cleanup function
atexit.register(cleanup)

def signal_handler(signum, frame):
    """Handle shutdown signals."""
    print(f"Received signal {signum}, shutting down...")
    cleanup()
    sys.exit(0)

# Register signal handlers
signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)

def detect_worker_class():
    if 'gevent' in sys.modules:
        return 'gevent'
    elif 'eventlet' in sys.modules:
        return 'eventlet'
    elif 'uvicorn' in sys.modules:
        return 'uvicorn'
    elif 'gunicorn' in sys.modules:
        return 'sync'
    else:
        return 'unknown'

@app.route('/hello', methods=['GET'])
def hello():
    # Generate a unique UUID for this request
    request_uuid = str(uuid.uuid4())
    
    # Collect some user data (headers, query params, etc.)
    user_data = {
        'user_agent': request.headers.get('User-Agent', 'Unknown'),
        'ip_address': request.remote_addr,
        'query_params': dict(request.args),
        'timestamp': str(uuid.uuid4().time)
    }
    
    # Trigger the async task (non-blocking)
    async_task_manager.trigger_async_task(request_uuid, user_data)
    
    # Return immediate response (not blocked by async task)
    return jsonify({
        'message': 'Hello, World!',
        'status': 'success',
        'request_uuid': request_uuid,
        'note': 'Async task triggered in background',
        'worker_info': {
            'pid': os.getpid(),
            'worker_class': detect_worker_class()
        }
    })

@app.route('/')
def index():
    # Generate a unique UUID for this request
    request_uuid = str(uuid.uuid4())
    
    # Collect some user data
    user_data = {
        'user_agent': request.headers.get('User-Agent', 'Unknown'),
        'ip_address': request.remote_addr,
        'endpoint': '/'
    }
    
    # Trigger the async task (non-blocking)
    async_task_manager.trigger_async_task(request_uuid, user_data)
    
    return jsonify({
        'message': 'Welcome to Flask Async Exploration',
        'endpoints': {
            'hello': '/hello',
            'status': '/status',
            'health': '/health'
        },
        'request_uuid': request_uuid,
        'note': 'Async task triggered in background',
        'worker_info': {
            'pid': os.getpid(),
            'worker_class': detect_worker_class()
        }
    })

@app.route('/status', methods=['GET'])
def status():
    """Endpoint to check application status without triggering async task."""
    async_status = async_task_manager.get_status()
    return jsonify({
        'status': 'running',
        'message': 'Application is running with async task manager',
        'async_task_manager': async_status,
        'async_task_manager_type': async_status.get('type', 'unknown'),
        'timestamp': datetime.now().isoformat(),
        'worker_info': {
            'pid': os.getpid(),
            'worker_class': detect_worker_class()
        }
    })

@app.route('/health', methods=['GET'])
def health():
    """Health check endpoint that doesn't trigger async tasks."""
    async_status = async_task_manager.get_status()
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.now().isoformat(),
        'pid': os.getpid(),
        'async_task_manager': async_status,
        'async_task_manager_type': async_status.get('type', 'unknown'),
        'worker_info': {
            'pid': os.getpid(),
            'worker_class': detect_worker_class()
        }
    })

if __name__ == '__main__':
    try:
        app.run(debug=True, host='0.0.0.0', port=5000)
    finally:
        # Ensure proper shutdown of async task manager
        cleanup() 