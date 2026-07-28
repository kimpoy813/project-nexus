# NExUS Architecture Audit

**Date:** 2026-07-28
**Scope:** Whole repository — ~16,500 lines of Python, ~17,900 lines of templates, 4 Django apps
**Status:** Findings only. Nothing in this document has been actioned except where explicitly marked ✅.

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

### 1.1 `DEBUG` defaults to `True`

`conf/settings.py:41`

```python
DEBUG = env_bool("DEBUG", True)
```

If `DEBUG` is ever unset in the production environment, Django serves full stack traces with
source, local variables, and settings to any visitor who triggers an error. This is the single
highest-impact issue in the repo, and it is a one-line fix.

**Fix:** default to `False`. Development can opt in via `.env`.

```python
DEBUG = env_bool("DEBUG", False)
```

**Effort:** minutes. **Risk of fixing:** none.

---

### 1.2 `db.sqlite3` is committed to Git

The 1.2 MB SQLite database is tracked, despite `.gitignore` listing `db.sqlite3` and `*.sqlite3`
(the ignore rules do not apply to already-tracked files).

Consequences:
- Real user records, including password hashes, live in Git history.
- Every developer's local data churn produces spurious diffs and merge conflicts.
- Production runs PostgreSQL, so the committed file is misleading.

**Fix:** `git rm --cached db.sqlite3`. Note this only stops future commits; the data remains in
history. If the database ever held real credentials, those should be rotated, and purging history
(`git filter-repo`) is worth considering.

**Effort:** minutes to stop the bleeding; longer if history must be purged.

---

### 1.3 47 uploaded media files are committed

`git ls-files media/ | wc -l` → 47

`.gitignore` excludes `media/`, but these predate the rule. Production uses Supabase Storage, so
these are dead weight that will keep growing if anyone commits before the ignore takes effect.

**Fix:** `git rm -r --cached media/` once you have confirmed the files exist in Supabase.

---

### 1.4 Effectively no test coverage

| File | Lines |
|---|---|
| `accounts/tests.py` | 3 |
| `details/tests.py` | 3 |
| `proposals/tests.py` | 34 |
| **Total** | **40** |

40 lines of tests for 16,500 lines of application code, covering a multi-role approval workflow
with document generation and role-based permissions.

This is the finding that gates everything else. **Every other refactor in this document is
dangerous until this is addressed**, because there is currently no way to know whether a change
broke the proposal lifecycle short of clicking through it manually.

**Suggested first targets**, in order of value:

1. **Permissions** — who may view/submit/approve at each stage. Highest value: security-relevant,
   fast to write, and exactly the logic most likely to regress silently.
2. **Proposal lifecycle** — draft → submit → review → revise → approve, plus the MOA and
   implementation branches.
3. **Auth** — registration, email verification, lockout, password reset.
4. **CMS/admin** — the page content and workflow-phase editors.

I have written throwaway integration suites while making the recent changes (roughly 240 checks
across four features). Those were deliberately not committed because they were scaffolding, but
they demonstrate the approach works well here: Django's test client exercises real URLs, real
permissions, and real templates without needing a browser. **Converting that approach into a
committed `tests/` package is the highest-value next step available.**

**Effort:** 2–4 days for meaningful coverage of the four areas above.

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

### 2.2 Role checks are scattered and inconsistent

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

**Fix:** one `accounts/permissions.py` exposing named predicates — `can_review_proposal(user,
proposal)`, `can_submit_accomplishment(user)` — with views calling those exclusively. The recent
`ACCOMPLISHMENT_SUBMIT_ROLES` / `ACCOMPLISHMENT_VIEW_ONLY_ROLES` constants are a small example of
the target shape.

**Effort:** 1 day, and it directly reduces the chance of a permissions bug.

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

## What I would actually do, in order

1. **`DEBUG=False` default** — minutes, removes the largest production risk. *(1.1)*
2. **Untrack `db.sqlite3` and `media/`** — minutes. *(1.2, 1.3)*
3. **Build the test suite** — 2–4 days. Everything below depends on it. *(1.4)*
4. **Centralise permissions** — 1 day, highest security value per hour. *(2.2)*
5. **Split the two view modules** — 1–2 days, mechanical once tests exist. *(2.1)*
6. **Tighten exception handling, add logging** — half a day. *(2.3)*
7. Cosmetic CSS/JS consolidation and the Tailwind build, if and when they start costing time.

Steps 1 and 2 are safe to do immediately. **Step 3 is the real unlock** — it is what converts
steps 4–6 from risky to routine.

---

## Explicitly not recommended

- **A rewrite or framework change.** The domain model is genuinely good: the proposal lifecycle,
  MOA branch, and role structure reflect a real institutional process that would be expensive to
  rediscover. The problems are organisational, not architectural.
- **Renaming the `details` app.** Migration risk outweighs the clarity gain. *(3.4)*
- **Large refactors before tests exist.** The most likely outcome is a subtly broken approval
  workflow that nobody notices until a proposal is stuck.
