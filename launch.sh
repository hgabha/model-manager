#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="$SCRIPT_DIR/venv"
PORT=9999

cd "$SCRIPT_DIR"

# Create venv if it doesn't exist
if [ ! -f "$VENV_DIR/bin/python" ]; then
    echo "Setting up virtual environment..."
    python3 -m venv "$VENV_DIR"
fi

# Activate venv
source "$VENV_DIR/bin/activate"

# Install/upgrade dependencies
echo "Checking dependencies..."
pip install -q -r requirements.txt

# Open browser after a short delay (runs in background)
(sleep 2 && xdg-open "http://localhost:$PORT" 2>/dev/null || open "http://localhost:$PORT" 2>/dev/null || true) &

echo "Starting Model Manager on http://localhost:$PORT"
echo "Press Ctrl+C to stop."
echo
python model_manager_by_wwaa.py
