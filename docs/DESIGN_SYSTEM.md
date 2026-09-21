# NExUS Design System

One visual language for the whole system. Every page — public site, role
dashboards, admin workspace, wizard, trackers, auth — is built from the
pieces below. If a new screen needs a button, card, badge, input, table, or
page header, it reuses these; it never invents a sibling.

## Stylesheet ownership

Each layer owns its rules; nothing is defined twice.

| File | Owns |
|---|---|
| `static/js/nexus-theme.js` | Tailwind tokens: brand palette + the single typeface. Loaded on every Tailwind page. Keep in sync with `nexus-ui.css`. |
| `static/css/nexus-ui.css` | Global shell: typeface rule, navbar, footer, toasts, raw-element normalisers (`input`/`select`/`textarea`, `thead`/`tbody`, `.bg-primary` buttons), progress rings. |
| `static/css/nexus-layout.css` | Fluid layout: `.nx-page` gutters, `.nx-form-grid`, `.nx-auto-grid`, splits, auth and wizard shells. |
| `static/css/dashboard-views.css` | **The component library.** Every card, KPI, tab, button, input, badge, table, avatar, chip, notice, and dashboard widget, with legacy class names kept as aliases. |
| `static/css/nexus-richtext.css` | CKEditor output typography on public pages. |
| `static/css/nexus-skeleton.css` | Loading skeletons (one layout per page family). |
| `static/css/public-pages.css` | Home/Services landing refinements only. |

Rules of the road:

- **No inline `<style>` blocks in templates.** Email templates are the only
  exception (email clients require inline CSS). `templates/base.html` keeps
  three tiny blocks: DB-driven brand vars, `[x-cloak]`, and the noscript
  skeleton guard.
- **New code uses the `nx-*` name.** The legacy prefixes (`dir-*`, `adm-*`,
  `pc-*`, `ht-*`, `ps-*`, `.badge`, `.kpi-card`, …) keep working as aliases
  in the same rule, so old markup renders the unified look — but no new
  markup should use them.
- **Never hard-code a colour that has a token.** Brand colours come from
  `SiteControl` (via `base.html` CSS vars) so an admin rebrand reaches every
  component; component CSS must reference the vars, not the hex.

## Canonical scale

- Cards: **16px** (`--nx-radius`) — `.nx-card`, section containers, modals.
- Nested record cards, KPI tiles, buttons, sidebar nav: **12px**
  (`--nx-radius-md`).
- Text inputs / selects / textareas: **.9rem** (`--nx-radius-control`),
  with the shared green focus ring. The rule lives in both `nexus-ui.css`
  (bare elements) and `dashboard-views.css` (input classes) with identical
  values.
- Pills / avatars / dots: **999px**.
- One typeface: **Inter** (400–900), enforced globally in `nexus-ui.css`
  and aliased for `sans`/`serif`/`mono` in `nexus-theme.js`, so no markup
  can drift to another font.

## Components

- **Buttons** — Primary: green gradient, white 600 text, shared shadow and
  hover lift (`.nx-btn--primary` and aliases, plus every raw `bg-primary`
  link/button via the normaliser). Primary actions render larger than
  their adjacent secondary actions — size carries hierarchy, style stays
  uniform. Secondary: `.nx-btn` (white, slate text, subtle hover lift).
  Brand-ghost: `.nx-btn--outline` (green text/border, fills on hover).
  Danger: red text/border (`.nx-btn--danger`). Small: `.nx-btn--sm`.
  Icon-only: `.nx-icon-btn` (+ `--danger`, which fills red on hover).
  Text links: `.nx-link` (+ `--danger`). The `rounded-full` pill button is
  the one sanctioned shape variant (navbar Login, CTAs). Every
  `<button>`/`<a>` class string in the system was inventoried (528
  elements); anything below not listed under deliberate non-uniformities
  is a bug.
- **Badges** — One pill shape. Two colour languages that are *not* drift:
  status (`--ok/--warn/--danger/--info/--muted`: lime/amber/red/blue/slate)
  reports state; stage (`.badge-green/red/amber/blue/purple/gray`: the
  workflow greens/maroons/ambers/blues/purples) reports the proposal stage.
- **Cards** — `.nx-card` with `__head/__title/__sub/__body/__foot`;
  `.section-block` + `.section-block-head` + `.dir-card-accent` for
  dashboard panels; `.ext-card/.rq-card/.mine-card` (12px, column flex,
  footer pinned) and `.prop-row` for records nested inside panels.
- **KPI** — `.nx-kpi` (label/value/hint) plus the `.kpi-card` accent
  variant whose top border and value colour come from per-card styles.
- **Tabs** — Underline tabs (`.nx-tabs/.nx-tab`) for panels; sidebar nav
  (`.nx-nav-btn`) for rail navigation.
- **Forms** — `.nx-label`, `.nx-input` (+ `--sm`), shared select caret,
  `.nx-error` for validation messages.
- **Tables** — `.nx-table` with `.nx-th/.nx-td`; the global `thead/tbody`
  rules give raw tables the same header treatment and row hover.
- **Avatar / chips** — `.nx-avatar`, `.ev-chip` for removable assignments.
- **Modal** — One delete-confirm frame shared byte-for-byte by every
  dashboard: `bg-gray-900/40` backdrop, `max-w-md rounded-2xl` panel.
- **Page headers** — Dashboards and every workspace page (CRUD, builders,
  review, profile): `.nx-dash__title` + `.nx-dash__subtitle` inside
  `.nx-page.py-8`. Wizard/tracker pages are their own family:
  `text-2xl sm:text-3xl font-bold tracking-tight text-gray-900`.
  Marketing heroes and auth cards stay distinct on purpose.

## Page families

The skeleton system (`nexus-skeleton.css`, `data-nx-variant`) names the
families: `marketing`, `auth`, `dashboard`, `wizard`, `tracker`, `list`,
`form`, `record`. Unity means *within* a family first: all dashboards
share one header/card/button language; all workspace lists share one;
wizard and tracker screens share theirs. Families differ in layout, never
in atoms (radius, type, colour, focus rings).

## Deliberate non-uniformities (do not "fix")

- `slate-*` vs `gray-*` text: visually identical (`#0f172a` vs `#111827`);
  dashboards lean slate, wizard leans gray. Leave both.
- `hover:bg-secondary` on `bg-primary` buttons is dead (the gradient
  `!important` wins) but harmless; the rendered hover is the gradient
  shift, uniform everywhere.
- Chart/gauge colours are hard-coded hex in JS (canvas cannot read CSS
  vars cheaply); they mirror the stage palette by hand.
- Admin toggle switches repeat one long Tailwind class string in ~17
  files. It is uniform; extracting a class is possible future DRY work
  with zero visual gain.
