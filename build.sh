#!/usr/bin/env bash
# Render build script: installs deps, builds static assets, applies migrations.
set -o errexit

pip install -r requirements.txt

python manage.py collectstatic --noinput
python manage.py migrate

# Create (or refresh) an admin account from DJANGO_SUPERUSER_* env vars.
# No-ops safely if those variables aren't set. Render's free web-service
# tier has no shell access, so this is how the first admin gets created.
python manage.py bootstrap_admin
