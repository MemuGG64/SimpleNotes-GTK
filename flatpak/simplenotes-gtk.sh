#!/usr/bin/env bash
export PYTHONPATH=/app/src:${PYTHONPATH}
exec /usr/bin/python3 /app/SimpleNotes.py "$@"
