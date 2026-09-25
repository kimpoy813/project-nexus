# NExUS interface guide

The site is a trust-first extension office workspace, not a generic SaaS theme. Keep the existing Django templates, Tailwind utilities, CMS models, and institutional mark. Public pages can be more editorial; dashboards and the proposal wizard should stay dense, predictable, and accessible.

## Foundations

- **Type:** self-hosted Public Sans for body, controls, and tables; Manrope for headings and large metrics. Files and OFL licenses are in `static/fonts/`. Do not introduce a third UI font or depend on a Google Fonts request.
- **Color:** forest green (`--nexus-primary`) is the interactive accent; ink (`--nexus-ink`) and muted green-gray (`--nexus-muted`) carry text. Maroon and gold belong to the institutional logo and meaningful phase/progress indicators. Red, amber, and green may signal error, attention, and success. Don't color-code decoration without a text label.
- **Surfaces:** use `--nexus-bg`, `--nexus-bg-2`, `--nexus-surface`, `--nexus-line`, `--nexus-shadow-sm`. Choose a hairline over a raised shadow for working panels. Keep copy at a comfortable measure while letting data tables use the full viewport.
- **Spacing:** use the fluid `nx-page` gutter and `nx-form-grid` for forms. Preserve `nexus-shell` and the fixed header offset (`--nx-header-h`: 5rem desktop, 4.5rem mobile). Do not bring back capped `max-w-7xl mx-auto` page shells.
- **Interactive controls:** one solid green primary action per section; quiet secondary actions. Labels, keyboard focus, disabled states, field errors, and confirmation text should remain explicit. Reduced-motion users must not depend on animation for information.

## Page families

| Screen | Pattern | Where to make changes |
| --- | --- | --- |
| Home, Services, Reports, Achievements | Full-bleed editorial hero, compact section links, readable CMS content and empty states | `static/css/public-pages.css`, `static/css/nexus-richtext.css`, public block templates |
| Sign in, register, password recovery | Split brand panel and light form card; inline errors and useful password rules | `accounts/_auth_panel.html`, `static/css/nexus-ui.css`, `static/css/nexus-layout.css` |
| Role dashboards, account screens | Fluid working area, KPI tiles, tables, semantic status badges, contextual empty states | `static/css/dashboard-views.css`, role templates |
| Proposal wizard and trackers | Stepper plus form, optional review rail; native form elements and persistent draft state | `static/css/nexus-layout.css`, wizard shell/stepper templates |
| Admin lists and editors | Dense, scrollable tables and paired field grids; retain native forms and server validation | `static/css/nexus-ui.css`, `static/css/nexus-layout.css` |
| Errors and maintenance | Small, direct explanation and a way out | `templates/404.html`, `templates/500.html`, `templates/maintenance.html` |

Skeletons in `templates/base.html` and `static/css/nexus-skeleton.css` should roughly match each page family's shape. `frontend/tailwind.config.cjs` generates the matching utility palette in `static/css/nexus-tailwind.css` (`npm --prefix frontend run build:django-css`); the shared stylesheet supplies semantic component styles. Alpine, AOS, Chart.js, and SortableJS are served locally from `static/vendor/`. Admin-editable copy, workflow phases, and metrics remain sourced from their existing models; don't replace them with static marketing claims. New images or icons should communicate actual content rather than fill space. Prefer restrained transitions, native fragment links, visible focus, and labeled form fields.
