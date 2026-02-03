#!/bin/bash
# Install Python 3.11+ using pyenv (alternative to Homebrew)

echo "=== Python 3.11+ Installer (pyenv) ==="
echo

# Check if pyenv is installed
if ! command -v pyenv &> /dev/null; then
    echo "pyenv not found. Installing pyenv..."
    curl https://pyenv.run | bash
    
    # Add pyenv to shell
    echo 'export PYENV_ROOT="$HOME/.pyenv"' >> ~/.zshrc
    echo '[[ -d $PYENV_ROOT/bin ]] && export PATH="$PYENV_ROOT/bin:$PATH"' >> ~/.zshrc
    echo 'eval "$(pyenv init -)"' >> ~/.zshrc
    
    export PYENV_ROOT="$HOME/.pyenv"
    [[ -d $PYENV_ROOT/bin ]] && export PATH="$PYENV_ROOT/bin:$PATH"
    eval "$(pyenv init -)"
fi

echo "Installing Python 3.11.7 (this may take a few minutes)..."
pyenv install 3.11.7

echo
echo "Setting Python 3.11.7 as local version for this project..."
cd "$(dirname "$0")/.."
pyenv local 3.11.7

echo
echo "Creating virtual environment..."
python -m venv venv

echo
echo "Activating virtual environment..."
source venv/bin/activate

echo
echo "Installing dependencies..."
pip install --upgrade pip
pip install -r requirements.txt

echo
echo "=== Installation Complete ==="
echo "Python version:"
python --version
echo
echo "To activate in the future:"
echo "  pyenv local 3.11.7"
echo "  source venv/bin/activate"
