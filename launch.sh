#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# launch.sh  –  Download, install and run the Model Manager on Linux
#
# Usage:
#   bash <(curl -fsSL https://raw.githubusercontent.com/YOUR_USER/YOUR_REPO/main/model-manager/launch.sh)
#
# Or after cloning the repo:
#   chmod +x launch.sh && ./launch.sh
# ─────────────────────────────────────────────────────────────────────────────
set -euo pipefail

REPO_URL="https://github.com/YOUR_USER/YOUR_REPO.git"
APP_DIR="$HOME/model-manager"
PORT=9999

echo "======================================================"
echo " Model Manager – Launch Script"
echo "======================================================"

# ── 1. Clone or update the repo ───────────────────────────────────────────────
if [ -d "$APP_DIR/.git" ]; then
    echo "[1/3] Updating existing repo at $APP_DIR..."
    git -C "$APP_DIR" pull --ff-only
else
    echo "[1/3] Cloning repo into $APP_DIR..."
    git clone "$REPO_URL" "$APP_DIR"
fi

cd "$APP_DIR/model-manager"

# ── 2. Install Python dependencies ───────────────────────────────────────────
echo ""
echo "[2/3] Installing Python dependencies..."

# Prefer pip3, fall back to pip
PIP_CMD="pip3"
if ! command -v pip3 &>/dev/null; then
    PIP_CMD="pip"
fi

$PIP_CMD install -r requirements.txt --quiet

# ── 3. Launch the app ─────────────────────────────────────────────────────────
echo ""
echo "[3/3] Starting Model Manager on port $PORT..."

# Get the local IP for display
LOCAL_IP=$(hostname -I 2>/dev/null | awk '{print $1}' || echo "localhost")

echo "======================================================"
echo " App URL  : http://localhost:$PORT"
echo " Local IP : http://$LOCAL_IP:$PORT"
echo "======================================================"
echo " Press Ctrl+C to stop"
echo "======================================================"
echo ""

python3 model_manager_by_wwaa.py
