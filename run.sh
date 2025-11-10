#!/bin/sh

# load .env if exists
if [ -f .env ]; then
    export $(grep -v '^#' .env | xargs)
fi

# workers
WORKERS=$(( $(nproc) * 2 ))

gunicorn main:app -k uvicorn.workers.UvicornWorker --workers $WORKERS --bind ${HOST:-0.0.0.0}:${PORT:-5000} --timeout 300