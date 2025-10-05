#!/bin/bash
set -e

export PYTHONPATH="."
export FLASK_APP=main.py
python3 -m flask db upgrade