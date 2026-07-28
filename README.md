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
| `accounts/tests/test_permissions_module.py` | The `accounts.permissions` predicates themselves |
| `accounts/tests/test_auth.py` | Login, logout, registration gating, email verification, maintenance mode |
| `accounts/tests/test_cms.py` | Admin-editable page content, Home sections, thrust cards, workflow phases |
| `proposals/tests.py` | Proposal progress weighting, phase labels, proposal access control |
| `proposals/tests_permissions.py` | Characterisation of the proposal permission helpers |
| `proposals/tests_workflow.py` | Wizard access and steps, status maps, review rounds, trackers |
| `accounts/tests/test_structure.py` | URL resolution, no duplicate definitions, re-export contract |
| `accounts/tests/test_error_handling.py` | Logging config, graceful degradation, no leaked error text |
| `proposals/tests_documents.py` | DOCX/XLSX generation, template routing, download access |
| `proposals/tests_transitions.py` | MOA/implementation transitions, status derivation, wizard helpers |
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

## Code layout

The two view modules are Python **packages**, not single files:

```
accounts/views/          proposals/views/
  helpers.py               constants.py
  proposal_queries.py      helpers.py
  auth.py                  permissions.py
  dashboards.py            wizard.py
  admin_users.py           public.py
  content.py               review.py
  builders.py              moa.py
  reports.py               implementation.py
  cms.py                   documents.py
```

Each `__init__.py` re-exports every public name, so `urls.py` refers to
`views.some_view` exactly as before. **When you add a view to a submodule, add
it to the package's `__init__.py` too** — otherwise the URLconf raises
`AttributeError` at import. `accounts/tests/test_structure.py` guards this.

## Logging

`conf/settings.py` configures console logging. Use a module logger rather than
`print()`:

```python
import logging

logger = logging.getLogger(__name__)
logger.exception("Could not do the thing for proposal %s.", proposal.pk)
```

Application loggers (`accounts`, `proposals`, `details`) default to `INFO`;
set `LOG_LEVEL=DEBUG` in the environment for more detail. The root logger sits
at `WARNING` so third-party libraries stay quiet.

**When catching exceptions**, prefer a specific type. Where a broad
`except Exception` is genuinely warranted — code that must never crash, such as
context processors or middleware — log it with `logger.exception(...)` and
never interpolate the exception into a user-facing message, since that leaks
database constraint names and internal paths.

## Permissions

All permission logic lives in **`accounts/permissions.py`**. Views, templates,
and decorators should call its predicates rather than comparing roles inline:

```python
from accounts import permissions

if permissions.can_review_proposal(request.user, proposal):
    ...
```

The helpers still present in `proposals/views.py` (`_can_edit`, `_can_review`,
and friends) are thin delegations kept for backwards compatibility.

One rule worth knowing: **`ADMIN` implies most capabilities but not all.**
`SUBMIT_QUARTERLY_ACCOMPLISHMENT` is restricted to coordinators, because Admin
manages the system rather than filing reports for a department. See
`_role_restricted_capabilities()`.

### Coverage status

Permissions, authentication, the CMS, the proposal wizard, document
generation, and the MOA/implementation state transitions are all covered.

Document tests generate real files from the templates committed under
`proposals/template_files/`, so a corrupt template or a broken field lookup
fails the suite rather than only surfacing on a user's download.
