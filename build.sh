#!/bin/bash

# Exit immediately if a command exits with a non-zero status.
set -e

# Install dependencies
python3 -m pip install -r requirements.txt

# Run database migrations
python3 -m flask db upgrade