#!/bin/bash
# Wrapper script that activates venv and runs speak.py
# Usage: ./speak.sh "Hello, I am Pii-chan!"

cd "$(dirname "$0")"
source venv/bin/activate
python speak.py "$@"
