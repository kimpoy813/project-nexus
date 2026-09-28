# NExUS frontend assets

Django serves the actual NExUS pages from `templates/`, `accounts/templates/`, `details/templates/`, and `proposals/templates/`. The React/Vite entry in this folder builds the small Goey Toast module; the stock React `App.jsx` is not a second NExUS web application.

The served Django interface still uses **Tailwind, Alpine, AOS, Chart.js, and SortableJS**. To avoid blank or unusable pages when a third-party CDN is unavailable, these assets are versioned locally:

```bash
npm ci --prefix frontend
npm --prefix frontend run build:django-css
```

The Tailwind source is `static/css/tailwind-input.css`, its scanning/theme config is `frontend/tailwind.config.cjs`, and the generated `static/css/nexus-tailwind.css` is committed because the Python-only deployment build runs without Node. Rebuild and commit this file after adding or changing template utility classes. Colors refer to the CSS custom properties in `static/css/nexus-ui.css`, so administrator-configured brand colors still apply. Third-party distribution files are copied into `static/vendor/`; their versions are pinned in `package-lock.json` and their notices live alongside them. To update a vendor library, update its npm version, recopy its distribution file and license, and verify the corresponding Django screens.

`npm --prefix frontend run build` remains the existing Vite build for the toast module in `static/goey/`. Do not run it merely to update Tailwind CSS; it rewrites the toast bundle.
