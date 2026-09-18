#!/usr/bin/env bash
# Render build script: installs deps, builds static assets, applies migrations.
set -o errexit

pip install -r requirements.txt

python manage.py collectstatic --noinput
python manage.py migrate

# Report the Supabase Storage settings in the build log. Render's free tier has
# no Shell tab, so a malformed endpoint/bucket/key would otherwise only show up
# when an administrator tries to upload. This is config-only (no network calls)
# and never fails the build: uploads stay blocked until the values are fixed.
# On a local checkout or a paid plan, run the full live check instead:
#   python manage.py check_file_storage
python manage.py check_file_storage --config-only || true

# Create (or refresh) an admin account from DJANGO_SUPERUSER_* env vars.
# No-ops safely if those variables aren't set. Render's free web-service
# tier has no shell access, so this is how the first admin gets created.
python manage.py bootstrap_admin
