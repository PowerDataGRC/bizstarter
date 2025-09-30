#!/bin/bash

# Exit immediately if a command exits with a non-zero status.
set -e

python3 -m pip install --upgrade pip
python3 -m pip install -r requirements.txt

# Run the database initialization function from main.py
python3 -c "from main import vercel_build; vercel_build()"
