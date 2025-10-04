#!/bin/bash

# Exit immediately if a command exits with a non-zero status.
set -e
# Set the FLASK_APP environment variable so the flask command knows where to find the app
export FLASK_APP=main:app
python -m flask db upgrade