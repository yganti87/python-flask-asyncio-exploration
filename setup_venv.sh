#!/bin/bash

# Virtual Environment Setup Script
# This script creates and configures the virtual environment for the Flask Async Exploration project

set -e  # Exit on any error

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
RED='\033[0;31m'
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

# Function to show usage
show_usage() {
    echo "Usage: $0 [OPTIONS]"
    echo ""
    echo "Options:"
    echo "  -h, --help     Show this help message"
    echo "  -f, --force    Force recreation of virtual environment"
    echo ""
    echo "Examples:"
    echo "  $0              # Setup virtual environment"
    echo "  $0 --force      # Force recreation of virtual environment"
}

# Main execution
main() {
    echo -e "${BLUE}================================${NC}"
    echo -e "${BLUE}  Virtual Environment Setup${NC}"
    echo -e "${BLUE}================================${NC}"
    echo ""
    
    # Parse command line arguments
    FORCE_RECREATE=false
    
    while [[ $# -gt 0 ]]; do
        case $1 in
            -h|--help)
                show_usage
                exit 0
                ;;
            -f|--force)
                FORCE_RECREATE=true
                shift
                ;;
            *)
                print_error "Unknown option: $1"
                show_usage
                exit 1
                ;;
        esac
    done
    
    # Check Python version
    print_status "Checking Python version..."
    check_python_version
    
    # Handle force recreation
    if [ "$FORCE_RECREATE" = true ] && [ -d "venv" ]; then
        print_status "Removing existing virtual environment..."
        rm -rf venv
        print_success "Existing virtual environment removed"
    fi
    
    # Create virtual environment
    create_venv
    
    # Activate virtual environment
    activate_venv
    
    # Install requirements
    install_requirements
    
    echo ""
    print_success "Virtual environment setup completed successfully!"
    echo ""
    print_status "To activate the virtual environment manually:"
    if [[ "$OSTYPE" == "msys" || "$OSTYPE" == "win32" ]]; then
        echo "  source venv/Scripts/activate"
    else
        echo "  source venv/bin/activate"
    fi
    echo ""
    print_status "To start the application:"
    echo "  ./startup.sh"
    echo "  or"
    echo "  python app.py"
}

# Run main function
main "$@" 