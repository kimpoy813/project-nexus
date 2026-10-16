# NExUS shared UI contract

The application keeps its existing institutional identity and workflow-specific
layouts. Pages should share component geometry and hierarchy, not independently
invent buttons, cards, typography and colors.

## Source of truth

- Runtime brand colors: `templates/partials/_theme.html` and `accounts/ui.py`.
- Shared components: `static/css/nexus-components.css`, loaded **after** legacy
  styles and `extra_head` in `templates/base.html`.
- Fluid layout/gutters: `static/css/nexus-layout.css`.
- Native fields, focus, disabled states: shared UI/component styles. Do not
  replace native selects with global JavaScript imitations.

| Component | Contract |
|---|---|
| Page heading | `nx-page-header`, `nx-page-title`, `nx-page-description`; actions wrap on narrow screens. Internal titles use a responsive scale and primary color. |
| Action | `nx-btn` plus one of `nx-btn--primary`, `nx-btn--secondary`, `nx-btn--danger`, `nx-btn--context`. Normal actions have 44px minimum height, 12px corners, 14px/600 type. |
| Dense action | Add `nx-btn--compact` only for editor/row actions: 36px minimum height, 13px/600 type. Do not compact the main page action. |
| Icon action | Add `nx-btn--icon` and an accessible name; preserve focus treatment. |
| Panel | `nx-panel`: 16px corners, shared neutral border, subtle stationary shadow. Optional `nx-panel__header` and `nx-panel__body` provide shared padding. |
| Table | `nx-table`: shared header/cell rhythm, with a horizontally scrollable wrapper where needed. Preserve numeric alignment. |
| Table/card switch | `.dashboard-view-toolbar` holding two `.dashboard-view-toggle` buttons: one pill track with a thumb that slides under the pressed icon. Keep the pill clear of the panel edge (injected switches carry their own inset), keep the glyphs distinguishable (framed grid with a header row for the table, a pair of content cards for the card view), and keep the accessible names/tooltips. `static/js/dashboard-views.js` keeps every proposal table on the page in step and remembers the choice. |
| Badge | `nx-badge`: shared pill geometry/type. Keep semantic status/role colors and a text label; color must not be the only status signal. |
| Field | Standard native text inputs/selects share 44px minimum height and 12px corners. Dense editor fields and multiline textareas are intentional exceptions. |

Example page structure:

```html
<div class="nx-page py-8">
  <header class="nx-page-header">
    <div>
      <h1 class="nx-page-title">Page title</h1>
      <p class="nx-page-description">Purpose or next step.</p>
    </div>
    <div class="nx-page-header__actions">
      <a class="nx-btn nx-btn--primary" href="…">Primary action</a>
    </div>
  </header>
  <section class="nx-panel">
    <div class="nx-panel__body">Content</div>
  </section>
</div>
```

## Intentional differences

Marketing/authentication display headings, dashboard metric layouts, wizard
rails, rich-text content, email and generated/print documents are not flattened
into one admin-page layout. Selection chips, tabs and navigation remain distinct
from submit/delete actions. Context buttons retain their contextual color.

The wizard step list is a native `details` disclosure: initially expanded without
JavaScript; collapsed on small screens when enhanced; expanded at the desktop
breakpoint. In-page step swaps reinitialize this behavior. Do not remove the
no-JavaScript navigation or readonly URL parameters.

Legacy page-specific class names remain for script compatibility. Shared styles
are the visual authority for explicitly annotated components. Do not add new
utility-pattern overrides such as “every white rounded box is a card,” or style
bare `.bg-primary` as a button: those also hit progress bars and decorative UI.
Do not duplicate palette hex values in a new editor stylesheet.

## Regression checklist

1. Use semantic component classes in new templates; rebuild utility assets after
   changing markup (`npm run build --prefix frontend`).
2. Run Django/Node suites and frontend lint. `accounts/tests/test_design_system.py`
   guards adoption/rendering; `tests/nexus-wizard-navigation.test.cjs` guards
   responsive wizard initialization.
3. Inspect actual computed styles in a browser, not just template class names.
   Check mobile (390px) and desktop (1440px), including populated/error states.
   In particular, legacy `!important` selectors can defeat an otherwise valid
   new component class.
4. Check keyboard focus, disabled/loading behavior, readable labels, long values,
   empty states, primary action visibility, and page-level horizontal overflow.
5. Restart a `--noreload` Django preview after template edits: cached templates
   can otherwise make a successful browser sweep test outdated markup.

This contract is a compatibility layer, not a claim that every historical local
stylesheet or every legal/document constant has been removed.
