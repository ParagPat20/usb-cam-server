#!/bin/bash

# Get the absolute path of the project directory
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Create the activation command
VENV_ACTIVATE="source $PROJECT_DIR/venv/bin/activate"

# Check if the command already exists in .bashrc
if ! grep -q "$VENV_ACTIVATE" ~/.bashrc; then
    # Add a comment and the activation command to .bashrc
    echo "" >> ~/.bashrc
    echo "# Activate webcam virtual environment" >> ~/.bashrc
    echo "$VENV_ACTIVATE" >> ~/.bashrc
    echo "cd $PROJECT_DIR" >> ~/.bashrc
    echo "echo 'Webcam virtual environment activated!'" >> ~/.bashrc
fi

# Source .bashrc to apply changes immediately
source ~/.bashrc

echo "Terminal setup complete! The virtual environment will now activate automatically when you open a new terminal."
echo "To apply changes in current terminal, run: source ~/.bashrc" 