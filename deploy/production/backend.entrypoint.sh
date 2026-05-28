#!/bin/sh
set -e

echo "Applying database migrations..."
python manage.py migrate --noinput

echo "Starting supervisord..."
exec supervisord -c /app/supervisord.conf
