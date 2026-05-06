#!/usr/bin/env bash
# Render runs this on every deploy
set -o errexit  # exit on error

pip install -r requirements.txt

# Collect static files (CSS, JS) into /staticfiles
python manage.py collectstatic --no-input

# Apply database migrations
python manage.py migrate