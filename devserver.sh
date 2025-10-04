#!/bin/sh
. .venv/bin/activate
python -u -m flask --app main run -p ${PORT:-5000} --debug