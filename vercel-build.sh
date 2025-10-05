#!/bin/bash
set -e

export FLASK_APP=main:app
flask db upgrade