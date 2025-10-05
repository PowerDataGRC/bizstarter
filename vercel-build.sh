#!/bin/bash
set -e

export PYTHONPATH="."
export FLASK_APP=main:app
flask db upgrade