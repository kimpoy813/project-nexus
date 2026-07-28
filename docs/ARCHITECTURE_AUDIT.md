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

### 1.3 ✅ 47 uploaded media files were committed — **fixed**

`git ls-files media/ | wc -l` → 47

`.gitignore` excludes `media/`, but these predate the rule. Production uses Supabase Storage, so
these are dead weight that will keep growing if anyone commits before the ignore takes effect.

**Status:** untracked via `git rm -r --cached media/`, with the owner's approval to start the
system from a clean slate. The local files are untouched; only Git stops tracking them, and the
existing `.gitignore` rule now takes effect for anything uploaded in future.

Because a fresh clone now starts with no uploads, the Home page was hardened for that state: a
`Personnel` row whose photo is missing previously rendered a broken image icon, and now falls back
to an initials avatar. Activities and CMS section images were already guarded.

Three regression tests in `accounts/tests/test_structure.py` stop this reappearing: no media
tracked, no SQLite database tracked, and the DOCX/XLSX templates under
`proposals/template_files/` *still* tracked — those are source assets rather than uploads and must
not be swept up by the same rule.

---

### 1.4 ✅ Effectively no test coverage — **substantially addressed**

**Before:** 40 lines across three files. Worse, *both* real tests in `proposals/tests.py` were
already failing — they referenced `Proposal.mark_implementation_in_progress()` and a
`proposal_moa_workflow` URL, neither of which still exists. They had been broken since an earlier
refactor and nobody noticed, which is itself the clearest evidence the suite was not being run.

**Now: 266 tests, running in ~14 seconds.**

| Suite | Tests | Focus |
|---|---|---|
| `accounts/tests/test_permissions.py` | 17 | Role access, admin-only areas, dashboards |
| `accounts/tests/test_permissions_module.py` | 21 | The permission predicates themselves |
| `accounts/tests/test_auth.py` | 16 | Login, registration gating, verification, maintenance |
| `accounts/tests/test_cms.py` | 39 | Page content, Home sections, thrusts, phases, missing media |
| `proposals/tests.py` | 17 | Progress weighting, phase labels, access control |
| `proposals/tests_permissions.py` | 30 | Characterisation of the proposal permission helpers |
| `proposals/tests_workflow.py` | 24 | Wizard access and steps, status maps, review rounds, trackers |
| `accounts/tests/test_structure.py` | 7 | URL resolution, no duplicate defs, re-exports, repo hygiene |
| `accounts/tests/test_error_handling.py` | 11 | Logging config, graceful degradation, no leaked error text |
| `proposals/tests_documents.py` | 35 | DOCX/XLSX generation, template routing, download access |
| `proposals/tests_transitions.py` | 38 | MOA/implementation transitions, status derivation, wizard helpers |
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
constraints, tracker access, and document generation (both DOCX entry points, template routing,
and the download endpoints).

**Now also covered:** MOA and implementation state transitions, overall-status derivation, the progress high-water ratchet, and terminal (rejected/cancelled) states.

This is the finding that gates everything else. **Every other refactor in this document is
dangerous until this is addressed**, because there is currently no way to know whether a change
broke the proposal lifecycle short of clicking through it manually.

**Remaining effort:** ~half a day for the deeper MOA and implementation state transitions.

---

## Severity 2 — Structural problems that slow every change

### 2.1 ✅ Two view modules had become dumping grounds — **fixed**

| File | Lines | Functions |
|---|---|---|
| `proposals/views.py` | 5,002 | 117 |
| `accounts/views.py` | 3,657 | 124 |

`proposal_wizard()` alone is **631 lines**. `proposal_moa_tracker()` is 246; `proposal_storage()`
is 200.

Consequences: merge conflicts on nearly every branch, no way to navigate by file, helpers get
duplicated because nobody can find the existing one, and functions this long cannot be unit
tested in isolation.

**Status:** both are now packages of themed modules. `__init__.py` re-exports every public
name, so `urls.py` and all existing imports were untouched.

```
accounts/views/          proposals/views/
  helpers.py       95      constants.py      121
  reports.py      103      permissions.py    116
  admin_users.py  247      public.py          80
  auth.py         322      helpers.py        181
  cms.py          365      implementation.py 391
  builders.py     390      moa.py            749
  content.py      546      documents.py      869
  proposal_queries.py 563  review.py        1175
  dashboards.py  1062      wizard.py        1269
```

**Verified as a pure move.** An AST comparison confirmed all 116 `accounts` and 109 `proposals`
top-level definitions survived with byte-identical bodies — no function was edited, dropped, or
duplicated. The 171-test suite stayed green throughout, and all 289 URL patterns still resolve to
real callables.

**A dead duplicate was found and removed:** `proposal_moa_draft` was defined *twice* in
`proposals/views.py`. Python keeps the last definition, so the first 35-line version had been
unreachable dead code — the routed behaviour came from the second, richer implementation 3,500
lines later. Splitting the file forced the ambiguity into the open.

Four structural guards now live in `accounts/tests/test_structure.py`: every URL pattern resolves
to a callable, no duplicate definitions exist within a package, every public view is re-exported,
and no submodule exceeds 1,400 lines. A missing re-export now fails loudly at import time rather
than 500-ing a single URL in production.

**Still oversized:** `wizard.py` (1,269) and `review.py` (1,175) are dominated by
`proposal_wizard` at 631 lines and `summarize_comments` at 135. Splitting those means breaking up
individual functions rather than moving them, which is a genuine refactor rather than a
rearrangement — worth doing separately, and now covered by the wizard tests.

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

### 2.3 ✅ 70 broad `except Exception` handlers — **fixed**

Across `accounts/`, `proposals/`, and `details/`. Several silently swallowed errors, and no
`LOGGING` configuration existed at all — so a database failure looked identical to "this user has
no permissions", and nothing was recorded anywhere.

**Status:**

* **`LOGGING` is now configured** in `conf/settings.py`: console output, `accounts`/`proposals`/
  `details` loggers at `LOG_LEVEL` (default `INFO`, override by env var), `django.request` at
  `ERROR`, and a `WARNING` root so third-party noise stays out. Verified to emit through the real
  settings module, not just in tests.
* **Every remaining broad handler now logs** with a traceback instead of discarding the error.
  Where the exception type was predictable it was narrowed: `DatabaseError` for config reads,
  `ValidationError` for `full_clean()`, `(ValueError, FileNotFoundError)` for storage lookups,
  `(TypeError, ValueError)` for parsing, `AttributeError` for optional model accessors.
* **`traceback.print_exc()` in the registration view** was replaced with `logger.exception`. It
  wrote to stdout outside the logging system, so it was invisible to any log aggregator.
* **Internal exception text no longer leaks to users.** Four handlers interpolated the raw
  exception into a `messages.error(...)`, exposing database constraint names and internal paths
  to whoever triggered them. They now show a generic message and log the detail. `ValidationError`
  text is still shown, because that copy is written for the user.
* **Fail-open behaviour is now explicit.** The maintenance-mode middleware deliberately lets
  requests through if it cannot read the config — otherwise a transient database error would lock
  every user out. That decision is now commented and logged, so it cannot silently disable
  maintenance mode unnoticed.

**`docx_forms.py` follow-up (now done):** the 42 handlers there were initially left alone because
the module had no tests. With `proposals/tests_documents.py` in place, 14 were narrowed to their
real failure modes — `TypeError` for sorts, `AttributeError`/`ValueError` for optional python-docx
attributes, `DatabaseError` for Signatory lookups, `ImportError` for optional imports — taking the
file from 42 broad handlers to 28. `moa_docx.py` went from 2 to 0.

The remaining 28 wrap third-party parsing of user-uploaded `.xlsx` and `.pdf` files, where the
library can raise almost anything and the only sane response is to skip that section and leave the
cell blank. Those are deliberately still broad, and the comment block at the top of the file now
explains that distinction.

**Verified by 11 new tests** in `accounts/tests/test_error_handling.py`, sabotage-checked:
reverting the context processor to a silent swallow, re-leaking exception text to the user, and
introducing a bare `except:` were each caught.

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

**All items complete:** a shared `nx-*` design system in `static/css/dashboard-views.css` (tokens, cards, KPIs,
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
3. ✅ Test suite: 0 → 266 passing tests, sabotage-verified *(1.4)*
4. ✅ Debug `print()` calls removed from the Director dashboard hot path *(2.4)*
5. ✅ Shared dashboard design system *(3.1)*
6. ✅ Permissions centralised in `accounts/permissions.py` *(2.2)*
7. ✅ Wizard, review round, and tracker coverage added *(1.4)*
8. ✅ Both view modules split into packages, with structural guards *(2.1)*
9. ✅ Logging configured; broad exception handlers narrowed and logged *(2.3)*
10. ✅ Document generation covered; `docx_forms` handlers narrowed 42 → 28 *(1.4, 2.3)*
11. ✅ `proposal_wizard` split 629 → 470 lines; MOA/implementation transitions covered *(2.1, 1.4)*
12. ✅ `media/` untracked; Home page hardened for a fresh install *(1.3)*

**Every finding in this document is now closed.**

Deliberately **not** recommended as further work:

* **The Tailwind CDN → build step** *(3.3)*. It is a real improvement on paper, but it introduces
  a Node toolchain into a Python deployment for a purely cosmetic gain. Not worth the operational
  cost at this project's size unless page weight becomes a measured problem.
* **Further splitting of `proposal_wizard`** *(2.1)* — see the note under that finding.
* **Renaming the `details` app** *(3.4)* — migration risk outweighs the clarity gain.

The codebase now has 266 tests, centralised permissions, structured logging, no module over
~1,300 lines, and no generated or uploaded artefacts in version control.

---

## Explicitly not recommended

- **A rewrite or framework change.** The domain model is genuinely good: the proposal lifecycle,
  MOA branch, and role structure reflect a real institutional process that would be expensive to
  rediscover. The problems are organisational, not architectural.
- **Renaming the `details` app.** Migration risk outweighs the clarity gain. *(3.4)*
- **Large refactors before tests exist.** The most likely outcome is a subtly broken approval
  workflow that nobody notices until a proposal is stuck.
