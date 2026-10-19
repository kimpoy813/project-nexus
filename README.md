# project-nexus

NExUS — Networked Extension Unified System. A Django application for managing
institutional extension proposals from drafting through review, approval, MOA
routing, and implementation reporting.

See [`DEPLOYMENT.md`](DEPLOYMENT.md) for production setup (PostgreSQL +
Supabase Storage) and [`docs/ARCHITECTURE_AUDIT.md`](docs/ARCHITECTURE_AUDIT.md)
for a prioritised review of known technical debt.

---

## Latest system / UI audit

See [`docs/UI_UX_AUDIT_2026-10-14.md`](docs/UI_UX_AUDIT_2026-10-14.md) for
fixes, flow mapping, browser/test coverage, compatibility notes and remaining
production checks. UI libraries/fonts are now served locally; rebuild assets
with `npm ci --prefix frontend && npm run build --prefix frontend` after changing
utility classes. See [`frontend/README.md`](frontend/README.md).

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
| `accounts/tests/test_structure.py` | URL resolution, no duplicate definitions, re-export contract |
| `accounts/tests/test_error_handling.py` | Logging config, graceful degradation, no leaked error text |
| `proposals/tests_documents.py` | DOCX/XLSX generation, template routing, download access |
| `proposals/tests_transitions.py` | MOA/implementation transitions, status derivation, wizard helpers |
| `details/tests.py` | Content model behaviour: ordering, clamping, visibility |
| `accounts/tests/test_layout.py` | Full-bleed layout: no capped page shells, stylesheet linked, auth/wizard/dashboard shells intact |
| `accounts/tests/test_loading_skeleton.py` | Overlay, eight layouts, route → variant, dest matching (login/logout plus JS vs Python for every named URL), the way out of a wait that never ends, and the download opt-outs |
| `tests/nexus-loader.test.cjs` | The skeleton controller's lifecycle: the page being left cannot take a slow navigation down, the escape control, the backstop, and the `?nx-skeleton` review pin |
| `accounts/tests/test_file_storage_configuration.py` | Supabase bucket/endpoint/region/key validation, the `check_file_storage` command, and the provider error shown after a failed upload |
| `accounts/tests/test_process_reordering.py` | Extension Process steps: nesting to any depth, parent-first saves, the drag reorder endpoint, public rendering |
| `tests/process-steps.test.cjs` | Outline maths for the nested step editor (`node --test tests/*.test.cjs`) |
| `accounts/tests/test_toasts.py` | Toasts: every page mounts the toaster, messages reach it, no native alerts, no leaked `{# #}` comment |
| `tests/nexus-toast.test.cjs` | The toast helper: waiting for the module, the plain fallback, message tags → toast types |
| `tests/dashboard-views.test.cjs` | The proposal table/card switch: icon-only toggles, proposal tables only, the saved preference (`node --test tests/*.test.cjs`) |

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

## Public pages are composed from content sources

A **content source** is a body of admin-managed data that has its own no-code
builder: Extension Thrust cards, Personnel, Activities, Processes, Targets, the
SDGs, the Template Library, the Form Builder. Every source is declared once in
**`details/content_sources.py`**, and everything else reads from that registry:

| Reads the registry | For |
| --- | --- |
| Page Content editor | the block palette an admin drags onto a page |
| `PageSection.Layout` | the layout codes and their labels |
| `resolve_section_data` | the query that feeds a block |
| `details/blocks/<source>.html` | the public markup |
| the nested editor | in-place CRUD inside the section |
| `content_source_reorder` | drag-to-order the items in a source |

### Extension Process steps nest to any depth

A step can sit under another step, to any depth. Both editors — the standalone
one under **Admin → Processes** and the inline **Processes** builder inside the
Page Content editor — share one component:

| Piece | File |
| --- | --- |
| Row markup (rendered and cloned in the browser) | `accounts/templates/dashboard/admin/_process_step_row.html` |
| Drag to move, drag sideways to nest, Tab / Shift+Tab | `static/js/process-steps-editor.js` |
| Turning the posted outline into rows | `accounts/views/process_steps.py` |
| Public numbering and bullets | `details/templates/details/blocks/_process_steps.html` |

Each row posts `step_ref[]`, `step_id[]`, `step_description[]` and
`step_parent[]`. The parent is a *reference* (`s<pk>` for a saved step,
`n<counter>` for one that is not saved yet), so a new sub-step can hang off a
new parent. `_sync_process_steps` creates parents before children, then writes
`ProcessStep.parent` plus a depth-first `order` that both the public block and
the editors read back.

The process list itself is also draggable from **Admin → Processes** (or the
inline Processes builder). Its position column is the public display sequence;
reordering saves immediately and applies everywhere a Processes block appears.
Editing a process's title or steps leaves that sequence unchanged.

**A page holds bindings, not copies.** Dropping the Template Library onto two
pages publishes one list twice; editing a template in its builder updates both.
That is the rule that keeps the system from becoming repetitive: data lives in
exactly one table, and pages decide where to show it.

### Adding a builder to the palette

1. Add a `ContentSource(...)` to `_SOURCES` in `details/content_sources.py`.
2. Add its layout to `PageSection.Layout` (label from the registry) and ship a
   migration for the new choice.
3. Create `details/templates/details/blocks/<key>.html`.
4. Optionally add a nested editor partial and set `order_model` to make its
   items draggable.

Nothing in the four public page templates or the page editor needs to change.
`accounts/tests/test_content_sources.py` fails if a source is declared but its
template, manager URL, or resolver is missing — the exact half-registered state
that used to leave a section rendering nothing.

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

### Loading skeletons

Every page in the system is server-rendered, so a navigation would otherwise be
a blank screen until the next response arrived. Instead, `templates/base.html`
renders a page skeleton as the **first thing in the body** — visible by default,
so it paints while the page is still being fetched/parsed — and
**`static/js/nexus-loader.js`** takes it away on load and paints it again while
the next page is fetched. Nothing else needs to opt in: any template that
extends `base.html` (directly or through `dashboard_base.html` /
`_wizard_shell.html`) ships it.

The screens are not one layout repeated, so the skeleton is not either. The
overlay carries **one layout per page family**, each drawn to the geometry of
the screens it stands in for — same gutters, same column splits, same
breakpoints — and `data-nx-variant` on the overlay says which one paints:

| `data-nx-variant` | Stands in for | Shape |
|---|---|---|
| `marketing` | `/`, `/reports/`, `/achievements/`, `/proposals/` | Full-bleed coloured hero (centred, capped measure), section nav, stacked full-width sections |
| `auth` | login, register, password reset | `.nx-auth`: brand panel beside the form card with its coloured header |
| `dashboard` | the seven role dashboards | Title bar, then a 240px navigation rail beside the KPI row and queue panel |
| `wizard` | `proposal_wizard`, `proposal_create` | `.nexus-wizard-layout`: stepper rail \| form column \| context rail |
| `tracker` | MOA / implementation / post-approval | Progress header, then a two-thirds main card beside a column of side cards |
| `list` | the admin CRUD index screens | Page head with actions, then a card holding a table |
| `form` | the admin CRUD create/edit screens | Page head, then a card with a 2/3-column field grid |
| `record` | profile, user detail, review comments (and any unlisted route) | Heading over stacked full-width detail cards |

The variant is resolved **per route** by `accounts.context_processors.skeleton_variant`
— an explicit table, then the name's ending (`_list` / `_manager` → `list`,
`_create` / `_edit` → `form`, `_dashboard` → `dashboard`), then the path area,
then `record`. A screen added later therefore gets the shape of its kind
without touching a template.

The pieces:

| File | What it holds |
|---|---|
| `static/css/nexus-skeleton.css` | The overlay, the eight layouts, and the reusable shapes (`.nx-skel`, `--text`, `--title`, `--avatar`, `--card`, `--row`, `--grid`). Plain CSS, no Tailwind classes, so it paints before the CDN bundle does. |
| `static/js/nexus-loader.js` | The controller: show on navigation, hide on load, self-heal after 12s, clear on bfcache restore, ignore downloads/new tabs/hash links/modified clicks/JS-cancelled clicks, and skip the shimmer entirely under `prefers-reduced-motion`. |
| `templates/base.html` | The overlay markup (all eight layouts), the stylesheet link, the `<noscript>` rule that hides it without JavaScript, and the controller script. |
| `accounts/context_processors.py` | `skeleton_variant()`: route → layout. |

All eight layouts ship in the document and only one is shown, which is what
lets the controller paint the shape of the page being navigated **to**: a link
or form can declare its destination with `data-nx-skeleton="dashboard"`, so
leaving the landing page for a dashboard shows the dashboard's rail rather than
the hero it came from. The navbar and footer links in `base.html` carry those
hints.

To look at a layout without catching it mid-navigation, hold it on screen with
`?nx-skeleton` — give it a value to force one, e.g. `/login/?nx-skeleton=wizard`.

A region that only fills in later (an AJAX list, a search box) can paint the
same shapes in place:

```js
NexusSkeleton.fill(box, { rows: 3 });   // avatar + two-line rows
NexusSkeleton.region(el, true);         // flip a .nx-skel-region to its skeleton
NexusSkeleton.busy(selectEl, true);     // shimmer a control that is waiting
NexusSkeleton.variant("tracker");       // switch the page layout by hand
NexusSkeleton.show();                   // cover the page for a long action
```

Add `data-nx-no-skeleton` to a link or form that must not cover the page (a
download, a print view, anything handled in place). Inside the proposal wizard,
stepper clicks and Save / Back / Skip posts are intercepted by
`static/js/nexus-wizard.js` so only the three-rail body swaps — the rest of the
site does not reload. `accounts/tests/test_loading_skeleton.py`
renders the public, dashboard, wizard, tracker and admin pages and fails if one
stops shipping the overlay, the stylesheet or the controller — or if a page
family starts painting somebody else's layout.

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

## Feedback and toasts

Every piece of feedback in NExUS goes through one function:

```js
window.nexusToast(message, type);   // success | error | warning | info
```

`templates/partials/_toaster.html` is its only home. A full page includes it as
the last thing it renders (`templates/base.html`, the maintenance page, the
debug sign-in, Django's admin) and links `static/goey/toaster.css` from its
head. The partial mounts the Gooey toaster (`static/goey/toaster.js`, built from
`frontend/`), turns Django's `messages` into `#messages-data`, and hands both to
the helper. Feature templates do not render a second inline copy of those
messages; Django flash feedback uses the toast across the whole system.

| What raises a toast | How |
|---|---|
| `messages.success/error/warning/info(request, ...)` | Rendered as `#messages-data`, read at `DOMContentLoaded` and shown with the matching type |
| A page script — `dashboard_base.html`, the role dashboards, `process-steps-editor.js`, `_source_reorder_script.html`, `wizard_steps_manager.html` | `window.nexusToast(message, type)` |
| The proposal wizard's in-page AJAX swap (`static/js/nexus-wizard.js`) | The swapped-in page's messages, through the same helper |
| Django's own admin | The same partial, mounted from `templates/admin/base_site.html`; its `.messagelist` is removed once the toasts are up, and kept if the module never loads |
| An expiring session | `base.html` raises a warning toast beside the "Stay logged in" banner |

Two order rules the helper handles for you:

* `toaster.js` is a **module**, so it runs only after the document is parsed. A
  toast raised before that — from an inline script, or from the admin's message
  list — waits for it rather than appearing in the plain style a moment before
  the good one.
* If the module never arrives, the message is shown with the same colours in
  `#toast-container`, the older dependency-free toast, so nothing is lost.

Nothing reports through `alert()` any more. `accounts/tests/test_toasts.py`
fails on a native alert in any template or `static/js` file, on a full page that
does not mount the toaster, on a page that mounts it twice, and on a Django
message that never reaches `#messages-data`. `tests/nexus-toast.test.cjs`
covers the waiting and fallback rules without a browser.

### `{# ... #}` is a one-line comment

Django strips `{# ... #}` only when it opens and closes on the **same line**. A
comment spread over two lines is not stripped — it is printed verbatim on the
page. That is how a note about `.nexus-shell` ended up above the content of
every page in the system, and how the nested step editor explained itself to
every admin who opened it. Multi-line notes belong in
`{% comment %} ... {% endcomment %}`; `test_toasts.py` fails on any `{#` that
closes on another line under `templates/`, `accounts/templates/`,
`details/templates/` or `proposals/templates/`.

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

## Quarterly report cycle

The system asks each campus for a quarterly accomplishment report; the Campus
Coordinator uploads the file and enters the quarter's activities, beneficiaries
and partners counts. Staff and Director open the requests and see the figures.

| Route | Who | What it does |
| --- | --- | --- |
| `/accomplishments/requests/` | Staff, Director, Admin (every campus); Campus Coordinator (own campus) | Each request with its due date and whether a report has been filed |
| `/accomplishments/requests/new/` | Staff, Director, Admin | Asks one, several, or every campus for a quarter |
| `/accomplishments/create/?request=<id>` | Coordinators with `SUBMIT_QUARTERLY_ACCOMPLISHMENT` | Uploads the report file, writes the narrative, enters the quarter's counts |
| `/accomplishments/<id>/` | Requester roles, plus the submitter's own scope | The uploaded file, the narrative, and the figures filed |

How the counts reach the Targets tracker:

* `QuarterlyReportRequest` holds one row per campus, year and quarter. Asking a
  campus that already has a row re-opens it instead of duplicating.
* The form asks for the figures once. Activities answer Programs, beneficiaries
  answer Participants, and partners answer Partners; the same numbers are
  stored on the report and as `AccomplishmentTargetEntry` rows.
* Technology Transfer has no count box on the report; it is maintained from
  the admin target editor.
* `details.quarterly.save_target_contributions()` writes each figure into the
  campus `Target` row for that quarter (`actual_q1` … `actual_q4`), creating the
  row when that campus has no target for the metric yet. The figure
  **replaces** what was filed before, so a correction never double-counts.
* A blank count is skipped, not read as 0: an untouched box must not overwrite
  an actual already on the tracker. A figure genuinely at zero is filed by
  typing `0`.
* Only Campus Coordinators write to the campus tracker. A Department
  Coordinator's scope sits inside a campus, so their reports never write to it.
* Answering a request requires the uploaded file; ad-hoc reports keep the file
  optional.

Pending requests are surfaced on the Campus Coordinator dashboard (and counted
in the notification badge); the Staff and Director dashboards link straight to
the request list.

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

The quarterly report cycle — who may ask, who may answer, the file requirement,
and the write-back into the campus `Target` rows — is covered by
`accounts/tests/test_quarterly_reports.py`.

Document tests generate real files from the templates committed under
`proposals/template_files/`, so a corrupt template or a broken field lookup
fails the suite rather than only surfacing on a user's download.
