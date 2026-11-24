#!/usr/bin/env bash
# Run as the nexus service account from the checkout; never as root.
set -euo pipefail
cd "$(dirname "$0")/../.."
if [ ! -f .env ]; then
  echo 'Create /srv/nexus/.env first; see deploy/hostinger/README.md.' >&2
  exit 1
fi
if [ ! -x .venv/bin/python ]; then
  echo 'Create .venv first; see deploy/hostinger/README.md.' >&2
  exit 1
fi
.venv/bin/pip install -r requirements.txt
# Fail before migration if a production setting is missing or unsafe.
.venv/bin/python - <<'PY'
import os
from conf import settings

errors = []
if settings.DEBUG:
    errors.append('DEBUG must be False')
if not os.environ.get('SECRET_KEY') or settings.SECRET_KEY in {
    'django-insecure-dev-only-change-this-in-production', 'replace-this-with-a-long-random-secret'
} or len(settings.SECRET_KEY) < 50:
    errors.append('set a unique SECRET_KEY of at least 50 characters')
if not os.environ.get('DATABASE_URL', '').startswith(('postgres://', 'postgresql://')):
    errors.append('set DATABASE_URL to a PostgreSQL connection string')
if not os.environ.get('ALLOWED_HOSTS') or not os.environ.get('CSRF_TRUSTED_ORIGINS'):
    errors.append('set ALLOWED_HOSTS and CSRF_TRUSTED_ORIGINS for your domain')
if not settings.USE_SUPABASE_STORAGE or settings.MEDIA_STORAGE_CONFIGURATION_ERROR:
    errors.append('configure Supabase Storage: ' + (settings.MEDIA_STORAGE_CONFIGURATION_ERROR or 'USE_SUPABASE_STORAGE must be True'))
if errors:
    raise SystemExit('Deployment configuration errors:\n- ' + '\n- '.join(errors))
PY
.venv/bin/python manage.py check --deploy
.venv/bin/python manage.py collectstatic --noinput
.venv/bin/python manage.py migrate --noinput
.venv/bin/python manage.py check_file_storage
printf '\nDeployment prepared. Restart nexus.service and check its logs.\n'
