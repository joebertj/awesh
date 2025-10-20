#!/bin/bash
# awesh launcher script

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Activate virtual environment and run awesh
cd "$SCRIPT_DIR"
source venv/bin/activate
python run_awesh.py
