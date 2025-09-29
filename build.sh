#!/bin/bash

# Exit immediately if a command exits with a non-zero status.
set -e

python -m pip install --upgrade pip
pip install -r requirements.txt

# Run the database initialization function from main.py
python -c "from main import vercel_build; vercel_build()"