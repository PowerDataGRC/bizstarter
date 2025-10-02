#!/bin/bash

# Exit immediately if a command exits with a non-zero status.
set -e

# Install dependencies
python3 -m pip install -r requirements.txt

# Run database migrations
# The 'db upgrade' command should be run manually against your production database.
# It is removed from the build script to prevent build failures.