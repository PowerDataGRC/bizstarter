#!/bin/bash
set -e

export FLASK_APP=main:app
python3 -m flask db upgrade