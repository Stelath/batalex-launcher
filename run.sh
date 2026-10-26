#!/bin/sh
# Convenience launcher: uses the project venv if present.
cd "$(dirname "$0")"
if [ -x .venv/bin/python ]; then
    exec .venv/bin/python -m batalex_launcher "$@"
fi
exec python3 -m batalex_launcher "$@"
