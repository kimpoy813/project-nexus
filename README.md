# project-nexus

NExUS — Networked Extension Unified System. A Django application for managing
institutional extension proposals from drafting through review, approval, MOA
routing, and implementation reporting.

See [`DEPLOYMENT.md`](DEPLOYMENT.md) for production setup (PostgreSQL +
Supabase Storage) and [`docs/ARCHITECTURE_AUDIT.md`](docs/ARCHITECTURE_AUDIT.md)
for a prioritised review of known technical debt.

---

## Local development

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env        # then edit: set DEBUG=True for local work
python manage.py migrate
python manage.py runserver
```

### `DEBUG` defaults to `False`

This is deliberate: an unset or misspelled `DEBUG` in production would
otherwise expose stack traces, settings, and local variables to visitors.

For local development set `DEBUG=True` in your `.env`. With `DEBUG=False`,
static files are served through WhiteNoise's manifest storage, so you would
need to run `python manage.py collectstatic` first.

---

## Running the tests

```bash
python manage.py test --settings=conf.settings_test
```

The `conf.settings_test` module is required. It swaps in fast password
hashing, in-memory file storage, and plain static file handling, and disables
django-axes lockouts — without it, tests fail on missing `collectstatic`
output rather than on real problems.

Run a subset:

```bash
python manage.py test accounts --settings=conf.settings_test
python manage.py test accounts.tests.test_permissions --settings=conf.settings_test
```

### What is covered

| Suite | Focus |
|---|---|
| `accounts/tests/test_permissions.py` | Role access: who may submit vs. view accomplishment reports, admin-only areas, dashboard access |
| `accounts/tests/test_auth.py` | Login, logout, registration gating, email verification, maintenance mode |
| `accounts/tests/test_cms.py` | Admin-editable page content, Home sections, thrust cards, workflow phases |
| `proposals/tests.py` | Proposal progress weighting, phase labels, proposal access control |
| `details/tests.py` | Content model behaviour: ordering, clamping, visibility |

`accounts/tests/factories.py` builds users with a given role. Use it rather
than calling `create_user` directly — a signal creates a `FACULTY` profile on
user creation, so the role must be updated *and* the user re-fetched, or
permission helpers silently read the stale cached profile.

```python
from accounts.tests import factories

user, client = factories.director("my_director")
response = client.get("/dashboard/director/")
```

### Coverage status

Permissions, authentication, and the CMS are covered. The proposal wizard
itself (a 631-line view), document generation, and the MOA and implementation
workflows are **not** yet covered — see the architecture audit for context.
