# Flask Async Exploration

A Flask application with gunicorn that demonstrates background async task execution for each incoming request.

## Quick Start

### Option 1: Automated Setup (Recommended)

**On macOS/Linux:**
```bash
./startup.sh
```

**On Windows:**
```cmd
startup.bat
```

The startup script will:
- ✅ Check Python version compatibility
- ✅ Create virtual environment
- ✅ Install all dependencies
- ✅ Start the application automatically
- 🚀 Application will be available at `http://localhost:8000` (production) or `http://localhost:5000` (development)

### Option 2: Manual Setup

See the [Setup](#setup) section below for manual installation steps.

## Features

- **Background Async Tasks**: Every request triggers a long-running async task that runs in the background
- **Non-blocking Responses**: User responses are returned immediately without waiting for async tasks
- **UUID Tracking**: Each request gets a unique UUID for tracking async task execution
- **Comprehensive Logging**: All async task events are logged to both console and file
- **Error Handling**: Async task errors are logged but don't affect the main response

## Setup

1. Create and activate virtual environment:
```bash
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

## Running the Application

### Development Mode
```bash
python app.py
```
The application will be available at `http://localhost:5000`

### Production Mode with Gunicorn
```bash
gunicorn -c gunicorn.conf.py app:app
```
The application will be available at `http://localhost:8000`

### Using Startup Scripts

**Startup Options:**
```bash
./startup.sh              # Auto-detect best mode and start
./startup.sh --dev        # Force development mode
./startup.sh --prod       # Force production mode
./startup.sh --setup      # Only setup environment, don't start server
```

## Endpoints

- `GET /` - Welcome message and available endpoints (triggers async task)
- `GET /hello` - Returns a hello message (triggers async task)
- `GET /status` - Application status check (no async task)

## Async Task Details

### What happens on each request:
1. A unique UUID is generated for the request
2. User data is collected (IP, User-Agent, query params, etc.)
3. An async task is triggered in the background (non-blocking)
4. The response is returned immediately with the request UUID
5. The async task runs for ~8 seconds (simulated work)
6. Task completion/errors are logged with the UUID

### Async Task Simulation:
- **Duration**: ~8 seconds total (5s + 3s with sleep)
- **Error Rate**: 10% chance of simulated error
- **Logging**: All events logged to `async_tasks.log` and console
- **Threading**: Uses dedicated event loop in separate thread

## Testing

You can test the endpoints using curl:

```bash
# Test the root endpoint (triggers async task)
curl http://localhost:8000/

# Test the hello endpoint (triggers async task)
curl http://localhost:8000/hello

# Test status endpoint (no async task)
curl http://localhost:8000/status
```

## Monitoring

Check the logs to see async task execution:

```bash
# View real-time logs
tail -f async_tasks.log

# View recent logs
cat async_tasks.log
```

## Architecture

- **AsyncTaskManager**: Handles async task execution in background threads
- **Event Loop**: Dedicated asyncio event loop in separate thread
- **ThreadPoolExecutor**: Manages concurrent task execution
- **Logging**: Comprehensive logging with file and console output 