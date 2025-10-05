#!/bin/sh
. .venv/bin/activate
export FLASK_SECRET_KEY='a_default_secret_key_for_development_only'
python -u -m flask --app main run --host=0.0.0.0 -p ${PORT:-5000} --debug