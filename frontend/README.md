# NExUS UI assets

Django renders the application. This directory is **not a second application**:
Vite builds the shared React toaster; Tailwind builds utilities used by Django
pages; the vendor script copies pinned browser libraries and fonts for local serving.

## Build

```sh
npm ci
npm run build
npm run lint
```

Commit the generated `static/goey/`, `static/css/nexus-utilities.css`, and
`static/vendor/` with source changes. The Python-only deployment can then run
`collectstatic` without Node or runtime CDNs. For template/class-only changes,
`npm run build:ui` is sufficient.

- `tailwind.config.cjs`: scanned Django templates, form widgets and static JS;
  brand utilities consume runtime CSS variables, including opacity modifiers.
- `src/main.jsx`: shared toaster, mounted by `templates/partials/_toaster.html`.
- `scripts/vendor.mjs`: Alpine, AOS, Chart.js, Sortable and Inter, with licenses.
- `../accounts/ui.py` and `../templates/partials/_theme.html`: validated
  admin-selected brand colors shared by utility and component styles.

Use complete class names rather than building `bg-${color}-500` strings: static
compilation cannot discover arbitrary runtime class fragments. Add an explicit
safelist if a genuine runtime palette requires one. User-authored rich content
should use `nexus-richtext`, not rely on injecting arbitrary utility classes.

`npm run dev` serves only the toaster entry. Use Django's development server to
review real screens. Browser interactions must use Django's named URLs, not
hard-coded API hosts.
