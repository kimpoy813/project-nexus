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
| `proposals/tests_dynamic_wizard.py` | Dynamic wizard steps: built-in vs custom layouts, proposal-field mapping, fresh-install regression |
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
  reports.py               implementation.py
  cms.py                   documents.py
```

Each `__init__.py` re-exports every public name, so `urls.py` refers to
`views.some_view` exactly as before. **When you add a view to a submodule, add
it to the package's `__init__.py` too** — otherwise the URLconf raises
`AttributeError` at import. `accounts/tests/test_structure.py` guards this.

## Dynamic wizard steps (no-code)

The proposal wizard's steps are **admin-managed end to end** — nothing about a
step's form is hard-coded into the templates anymore:

* **Step list** — `details.ProposalWizardStepConfig` owns each step's title,
  description, instructions, visibility, and whether it is required.
* **Step content** — each step has a `layout`. `BUILTIN` keeps the classic
  system form (the type/scope chips, the SDG grid, the sex/gender table, the
  upload widgets — now just entries in the `proposals/views/wizard_builtin.py`
  registry); `DYNAMIC` retires it and shows **only** the admin-built form.
  This is how the office adopts a new printed template for a step without a
  developer.
* **Proposal-field mapping** — a plain field with
  `DynamicFormField.maps_to_proposal` also writes its answer into the real
  `Proposal` column (title, implementing agency, budget, rationale, …), so the
  generated DOCX/XLSX forms, review screens, and dashboards keep reading it
  no matter how a step is rebuilt. On a `BUILTIN` step, a field mapped to a
  column the system form already owns is a *label override* — it is never
  rendered or validated twice.

The flows live in `proposals/views/wizard.py` (dispatch),
`proposals/views/wizard_builtin.py` (the built-in step registry), and
`proposals/views/dynamic_answers.py` (render/save/validate for admin-built
fields). `proposals/tests_dynamic_wizard.py` pins the behaviour, including the
fresh-install regression where required mirror fields used to block Step 1
from ever saving.

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
