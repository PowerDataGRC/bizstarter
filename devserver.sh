#!/bin/sh
. .venv/bin/activate
export FLASK_SECRET_KEY='24c1bf8f45e5a508ff624ae87a159730ffdabf4e513e436f31b07e7edb959d79'
python -u -m flask --app main run --host=0.0.0.0 -p ${PORT:-5000} --debug