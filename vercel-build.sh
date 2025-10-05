#!/bin/bash
# Exit on error and print commands for debugging
set -ex
 
echo "--- Running database migrations ---"
export PYTHONPATH="."
export FLASK_APP=main.py
python3 -m flask db upgrade
echo "--- Database migrations finished successfully ---"