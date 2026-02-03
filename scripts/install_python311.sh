#!/bin/bash
# Install Python 3.11+ on macOS

echo "=== Python 3.11+ Installer ==="
echo

# Check current Python version
echo "Current Python version:"
python3 --version
echo

# Check if Homebrew is installed
if ! command -v brew &> /dev/null; then
    echo "Homebrew not found. Installing Homebrew first..."
    /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
    
    # Add Homebrew to PATH for Apple Silicon Macs
    if [[ $(uname -m) == "arm64" ]]; then
        echo 'eval "$(/opt/homebrew/bin/brew shellenv)"' >> ~/.zprofile
        eval "$(/opt/homebrew/bin/brew shellenv)"
    fi
fi

echo "Installing Python 3.11 via Homebrew..."
brew install python@3.11

echo
echo "Adding Python 3.11 to PATH..."
if [[ $(uname -m) == "arm64" ]]; then
    # Apple Silicon
    echo 'export PATH="/opt/homebrew/opt/python@3.11/libexec/bin:$PATH"' >> ~/.zshrc
    export PATH="/opt/homebrew/opt/python@3.11/libexec/bin:$PATH"
else
    # Intel
    echo 'export PATH="/usr/local/opt/python@3.11/libexec/bin:$PATH"' >> ~/.zshrc
    export PATH="/usr/local/opt/python@3.11/libexec/bin:$PATH"
fi

echo
echo "Python 3.11 installed!"
python3.11 --version

echo
echo "Creating virtual environment for job-applier..."
cd "$(dirname "$0")/.."
python3.11 -m venv venv

echo
echo "Activating virtual environment..."
source venv/bin/activate

echo
echo "Installing dependencies..."
pip install --upgrade pip
pip install -r requirements.txt

echo
echo "=== Installation Complete ==="
echo "To activate the virtual environment in the future, run:"
echo "  source venv/bin/activate"
echo
echo "New Python version:"
python --version
