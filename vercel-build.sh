#!/bin/bash

# Exit immediately if a command exits with a non-zero status.
set -e
# Add the project root to the python path and run the migration
export PYTHONPATH=.
export FLASK_APP=main.py
flask db upgrade