#!/bin/bash
# Exit on error and print commands for debugging
set -ex
 
echo "--- Installing dependencies ---"
pip install -r requirements.txt

echo "--- Running database migrations ---"
export PYTHONPATH="."
export FLASK_APP=main.py
python -m flask db upgrade
echo "--- Database migrations finished successfully ---"