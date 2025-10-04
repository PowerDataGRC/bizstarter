#!/bin/bash

# Exit immediately if a command exits with a non-zero status.
set -e

# Directly invoke the migration using a python script to ensure context
python -c "from flask_migrate import upgrade; from main import app; app.app_context().push(); upgrade()"