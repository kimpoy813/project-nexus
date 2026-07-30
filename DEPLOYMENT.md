# NExUS Deployment Guide: PostgreSQL + Supabase Storage

This project should use **PostgreSQL for database records** and **Supabase Storage for uploaded files** in production.

## 0. Quick start: Render + Supabase

This is the fastest path to a live, publicly reachable deployment. The repo already
ships `render.yaml` and `build.sh` for this.

1. **Create a Supabase project** at [supabase.com](https://supabase.com) (free tier is fine
   to start). You'll use it for both the Postgres database and file storage.
2. **Get the database connection string:** Supabase dashboard → **Project Settings → Database
   → Connection string**. Render's outbound network is IPv4-only, and Supabase's *direct*
   connection is IPv6-only unless you pay for the IPv4 add-on — so copy the **Session pooler**
   connection string (port `5432`), not the "Direct connection" one. It looks like:
   `postgresql://postgres.xxxx:PASSWORD@aws-0-region.pooler.supabase.com:5432/postgres`.
3. **Create a Storage bucket** (e.g. `nexus-media`) — see section 3 below — and grab your S3
   access keys.
4. **Push this repo to your own GitHub account** if you haven't already (Render deploys from
   a repo you control).
5. On [Render](https://render.com), click **New → Blueprint**, point it at your repo, and it
   will read `render.yaml` automatically. Render will prompt you to fill in the variables
   marked `sync: false` — that's where you paste the Supabase connection string and keys from
   steps 2–3, plus your domain and the `DJANGO_SUPERUSER_*` values described in section 2.
6. Click **Apply**. Render runs `build.sh`, which installs dependencies, collects static
   files, runs migrations, and — because you set `DJANGO_SUPERUSER_*` — creates your first
   admin account automatically. This matters because **Render's free web-service tier has no
   shell access**, so there's no interactive `createsuperuser` step available after deploy.
7. Once the deploy is live, log in at `https://your-service.onrender.com/login/` with the
   `DJANGO_SUPERUSER_USERNAME` / `DJANGO_SUPERUSER_PASSWORD` you set, then rotate that password
   from the admin dashboard.

Notes specific to Render's free tier:
- The instance **spins down after 15 minutes of inactivity** and takes ~30–60s to wake up on
  the next request — expected, not a bug.
- Its filesystem is **ephemeral**: anything not in Postgres or Supabase Storage (e.g. a local
  `db.sqlite3` or `media/` folder) is wiped on every redeploy/restart. This is exactly why
  production must use `DATABASE_URL` (Postgres) and `USE_SUPABASE_STORAGE=True` — never the
  local defaults.
- There's no SSH/Shell tab on the free tier, so any one-off admin task (creating more admins,
  fixing data) has to go through the app's own admin dashboard/Django admin, not the command
  line. `manage.py bootstrap_admin` (see below) exists specifically to work around this for the
  *first* account.

## 1. Install dependencies

Local setup:

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

On a hosting provider, the platform should run:

```bash
pip install -r requirements.txt
```

## 2. PostgreSQL database

Create a PostgreSQL database on your host or Supabase. Set the connection string as:

```env
DATABASE_URL=postgresql://USER:PASSWORD@HOST:5432/DBNAME
```

Run migrations:

```bash
python manage.py migrate
```

If starting fresh, create an admin account. If you have shell access (local dev, or a paid
Render/other plan), the interactive command works as usual:

```bash
python manage.py createsuperuser
```

If you don't have shell access after deploy (e.g. Render's free tier), use the non-interactive
`bootstrap_admin` management command instead, driven by environment variables. It's already
wired into `build.sh`, so simply setting these three variables on your host is enough — the
account is created automatically on the next deploy:

```env
DJANGO_SUPERUSER_USERNAME=your-admin-username
DJANGO_SUPERUSER_EMAIL=you@example.com
DJANGO_SUPERUSER_PASSWORD=a-strong-password
```

`bootstrap_admin` is idempotent: if the user already exists it leaves it untouched by default.
To force-reset an existing account's password/role on the next deploy, also set
`DJANGO_SUPERUSER_UPDATE_EXISTING=True` (or pass `--update-existing` when running it by hand),
then unset it again afterwards. Once you can log in, prefer rotating credentials through the
admin dashboard rather than leaving superuser passwords in host environment variables long-term.

## 3. Supabase Storage for uploaded files

PostgreSQL is not used for file uploads. Uploaded files should go to Supabase Storage.

In Supabase:

1. Create a project.
2. Go to **Storage**.
3. Create a bucket, for example: `nexus-media`.
4. If files should be directly viewable through generated links, make the bucket public or configure suitable policies.
5. Go to Supabase S3 settings and create S3 access keys.
6. Add these environment variables to your host:

```env
USE_SUPABASE_STORAGE=True
SUPABASE_STORAGE_BUCKET=nexus-media
SUPABASE_S3_ENDPOINT_URL=https://PROJECT_REF.supabase.co/storage/v1/s3
SUPABASE_S3_ACCESS_KEY_ID=your-access-key
SUPABASE_S3_SECRET_ACCESS_KEY=your-secret-key
SUPABASE_S3_REGION_NAME=us-east-1
SUPABASE_STORAGE_PUBLIC_URL=https://PROJECT_REF.supabase.co/storage/v1/object/public/nexus-media
```

The project uses `django-storages` with Supabase's S3-compatible API.

## 4. Static files

Static files are served with WhiteNoise.

Build command should include:

```bash
python manage.py collectstatic --noinput
```

## 5. Recommended production commands

Build command:

```bash
pip install -r requirements.txt && python manage.py collectstatic --noinput && python manage.py migrate
```

Start command:

```bash
gunicorn conf.wsgi:application
```

## 6. Required environment variables

Copy `.env.example` and fill in real values on your host. Never commit `.env`.

Minimum production variables:

```env
SECRET_KEY=replace-this
DEBUG=False
ALLOWED_HOSTS=your-domain.com
CSRF_TRUSTED_ORIGINS=https://your-domain.com
DATABASE_URL=postgresql://...
USE_SUPABASE_STORAGE=True
SUPABASE_STORAGE_BUCKET=nexus-media
SUPABASE_S3_ENDPOINT_URL=https://PROJECT_REF.supabase.co/storage/v1/s3
SUPABASE_S3_ACCESS_KEY_ID=...
SUPABASE_S3_SECRET_ACCESS_KEY=...
SUPABASE_STORAGE_PUBLIC_URL=https://PROJECT_REF.supabase.co/storage/v1/object/public/nexus-media
```

On Render specifically, `ALLOWED_HOSTS` and `CSRF_TRUSTED_ORIGINS` must include the
`*.onrender.com` hostname Render assigns your service (shown on the service's dashboard page),
e.g. `ALLOWED_HOSTS=project-nexus.onrender.com` and
`CSRF_TRUSTED_ORIGINS=https://project-nexus.onrender.com` — add a custom domain to both once you
attach one.

## 7. Migrating old SQLite data to PostgreSQL

If you need to keep existing local data:

```bash
python manage.py dumpdata --exclude auth.permission --exclude contenttypes --indent 2 > data.json
```

Then switch `DATABASE_URL` to PostgreSQL and run:

```bash
python manage.py migrate
python manage.py loaddata data.json
```

### Uploaded media

Uploaded files are **not** stored in the repository — `media/` is ignored, so a fresh clone
starts with no uploads. This is intentional.

The public pages handle that state: a personnel record with no photo renders an initials avatar
rather than a broken image, and activity/section images are simply omitted. Re-upload content
through the admin dashboard, or copy existing files into your Supabase bucket if you are
migrating an established instance.

Note this applies only to *uploads*. The DOCX/XLSX form templates under
`proposals/template_files/` are source assets and remain in the repository.

## 8. Important security note

Do not hard-code credentials in `settings.py`. Use environment variables. If any email/app passwords were ever committed, rotate them in the provider dashboard.
