#!/bin/bash

# Flask Async Exploration - Startup Script
# This script sets up the virtual environment, installs dependencies, and starts the application

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Function to check if command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Function to check Python version
check_python_version() {
    if command_exists python3; then
        PYTHON_VERSION=$(python3 --version 2>&1 | awk '{print $2}' | cut -d. -f1,2)
        REQUIRED_VERSION="3.8"
        
        if [ "$(printf '%s\n' "$REQUIRED_VERSION" "$PYTHON_VERSION" | sort -V | head -n1)" = "$REQUIRED_VERSION" ]; then
            print_success "Python version $PYTHON_VERSION is compatible"
            PYTHON_CMD="python3"
        else
            print_error "Python version $PYTHON_VERSION is too old. Required: $REQUIRED_VERSION or higher"
            exit 1
        fi
    elif command_exists python; then
        PYTHON_VERSION=$(python --version 2>&1 | awk '{print $2}' | cut -d. -f1,2)
        REQUIRED_VERSION="3.8"
        
        if [ "$(printf '%s\n' "$REQUIRED_VERSION" "$PYTHON_VERSION" | sort -V | head -n1)" = "$REQUIRED_VERSION" ]; then
            print_success "Python version $PYTHON_VERSION is compatible"
            PYTHON_CMD="python"
        else
            print_error "Python version $PYTHON_VERSION is too old. Required: $REQUIRED_VERSION or higher"
            exit 1
        fi
    else
        print_error "Python 3.8+ is required but not found"
        exit 1
    fi
}

# Function to create virtual environment
create_venv() {
    if [ ! -d "venv" ]; then
        print_status "Creating virtual environment..."
        $PYTHON_CMD -m venv venv
        print_success "Virtual environment created"
    else
        print_warning "Virtual environment already exists"
    fi
}

# Function to activate virtual environment
activate_venv() {
    print_status "Activating virtual environment..."
    
    if [[ "$OSTYPE" == "msys" || "$OSTYPE" == "win32" ]]; then
        # Windows
        source venv/Scripts/activate
    else
        # Unix/Linux/macOS
        source venv/bin/activate
    fi
    
    print_success "Virtual environment activated"
}

# Function to install requirements
install_requirements() {
    print_status "Installing requirements..."
    
    # Determine the correct pip path based on OS
    if [[ "$OSTYPE" == "msys" || "$OSTYPE" == "win32" ]]; then
        # Windows
        PIP_CMD="venv/Scripts/pip"
    else
        # Unix/Linux/macOS
        PIP_CMD="venv/bin/pip"
    fi
    
    # Check if pip exists in the virtual environment
    if [ ! -f "$PIP_CMD" ]; then
        print_error "pip not found in virtual environment at $PIP_CMD"
        print_status "Trying to install pip in the virtual environment..."
        
        # Try to install pip using python -m pip
        if [[ "$OSTYPE" == "msys" || "$OSTYPE" == "win32" ]]; then
            venv/Scripts/python -m ensurepip --upgrade
        else
            venv/bin/python -m ensurepip --upgrade
        fi
    fi
    
    # Upgrade pip first
    print_status "Upgrading pip..."
    $PIP_CMD install --upgrade pip
    
    # Install requirements
    if [ -f "requirements.txt" ]; then
        print_status "Installing packages from requirements.txt..."
        $PIP_CMD install -r requirements.txt
        print_success "Requirements installed"
    else
        print_error "requirements.txt not found"
        exit 1
    fi
}

# Function to check if port is available
check_port() {
    local port=$1
    if lsof -Pi :$port -sTCP:LISTEN -t >/dev/null 2>&1; then
        print_warning "Port $port is already in use"
        return 1
    else
        print_success "Port $port is available"
        return 0
    fi
}

# Function to start the application
start_application() {
    print_status "Starting Flask application..."
    
    # Check if gunicorn is available
    if command_exists gunicorn; then
        print_status "Using gunicorn for production deployment"
        
        # Check if port 8000 is available
        if check_port 8000; then
            print_status "Starting gunicorn server on port 8000..."
            echo -e "${GREEN}Application will be available at: http://localhost:8000${NC}"
            echo -e "${YELLOW}Press Ctrl+C to stop the server${NC}"
            echo ""
            
            # Start gunicorn
            gunicorn -c gunicorn.conf.py app:app
        else
            print_error "Port 8000 is not available. Please stop the process using port 8000 or modify gunicorn.conf.py"
            exit 1
        fi
    else
        print_warning "Gunicorn not found, using Flask development server"
        
        # Check if port 5000 is available
        if check_port 5000; then
            print_status "Starting Flask development server on port 5000..."
            echo -e "${GREEN}Application will be available at: http://localhost:5000${NC}"
            echo -e "${YELLOW}Press Ctrl+C to stop the server${NC}"
            echo ""
            
            # Start Flask development server
            python app.py
        else
            print_error "Port 5000 is not available. Please stop the process using port 5000"
            exit 1
        fi
    fi
}

# Function to show usage
show_usage() {
    echo "Usage: $0 [OPTIONS]"
    echo ""
    echo "Options:"
    echo "  -h, --help     Show this help message"
    echo "  -d, --dev      Start in development mode (Flask dev server)"
    echo "  -p, --prod     Start in production mode (gunicorn)"
    echo "  -s, --setup    Only setup environment, don't start server"
    echo ""
    echo "Examples:"
    echo "  $0              # Auto-detect best mode and start"
    echo "  $0 --dev        # Force development mode"
    echo "  $0 --prod       # Force production mode"
    echo "  $0 --setup      # Only setup environment"
}

# Function to cleanup on exit
cleanup() {
    print_status "Shutting down..."
    # Add any cleanup code here if needed
}

# Set up trap for cleanup
trap cleanup EXIT

# Parse command line arguments
DEV_MODE=false
PROD_MODE=false
SETUP_ONLY=false

while [[ $# -gt 0 ]]; do
    case $1 in
        -h|--help)
            show_usage
            exit 0
            ;;
        -d|--dev)
            DEV_MODE=true
            shift
            ;;
        -p|--prod)
            PROD_MODE=true
            shift
            ;;
        -s|--setup)
            SETUP_ONLY=true
            shift
            ;;
        *)
            print_error "Unknown option: $1"
            show_usage
            exit 1
            ;;
    esac
done

# Main execution
main() {
    echo -e "${BLUE}================================${NC}"
    echo -e "${BLUE}  Flask Async Exploration${NC}"
    echo -e "${BLUE}  Startup Script${NC}"
    echo -e "${BLUE}================================${NC}"
    echo ""
    
    # Check Python version
    print_status "Checking Python version..."
    check_python_version
    
    # Create virtual environment
    create_venv
    
    # Activate virtual environment
    activate_venv
    
    # Install requirements
    install_requirements
    
    if [ "$SETUP_ONLY" = true ]; then
        print_success "Setup completed successfully!"
        print_status "To start the application, run: $0"
        exit 0
    fi
    
    # Start application based on mode
    if [ "$DEV_MODE" = true ]; then
        print_status "Starting in development mode..."
        if check_port 5000; then
            python app.py
        else
            print_error "Port 5000 is not available"
            exit 1
        fi
    elif [ "$PROD_MODE" = true ]; then
        print_status "Starting in production mode..."
        if check_port 8000; then
            gunicorn -c gunicorn.conf.py app:app
        else
            print_error "Port 8000 is not available"
            exit 1
        fi
    else
        # Auto-detect mode
        start_application
    fi
}

# Run main function
main "$@"
