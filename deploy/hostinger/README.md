# Deploy NExUS on a Hostinger VPS

This recipe targets an **Ubuntu 24.04 Hostinger VPS with SSH and root/sudo**.
NExUS is a Django/Python application, not a static site or PHP application;
ordinary shared hosting or a static upload to `public_html` is not sufficient
unless your particular plan explicitly supports a persistent Python WSGI service.
The examples use PostgreSQL and the existing Supabase Storage integration. You
still need a reachable PostgreSQL database and a Supabase project; the VPS does
not create either. No changes are made to your Hostinger account by this repo.

**Privacy:** the existing Supabase integration generates public bucket URLs.
Anyone with a link can read an uploaded file. Do not use it for confidential
proposals or personal documents without first implementing private storage and
authorization-controlled downloads. See `DEPLOYMENT.md` for storage details.

## 1. Prepare the server and DNS

Point the domain's A record (and AAAA only if IPv6 is configured) to the VPS.
Allow ports 22, 80 and 443 in Hostinger's firewall and the server firewall.
Use a domain you control; replace `example.com` and `www.example.com` throughout
(or omit `www` everywhere if it has no DNS record).

On a fresh Ubuntu 24.04 VPS, as a sudo-capable administrator:

```bash
sudo apt update
sudo apt install -y python3 python3-venv python3-pip git nginx certbot python3-certbot-nginx
sudo adduser --system --group --home /srv/nexus nexus
# Clone your repository at /srv/nexus as the nexus user (use your actual URL).
sudo -u nexus git clone https://github.com/YOUR-OWNER/YOUR-REPO.git /srv/nexus
sudo -u nexus python3 -m venv /srv/nexus/.venv
```

If `/srv/nexus` already exists or the repository is private, provision the
checkout and Git access appropriately. Keep the working directory and virtualenv
owned by `nexus`. Do not put the application or its `.env` in an Nginx web root.

## 2. Configure application secrets

Create `/srv/nexus/.env`, owned by `nexus` with mode `600`. Start with the root
`.env.example` and replace **all** placeholders. At minimum configure:

- `SECRET_KEY`: generate one with `python3 -c 'import secrets; print(secrets.token_urlsafe(64))'`.
- `DEBUG=False`, `ALLOWED_HOSTS=example.com,www.example.com` and
  `CSRF_TRUSTED_ORIGINS=https://example.com,https://www.example.com`.
- `DATABASE_URL`: PostgreSQL URL; percent-encode reserved characters in the
  username and password. Configure database access, TLS and backups with your
  provider. SQLite is not the recommended production database.
- `USE_SUPABASE_STORAGE=True` and all Supabase S3/bucket values described in
  `DEPLOYMENT.md`. Configure SMTP values for email features.
- `SESSION_COOKIE_SECURE=True`, `CSRF_COOKIE_SECURE=True`. Leave
  `SECURE_SSL_REDIRECT=False` for initial HTTP certificate setup, then set it
  to `True` after HTTPS is working. Do not log in over plain HTTP.

```bash
sudo cp /srv/nexus/.env.example /srv/nexus/.env
sudo chown nexus:nexus /srv/nexus/.env
sudo chmod 600 /srv/nexus/.env
sudo nano /srv/nexus/.env
```

The settings module reads `.env` directly; it is not a shell script. Don't
commit it or put secrets in service files. A copy of `.env.example` alone is
not a working configuration.

## 3. Install and start

```bash
sudo -u nexus /srv/nexus/deploy/hostinger/deploy.sh
sudo -u nexus /srv/nexus/.venv/bin/python /srv/nexus/manage.py createsuperuser
sudo cp /srv/nexus/deploy/hostinger/nexus.service /etc/systemd/system/nexus.service
sudo systemctl daemon-reload
sudo systemctl enable --now nexus
sudo systemctl status nexus --no-pager
```

The deploy script installs Python dependencies, validates key production
settings, runs Django's deployment checks, collects static files, applies
migrations, and tests the configured storage connection. Deployment checks may
report warnings; review them. The storage test requires working network access
and S3 credentials. Static frontend assets are already tracked in the repo;
if frontend source changes, rebuild them with Node (see `frontend/README.md`)
before deploying. WhiteNoise serves collected static files through Gunicorn.

```bash
sudo cp /srv/nexus/deploy/hostinger/nginx.conf /etc/nginx/sites-available/nexus
sudo nano /etc/nginx/sites-available/nexus  # replace server_name
sudo ln -s /etc/nginx/sites-available/nexus /etc/nginx/sites-enabled/nexus
# Remove the default site if it conflicts with your domain.
sudo nginx -t && sudo systemctl reload nginx
sudo certbot --nginx -d example.com -d www.example.com
```

Certbot needs public DNS and port 80 to work. Select its HTTPS redirect option,
then set `SECURE_SSL_REDIRECT=True` in `.env` and restart:

```bash
sudo systemctl restart nexus
sudo -u nexus /srv/nexus/.venv/bin/python /srv/nexus/manage.py check --deploy
```

Visit the HTTPS site, log in, verify static assets and test an upload and email.
Nginx overwrites `X-Forwarded-Proto`, which Django trusts; do not expose
Gunicorn's loopback port publicly or put an untrusted proxy in front of it.

## 4. Updates and operations

Back up the database and uploaded files before an update. From the deployed
checkout, fetch the intended release using your normal Git workflow, then:

```bash
sudo -u nexus /srv/nexus/deploy/hostinger/deploy.sh
sudo systemctl restart nexus
sudo systemctl status nexus --no-pager
sudo journalctl -u nexus -n 100 --no-pager
```

The deploy script does not pull code or restart the service. Migrations are not
automatically reversible: test updates and plan database rollback separately.
Use your database provider's backup/restore process and back up the Supabase
bucket separately; the VPS snapshot alone does not cover either. Verify TLS
renewal with `sudo certbot renew --dry-run`. Monitor disk, logs, expiry and
backups. For troubleshooting check `journalctl -u nexus`, Nginx logs, and
`python manage.py check_file_storage` as the `nexus` user.
