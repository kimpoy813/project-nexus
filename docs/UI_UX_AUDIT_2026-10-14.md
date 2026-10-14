# NExUS system / UI / UX audit

Date: 2026-10-14. Branch: `arena/d5978f25-project-nexus`.

## Scope and limits

This is a repository-wide review with cross-cutting fixes, regression tests, and
browser checks — **not a claim that every possible production state has been
certified**. Tests used local SQLite, generated test accounts, and synthetic
proposal data. No production database, production users, real mail service, or
live Supabase bucket was modified or verified.

The existing architecture and institutional visual identity are retained. This
was not a rewrite of the application or an unreviewed change to approval rules.

## Flow map

1. **Public information:** Home, Services, Reports and Achievements compose
   admin-managed page sections/content sources. Services introduces the workflow.
2. **Account entry:** registration with organizational scope → email verification
   → username/email sign-in → role dashboard. Password recovery is email-based.
3. **Authoring:** an eligible author creates a proposal; its 20 built-in wizard
   steps collect scope/type, title, proponents, agency, beneficiaries, SDGs and
   agenda, utility model, budget, participant counts, gender issues, venue/date,
   rationale, significance, objectives, methods, outcomes and supporting files.
   Admin-configured fields and repeaters supplement/mirror the built-in fields.
4. **Review:** submission locks normal editing; scoped coordinators, Director and
   assigned evaluators review. Review rounds and staff summaries support return
   for revision and resubmission. Author/collaborator access remains object-based.
5. **Approval documents:** approved proposal generation, signed upload, staff
   release/claim and document storage.
6. **MOA:** draft/steps/summary → legal review and revisions → certification/
   presentation → completion; proposals may have a not-required MOA.
7. **Implementation:** preparation, activity/reporting, monitoring, revision and
   final documentation. The model derives lifecycle progress from phase state.
8. **Supporting workflows:** coordinators submit accomplishment reports; authorized
   readers review them. Admin manages accounts, scopes, signatories, content,
   document templates, wizard configuration and role capabilities.

Business enums, authorization rules and default document layouts are legitimate
code, not dummy content. Historical migration seed data remains immutable; it no
longer overrides live organizational choices at runtime.

## Findings fixed

| Finding | Fix / evidence |
|---|---|
| Hidden custom selects broke keyboard/mobile behavior, disabled options and native validation | Removed global select replacement; styled native selects remain the real controls. |
| Default wizard chips printed and posted Python tuples | Normalized Django choice tuples and admin dictionaries. Chips now submit actual values and support keyboard activation/pressed state. |
| Forged wizard choices could be persisted | Step 1 validates rendered choice values before saving and returns errors without discarding valid entered selections. Skip still allows an unfinished step. |
| Editing UI could disagree with access rights | Wizard edit mode now checks edit permission as well as status. Explicit read-only collaborators may view but cannot edit; unrelated users stay denied. |
| Deleting colleges/departments resurrected hard-coded seed choices | Runtime choices and validation now query managed tables only; empty tables stay empty. Database failures are logged, not replaced with misleading choices. |
| Four copies of account cascades could race or silently erase values | Shared organization-field controller: abort/stale-response guards, loading state, retry, saved-value preservation, and prevention of saving unresolved fields. |
| Admin account edits bypassed create-time validation | Bound edit form validates usernames, unique email, roles, passwords and organizational relationships. Invalid edits do not partially save; errors are inline and input is preserved. Unchanged legacy scopes remain editable. |
| Brand settings only changed part of the UI | Validated runtime color tokens feed utility colors/opacity and shared component styles, including admin editors. Email/Word document styling was not blindly converted to CSS variables. |
| UI depended on runtime third-party CDNs | Compiled Tailwind, Alpine, AOS, Chart.js, Sortable and Inter are served locally. Pinned lockfile, build script and licenses are included. |
| Server/cookie/browser inactivity limits disagreed | One configurable timeout, activity renewal with CSRF, warning/countdown, suspended-tab expiry and same-user tab coordination. Anonymous pages do not run idle logout. |
| GET navigation could log out or send password-reset email | Logout now requires a CSRF-protected POST. Password change GET is a confirmation; sending requires POST and handles delivery failure. |
| Legacy duplicate emails caused sign-in errors | Email ambiguity prompts username sign-in instead of crashing or choosing an arbitrary account. Failed sign-in retains identifier and destination, never the password. |
| Contact settings could not be cleared; malformed URL could be stored | Optional contact values can be cleared, settings are validated, and blank footer contacts no longer invent fallback links. |
| Shared navigation repeated role-routing logic | Uses named routes and the existing dashboard router. Profile/notification controls expose expanded state; menus close with Escape. |
| Mobile template-library overflow and desktop mobile-menu button | Shrinkable grid children/native controls; corrected responsive visibility. |
| Footer year was empty; shared accessibility gaps | Dynamic year, focusable skip destination, focus styling, disabled states and reduced-motion support. |
| Unused React starter counter/assets confused the frontend purpose | Removed unused starter files and documented the actual toaster/static-asset pipeline. |
| Checks were not automated together | Added a CI workflow for Python/JS tests, lint, build, migration drift, generated-asset drift and collectstatic. The workflow itself has not yet run on GitHub. |

## Verification

- Baseline: **737 Django tests, 41 JavaScript tests** passing.
- After the initial fixes: **773 Django tests, 56 JavaScript tests** passing.
- After the dedicated design pass: **782 Django tests, 60 JavaScript tests** passing.
- Django system check: **no issues**. Migration drift check: **no changes**.
- Frontend production build and ESLint pass. `collectstatic` succeeds with the
  new local assets and WhiteNoise post-processing.
- Initial browser checks: 42 page/viewport combinations across all seven roles,
  plus 40 checks covering wizard steps 1–20 at 390px and 1440px.
- Expanded browser sweep: **112 successful page/viewport landing checks** covering
  public/auth pages, all role dashboards, account/profile forms, admin builders,
  template lists, accomplishment screens and proposal trackers. No uncaught JS
  errors, failed assets, leaked template comments or page-level horizontal
  overflow were observed. The upload-signed route correctly redirected for a
  draft rather than rendering an approval-only form; that is not an approved
  upload certification. Six POST-only action routes were also probed at both
  sizes and correctly returned 405 to GET (12 additional checks).
- Browser interactions: keyboard-only proposal type/scope selection and next-step
  save; campus/college/department cascade; mobile menu/Escape; simulated cascade
  network failure and Retry; invalid admin edit with inline errors and retained
  input.
- Production npm dependency audit: **0 reported vulnerabilities** at audit time.
  Full npm audit still reports **7 build-tool dependency advisories** (Tailwind 3
  transitive dependencies). Their reported automatic remediation upgrades
  Tailwind to a breaking major version. Do not apply `npm audit fix --force`
  without a separate CSS compatibility pass; build only trusted repository input.

Commands:

```sh
python manage.py test --settings=conf.settings_test
node --test tests/*.test.cjs
npm ci --prefix frontend
npm run lint --prefix frontend
npm run build --prefix frontend
python manage.py check
python manage.py makemigrations --check --dry-run
python manage.py collectstatic --noinput
```

## Dedicated design-consistency pass

The follow-up goes beyond a shared palette: over 120 application templates now
explicitly adopt shared components. This includes 471 action controls, 262
panels, 76 page titles, 43 heading wrappers, 33 tables and 169 badges. Existing
page-specific classes remain where scripts or layout depend on them.

- Added a shared component contract for button/field geometry, typography,
  borders, shadows, heading rhythm and semantic action variants.
- Removed legacy high-specificity card heuristics that overrode the new panels;
  removed bare color-utility button styling that also affected progress bars.
- Preserved status colors, marketing/auth display typography, selection controls
  and document/CKEditor layouts as intentional differences.
- Collapsed the wizard's lengthy step list on mobile using an accessible native
  disclosure; desktop and no-JavaScript navigation stay available.
- Added an actionable not-started MOA status instead of an empty status panel.
- Fixed the faculty revision-summary link to use its actual named route.
- Fixed a malformed CSS comment that swallowed the shared container rule.

Verification was repeated after restarting the Django template cache:

- **164 page/viewport checks:** 152 successful landings, including all 20 wizard
  steps at both widths, plus 12 expected GET/405 responses for POST-only actions.
  No unexpected HTTP/asset failures, uncaught JavaScript errors, leaked template
  comments or page-level horizontal overflow were observed.
- Computed styles were checked for visible annotated actions/panels across that
  sweep. Standard actions use 44px minimum height, 12px corners and 14px/600 type;
  compact editor actions use 36px minimum height and 13px/600 type. Panels share
  16px corners and the same border color.
- Detailed measurements/screenshots for campus management, content management,
  wizard, MOA and login at both widths additionally confirm matching panel
  shadows. Login username/password fields share 44px minimum height, 12px
  corners and 14px type.
- Mobile keyboard disclosure, in-page navigation/reinitialization, breakpoint
  changes and no-JavaScript wizard navigation passed browser interaction checks.
- Added nine Django design/rendering regressions and four JavaScript navigation
  regressions. Frontend build and ESLint pass.

See [the shared design contract](DESIGN_SYSTEM.md) for component usage and checks
for future pages. These checks cover synthetic local states; they do not certify
every populated, permission-specific or historical state, or every browser.

## Deployment / further validation

- Set `IDLE_TIMEOUT_SECONDS` (default 600). The effective limit is capped by
  `SESSION_COOKIE_AGE`. Existing 600-second deployments retain a ten-minute limit.
- Rebuild and commit static assets when templates introduce new utility classes.
  Python-only hosting can keep its existing collectstatic-based build. See
  `frontend/README.md`.
- Any external integration calling GET `/logout/` must switch to a CSRF-protected
  POST. Password reset sending likewise requires explicit confirmation.
- **Production settings still need deployment verification:** a local
  `check --deploy` flags the development fallback SECRET_KEY, HTTPS redirect and
  HSTS. Set a strong deployment secret and verify HTTPS at the proxy; HSTS must
  match the real domain configuration, not be enabled blindly here.
- **Not exercised live:** SMTP verification/recovery delivery; Supabase writes,
  permissions and file downloads; PostgreSQL/concurrent reviewers; production
  backups and migrations; browser-specific Safari/Firefox/mobile assistive
  technology; every populated/legacy/revision state of every screen.
- **Not replaced with guessed configuration:** statutory/institutional wording in
  generated MOAs (for example `proposals/moa_docx.py`), institutional logos,
  document structure and stable workflow codes. Decoupling these for a different
  institution requires approved content and a data-migration plan, not search and
  replace. Most content already has builders; those remain the source of truth.
- Screen-specific markup and some local component styling remain. These changes
  resolve shared defects, not a complete conversion of every historical template
  to a new component framework. Accessibility checks here are targeted, not WCAG
  certification. Arbitrary admin-selected colors still need contrast review.
