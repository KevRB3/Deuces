#!/bin/bash
# Deuces Trading Platform - Startup Script
# Usage: bash run.sh [port]

set -e

PORT=${1:-8000}
DIR="$(cd "$(dirname "$0")" && pwd)"

echo "================================================"
echo "  DEUCES TRADING PLATFORM"
echo "================================================"
echo ""

# Check Python
if ! command -v python3 &> /dev/null; then
    echo "ERROR: python3 not found. Install Python 3.10+."
    exit 1
fi

# Install dependencies
echo "[1/3] Installing dependencies..."
pip install -q -r "$DIR/requirements.txt"

# Initialize database
echo "[2/3] Initializing database..."
python3 -c "
import sys; sys.path.insert(0, '$(dirname "$DIR")')
from trading_platform.database.engine import init_db
init_db()
print('    Database ready at: $(dirname "$DIR")/trading_platform/storage/trading_platform.db')
"

# Start server
echo "[3/3] Starting server on http://0.0.0.0:$PORT"
echo ""
echo "  Open your browser to: http://localhost:$PORT"
echo "  Press Ctrl+C to stop."
echo ""

cd "$(dirname "$DIR")"
python3 -m uvicorn trading_platform.app:app --host 0.0.0.0 --port "$PORT" --reload
