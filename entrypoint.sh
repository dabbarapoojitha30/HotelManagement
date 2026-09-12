#!/bin/sh
set -e

# Support passing custom port as first argument (e.g. docker run ... hotel-management 5000)
if [ "$1" ] && [ -z "${1##[0-9]*}" ]; then
    PORT="$1"
    shift
fi

# Fallback to $PORT env var, or default to 8000
PORT="${PORT:-8000}"

echo "============================================================"
echo "Starting VV Residency Hotel Management on port: ${PORT}"
echo "============================================================"

# Execute Uvicorn in the backend directory
exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT}" "$@"
