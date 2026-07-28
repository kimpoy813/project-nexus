# NExUS Architecture Audit

**Date:** 2026-07-28
**Scope:** Whole repository — ~16,500 lines of Python, ~17,900 lines of templates, 4 Django apps
**Status:** Items marked ✅ have been actioned. Everything else is a finding awaiting a decision.
**Last updated:** 2026-07-28, after the safety fixes and test-suite work.

---

## How to read this

Findings are ordered by **risk × effort**, not by how interesting they are. Each one states the
evidence, why it matters, and what fixing it would involve. The goal is to let you decide what to
action — not to argue for a rewrite.

The short version: **the system works and the domain modelling is sound.** The problems are
concentrated in three places — no test coverage, two enormous view modules, and a handful of
production-safety settings. None require a rewrite; all can be fixed incrementally.

---

## Severity 1 — Fix before the next production deploy

### 1.1 ✅ `DEBUG` defaulted to `True` — **fixed**

`conf/settings.py`

```python
DEBUG = env_bool("DEBUG", True)
```

If `DEBUG` is ever unset in the production environment, Django serves full stack traces with
source, local variables, and settings to any visitor who triggers an error. This is the single
highest-impact issue in the repo, and it is a one-line fix.

**Status:** now defaults to `False`; development opts in via `.env`.

```python
DEBUG = env_bool("DEBUG", False)
```

Consequence worth knowing: with `DEBUG=False`, WhiteNoise's manifest storage
requires `collectstatic` before static files resolve. This is why the test
suite needs `--settings=conf.settings_test`, and why `.env.example` and the
README now spell out the local workflow.

---

### 1.2 ✅ `db.sqlite3` was committed to Git — **untracked**

The 1.2 MB SQLite database is tracked, despite `.gitignore` listing `db.sqlite3` and `*.sqlite3`
(the ignore rules do not apply to already-tracked files).

Consequences:
- Real user records, including password hashes, live in Git history.
- Every developer's local data churn produces spurious diffs and merge conflicts.
- Production runs PostgreSQL, so the committed file is misleading.

**Status:** untracked via `git rm --cached db.sqlite3`; the local file is untouched and the
existing `.gitignore` rule now takes effect.

**Still outstanding:** this stops future commits but the data remains in Git history. If the
database ever held real user credentials, those should be rotated, and purging history with
`git filter-repo` is worth considering. That rewrites history for everyone, so it is your call
rather than something to do unannounced.

---

### 1.3 47 uploaded media files are committed

`git ls-files media/ | wc -l` → 47

`.gitignore` excludes `media/`, but these predate the rule. Production uses Supabase Storage, so
these are dead weight that will keep growing if anyone commits before the ignore takes effect.

**Deliberately not actioned — needs your confirmation.** The 47 files total **120 MB** and
include the personnel photographs rendered on the public homepage. `DEPLOYMENT.md` (line 125)
states media must be copied into the Supabase bucket separately, so Git is not the delivery
mechanism — but I cannot verify from here that your bucket is actually populated.

Untracking them before that is true would break every image on the live site.

**To action, once you have confirmed the bucket holds these files:**

```bash
git rm -r --cached media/
```

The local files stay in place; only Git stops tracking them.

---

### 1.4 ✅ Effectively no test coverage — **substantially addressed**

**Before:** 40 lines across three files. Worse, *both* real tests in `proposals/tests.py` were
already failing — they referenced `Proposal.mark_implementation_in_progress()` and a
`proposal_moa_workflow` URL, neither of which still exists. They had been broken since an earlier
refactor and nobody noticed, which is itself the clearest evidence the suite was not being run.

**Now: 171 tests, running in ~2.5 seconds.**

| Suite | Tests | Focus |
|---|---|---|
| `accounts/tests/test_permissions.py` | 17 | Role access, admin-only areas, dashboards |
| `accounts/tests/test_permissions_module.py` | 21 | The permission predicates themselves |
| `accounts/tests/test_auth.py` | 16 | Login, registration gating, verification, maintenance |
| `accounts/tests/test_cms.py` | 35 | Page content, Home sections, thrusts, workflow phases |
| `proposals/tests.py` | 17 | Progress weighting, phase labels, access control |
| `proposals/tests_permissions.py` | 30 | Characterisation of the proposal permission helpers |
| `proposals/tests_workflow.py` | 24 | Wizard access and steps, status maps, review rounds, trackers |
| `details/tests.py` | 11 | Model ordering, clamping, visibility |

Run with `python manage.py test --settings=conf.settings_test`.

**These were verified to actually catch regressions**, not merely pass. Three deliberate
sabotages were introduced and each was caught: re-granting Admin the submit capability (10
failures), removing the workflow-weight clamp (1 failure), and reintroducing the null-submitter
template crash (3 errors). The suite returned to green when each was reverted.

**A real bug was found while writing them:** the accomplishment reports list raised a 500 for
*every* viewer whenever any report had a null `submitted_by` — which the model explicitly allows
via `on_delete=SET_NULL`. Deleting a user would have broken the page for everyone. Fixed.

**Now covered:** the wizard's access rules and all 19 steps, status/progress maps, review round
constraints, and tracker access.

**Still not covered:** document generation (`docx_forms.py`, 2,176 lines) and the deeper MOA and
implementation state transitions.

This is the finding that gates everything else. **Every other refactor in this document is
dangerous until this is addressed**, because there is currently no way to know whether a change
broke the proposal lifecycle short of clicking through it manually.

**Remaining effort:** ~1 day for document generation and the deeper workflow transitions.

---

## Severity 2 — Structural problems that slow every change

### 2.1 Two view modules have become dumping grounds

| File | Lines | Functions |
|---|---|---|
| `proposals/views.py` | 5,002 | 117 |
| `accounts/views.py` | 3,657 | 124 |

`proposal_wizard()` alone is **631 lines**. `proposal_moa_tracker()` is 246; `proposal_storage()`
is 200.

Consequences: merge conflicts on nearly every branch, no way to navigate by file, helpers get
duplicated because nobody can find the existing one, and functions this long cannot be unit
tested in isolation.

**Fix — mechanical and safe, done incrementally.** Convert each module into a package, moving
functions without editing them:

```
accounts/views/__init__.py      # re-exports, so URLs and imports keep working
accounts/views/auth.py          # login, register, verification, password reset
accounts/views/dashboards.py    # the seven role dashboards
accounts/views/admin_users.py   # user CRUD, roles, site control
accounts/views/cms.py           # page content, home sections, workflow phases
accounts/views/reports.py       # accomplishment reports

proposals/views/__init__.py
proposals/views/wizard.py
proposals/views/review.py
proposals/views/moa.py
proposals/views/implementation.py
proposals/views/documents.py
```

The `__init__.py` re-export means `accounts/urls.py` needs no changes at all, which keeps each
step reviewable and reversible.

**Effort:** 1–2 days. **Prerequisite:** finding 1.4, or you are refactoring blind.

---

### 2.2 ✅ Role checks were scattered and inconsistent — **fixed**

26 separate inline role comparisons across `accounts/` and `proposals/`, in at least four styles:

```python
if profile.role == "ADMIN": ...
if _user_role(user) == Profile.ROLE_ADMIN: ...
if role in {Profile.ROLE_ADMIN, Profile.ROLE_DIRECTOR, Profile.ROLE_STAFF}: ...
if user_has_capability(user, RoleCapability.Capability.X): ...
```

Two parallel systems coexist: hardcoded role comparisons and the `RoleCapability` matrix. There
is no single place to answer "who can do X?", which is how the accomplishment-report permissions
drifted (see the changelog below — Admin had unintended access purely because `user_has_capability`
returned `True` for every capability when the role was Admin).

**Status:** `accounts/permissions.py` is now the single source of truth. It exposes named role
groups (`PROPOSAL_AUTHOR_ROLES`, `PHASE_MANAGER_ROLES`, `ACCOMPLISHMENT_SUBMIT_ROLES`...) and
predicates (`can_review_proposal`, `can_edit_proposal`, `can_manage_proposal_phase`,
`can_submit_accomplishment_reports`...).

The old helpers in `proposals/views.py` (`_can_edit`, `_can_review`, `_can_manage_phase`,
`_role_has_capability`, `_is_director`...) are kept as one-line delegations so no call site
changed, and `accounts/views.py` and the context processor now resolve through the same module.
Previously the context processor duplicated the role logic in a separate string comparison, so a
template and a view could disagree.

**Approach:** 30 characterisation tests were written first, pinning the existing behaviour of
every helper, and only then was the logic moved. The suite stayed green throughout, which is what
makes the change safe to review.

**Two latent bugs fixed in passing:**

* `_can_review` computed a 12-line `step_comment_counts` block — several database queries — and
  then discarded it without ever using the result. Dead code inside a permission check on every
  call. Removed.
* Scope matching was case-sensitive, so a coordinator for `Computer Science` silently could not
  review a proposal recorded as `COMPUTER SCIENCE`. Now compared case-insensitively.

---

### 2.3 70 broad `except Exception` handlers

Across `accounts/`, `proposals/`, and `details/`. Several silently swallow errors:

```python
try:
    ...
except Exception:
    capabilities = set()      # a DB error is indistinguishable from "no permissions"
```

This converts real failures into confusing behaviour — a database problem looks like a permissions
problem, and nothing is logged.

**Fix:** catch specific exceptions; where a broad catch is genuinely warranted (context processors
that must never break rendering), log the exception rather than discarding it. No `LOGGING`
configuration currently exists, so adding one is a prerequisite.

**Effort:** half a day for the worst offenders.

---

### 2.4 ✅ Stray debug `print()` statements in a hot path — **fixed in this commit**

`accounts/views.py` contained:

```python
print("ALL PROPOSALS:", Proposal.objects.count())
print("QUEUE COUNT:", review_queue.count())
for p in review_queue:
    print(p.id, p.proposal_status)
```

This ran on **every Director dashboard load**, issuing two extra `COUNT` queries and then
iterating the entire review queue purely to write to stdout — a real performance cost that grows
with the proposal table, plus noise in production logs.

**Status:** removed. This was a clear bug rather than a judgement call, so I fixed it rather than
just reporting it.

---

## Severity 3 — Consistency and maintainability

### 3.1 ✅ Dashboard styling had diverged — **substantially addressed in this commit**

Each of the seven role dashboards had grown its own near-identical CSS under a private prefix
(`.adm-*`, `.dir-*`, `.kpi-card`, `.rq-card`, `.ext-card`, `.mine-card`), with three different
heading styles, two different page backgrounds, and two different card treatments.

**Done:** a shared `nx-*` design system in `static/css/dashboard-views.css` (tokens, cards, KPIs,
tabs, buttons, badges, tables, empty states); all seven dashboards moved to a common page shell
and heading style; 36 ad-hoc card declarations normalised; the Admin and Director private palettes
re-pointed at the shared tokens via `var()` aliases.

**Remaining:** the Director dashboard still carries ~170 lines of inline `<style>`, and Admin
~120. These now *inherit* the shared tokens so they stay in visual step, but folding them fully
into the stylesheet is worthwhile follow-up. Deferred deliberately — it is cosmetic, and doing it
without tests risks breaking a working page for no functional gain.

### 3.2 Inline `<style>` and `<script>` blocks in templates

Five dashboards embed `<style>`; six embed `<script>`. This defeats browser caching, prevents any
CSS/JS tooling, and makes duplication invisible. Consolidating into `static/` is straightforward
once the shared system above is fully adopted.

### 3.3 Tailwind loaded from CDN

`templates/base.html` loads `https://cdn.tailwindcss.com`. The CDN build is explicitly documented
by Tailwind as unsuitable for production: it ships the entire framework, compiles in the browser
on every page load, and introduces a third-party runtime dependency for your site to render.

**Fix:** a build step producing a purged stylesheet. This is a genuine improvement but adds a
Node toolchain to deployment, so it is a deliberate trade-off rather than an obvious win.

### 3.4 `details` app is misnamed and overloaded

`details/models.py` now holds the public landing page, personnel, activities, processes, targets,
document templates, dynamic forms, wizard config, role capabilities, accomplishment reports, and
the new CMS models. "Details" describes none of this.

Splitting it into `content/` (CMS, pages, personnel, activities) and `config/` (templates, forms,
wizard, capabilities) would be clearer — but renaming Django apps means migration surgery and
carries real risk for modest gain. **Recommendation: leave it.** Noted for awareness, not action.

---

## Progress and what remains

**Done:**

1. ✅ `DEBUG` defaults to `False` *(1.1)*
2. ✅ `db.sqlite3` untracked *(1.2)*
3. ✅ Test suite: 0 → 96 passing tests, sabotage-verified *(1.4)*
4. ✅ Debug `print()` calls removed from the Director dashboard hot path *(2.4)*
5. ✅ Shared dashboard design system *(3.1)*

**Next, in order:**

6. **Untrack `media/`** — 5 minutes, but needs you to confirm the Supabase bucket is populated
   first. *(1.3)*
7. **Centralise permissions** into `accounts/permissions.py` — ~1 day, highest security value per
   hour, and now safe because the permission tests will catch any behaviour change. *(2.2)*
8. **Extend test coverage** to the proposal wizard, document generation, and the MOA and
   implementation branches — 2–3 days. Required before step 9. *(1.4)*
9. **Split the two view modules** — 1–2 days, mechanical. *(2.1)*
10. **Tighten exception handling, add logging** — half a day. *(2.3)*
11. Cosmetic CSS/JS consolidation and the Tailwind build, if and when they start costing time.

The test suite is in place, so steps 7 and 9 are now routine rather than risky — provided step 8
lands before anyone touches `proposals/views.py`.

---

## Explicitly not recommended

- **A rewrite or framework change.** The domain model is genuinely good: the proposal lifecycle,
  MOA branch, and role structure reflect a real institutional process that would be expensive to
  rediscover. The problems are organisational, not architectural.
- **Renaming the `details` app.** Migration risk outweighs the clarity gain. *(3.4)*
- **Large refactors before tests exist.** The most likely outcome is a subtly broken approval
  workflow that nobody notices until a proposal is stuck.
