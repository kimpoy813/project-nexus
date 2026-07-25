# NExUS Deployment Guide: PostgreSQL + Supabase Storage

This project should use **PostgreSQL for database records** and **Supabase Storage for uploaded files** in production.

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

If starting fresh, create an admin account:

```bash
python manage.py createsuperuser
```

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

You must separately copy existing `media/` files into your Supabase bucket.

## 8. Important security note

Do not hard-code credentials in `settings.py`. Use environment variables. If any email/app passwords were ever committed, rotate them in the provider dashboard.
