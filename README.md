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

### Signing in for the first time

`python manage.py createsuperuser` is **not enough to reach the admin
dashboard**. A `post_save` signal gives every new user a `Profile` with
`role=FACULTY`, and `@admin_required` checks that role — not `is_superuser`.
Promote the profile after creating the user:

```bash
python manage.py shell -c "
from django.contrib.auth import get_user_model
from accounts.models import Profile
u = get_user_model().objects.get(username='admin')
u.set_password('change-me'); u.is_active = True; u.save()
Profile.objects.update_or_create(user=u, defaults={'role': Profile.ROLE_ADMIN, 'email_verified': True})
"
```

The same applies to `/register/`: a new account starts inactive until the
verification email is clicked, and `EMAIL_BACKEND` defaults to SMTP. For local
work set `EMAIL_BACKEND=django.core.mail.backends.console.EmailBackend` and the
verification link prints to the terminal instead.

Two defaults that surprise people: sessions expire after **10 minutes** of
inactivity (`SESSION_COOKIE_AGE=600`) and **5 failed logins** lock the account
for an hour (`AXES_FAILURE_LIMIT=5`). Both are environment variables.

### GitHub Codespaces

The Codespace URL is not `localhost`, and this app validates both the `Host`
header and the `Origin`, so two settings are required or you get `400
DisallowedHost` on every page and a CSRF rejection on the login POST:

```bash
# your codespace host looks like  <workspace>-<id>-8000.app.github.dev
echo "DEBUG=True" >> .env
echo "ALLOWED_HOSTS=.app.github.dev,localhost,127.0.0.1" >> .env
echo "CSRF_TRUSTED_ORIGINS=https://*.app.github.dev,http://localhost:8000" >> .env

gh codespace ports forward 8000:8000
```

`runserver` must bind all interfaces for forwarding to reach it:
`python manage.py runserver 0.0.0.0:8000`. Uploaded files go to local storage
unless `USE_SUPABASE_STORAGE=True` with valid keys, so a Codespace with no
`.env` storage block still runs — uploads just land on the container's disk and
disappear with it.

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

## File storage

Uploads use local storage in development and **Supabase Storage** (its
S3-compatible API) in production — see [`DEPLOYMENT.md`](DEPLOYMENT.md) §3. The
settings in **`conf/storage_config.py`** validate the bucket, endpoint, region,
public URL, and access keys before the remote backend is selected, so a
malformed value returns an actionable message instead of a mid-upload failure.

To test a live configuration end to end (writes and removes a throwaway object
under `_nx_storage_check/`):

```bash
python manage.py check_file_storage              # full check, talks to Supabase
python manage.py check_file_storage --config-only  # settings only, no network
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
| `proposals/tests_wizard_steps.py` | The configurable wizards: step ordering, part reassignment, office-built steps, attached forms, the MOA wizard |
| `accounts/tests/test_wizard_admin.py` | The wizard builder screens: manager, create, edit, move, delete, permissions |
| `accounts/tests/test_structure.py` | URL resolution, no duplicate definitions, re-export contract |
| `accounts/tests/test_error_handling.py` | Logging config, graceful degradation, no leaked error text |
| `proposals/tests_documents.py` | DOCX/XLSX generation, template routing, download access |
| `proposals/tests_transitions.py` | MOA/implementation transitions, status derivation, wizard helpers |
| `details/tests.py` | Content model behaviour: ordering, clamping, visibility |
| `accounts/tests/test_layout.py` | Full-bleed layout: no capped page shells, stylesheet linked, auth/wizard/dashboard shells intact |
| `accounts/tests/test_file_storage_configuration.py` | Supabase bucket/endpoint/region/key validation, the `check_file_storage` command, and the provider error shown after a failed upload |

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
  wizard_builder.py        implementation.py
  reports.py               documents.py
  cms.py                   step_flow.py
                           step_sections.py
                           moa_sections.py
                           wizard_flows.py
```

## Configurable wizards

Neither the proposal wizard nor the MOA drafting wizard is a fixed list of
screens any more. Both are rows in a step table the Extension Office edits from
**Admin → Wizard Steps** (and **MOA Wizard Steps**):

| An admin can | How it works |
|---|---|
| Rename a step, rewrite its instructions, hide it, make it optional | `ProposalWizardStepConfig` / `MOAWizardStepConfig` |
| Add a step the code has never heard of | A step with no built-in part renders the office's own attached forms |
| Move a step anywhere in the wizard | Only `order` changes; the step's number is its stable reference |
| Point a step at a different built-in part | `section_key` selects the part: its template, its save logic, and its completion rule move together |
| Attach any Form Builder form to any step | `attached_proposal_steps` / `attached_moa_steps` follow the step when it moves |

Two ideas make that work, and they are worth knowing before editing this code:

* **A step's number is not its position.** `step_no` is the handle used by
  URLs, saved progress, reviewer comments, and attached forms, so it never
  changes. `order` is where the step appears. Templates therefore show
  `step_position` / `step_total` and link with `next_step_no` /
  `prev_step_no` — never `step|add:1`, which assumes consecutive numbers.
* **A built-in part owns its rendering, its saving, and its completion rule.**
  They live together in one `WizardSection` (`proposals/views/step_sections.py`)
  or `MOAWizardSection` (`proposals/views/moa_sections.py`) rather than in three
  separate `if step == N` chains. To add a built-in part, register one there —
  no view changes.

`StepFlow` (`proposals/views/step_flow.py`) is the only reader of the step
tables; ordering, visibility, requiredness, and "which part renders here" all
resolve through it, so the wizard, the sidebar, the progress bar, the
submission gate, and the admin screens cannot disagree. A required field in an
attached form holds its step open, and holds submission too.

Each `__init__.py` re-exports every public name, so `urls.py` refers to
`views.some_view` exactly as before. **When you add a view to a submodule, add
it to the package's `__init__.py` too** — otherwise the URLconf raises
`AttributeError` at import. `accounts/tests/test_structure.py` guards this.

## Layout and spacing

Every screen is **full-bleed**: it spans the viewport and keeps its breathing
room through shared rhythm rather than a centred fixed-width column. The rules
live in **`static/css/nexus-layout.css`** — use these classes instead of adding
new `max-w-*xl mx-auto` wrappers:

| Class | Use it for |
|---|---|
| `.nx-page` | A page body. Owns the side gutter (`--nx-gutter`), so add `py-*` for vertical spacing but never `px-*`/`p-*`. |
| `.nx-bar` | The navbar and footer, so their edges line up with page content. |
| `.nx-page--measure` | Centred display text (hero headings, notices) inside a full-width band. |
| `.nx-measure` | A prose block that must stay readable (~68 characters) next to wide content. |
| `.nx-split` | Fluid main column plus a `--nx-rail-lg` side rail (`--rail-left` for the reverse). |
| `.nx-form-grid` | Form fields that should flow into columns; `.nx-full` keeps a field on its own line. |
| `.nx-auto-grid` | Card rows that should gain columns on wide screens instead of stretching. |

Tables, KPIs, cards and forms use the whole width; only prose and centred
headings are measured. `.nx-dash__inner` (dashboards) and `.nexus-wizard-layout`
(proposal wizard: stepper | form | context panel) follow the same gutter.

`accounts/tests/test_layout.py` renders the public pages, every role
dashboard, the admin CRUD screens, the auth screens and the wizard, and fails
if one regresses to a capped container or stops linking the stylesheet.

### Progress rings

Phase percentages are drawn as rings rather than bars. The component lives in
`static/css/nexus-ui.css` (`.nx-ring`) and its markup in
`proposals/templates/services/_progress_ring.html`:

| Include variable | What it does |
|---|---|
| `ring_percent` | 0-100, drawn as the filled arc. The circle carries `pathLength="100"`, so the dasharray is written in percent units and no circumference maths leaks into templates. |
| `ring_tone` | `proposal` / `moa` / `implementation` — green, maroon and gold, the same bands the dashboard gauges use. |
| `ring_size` | `lg` / `md` / `sm`. `sm` hides the figure inside the ring because the percentage is printed beside it. |
| `ring_label` | Optional accessible name. When it is set the ring is announced as an image and the figure inside it stays out of the accessibility tree, so the number is never read twice. |

The numbers come from `details.models.WorkflowPhase.weight_percent` (admin →
Services page → Workflow Phases), which is also what `Proposal.overall_progress`
weights by — one source of truth, so the published rings and the dashboard
percentages cannot drift apart. A proposal that needs no MOA has that phase's
share redistributed across Proposal and Implementation.

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
