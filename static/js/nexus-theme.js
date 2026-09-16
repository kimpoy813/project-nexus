/* ==========================================================================
   NExUS — Single source of truth for the Tailwind theme.

   Loaded on EVERY page that uses the Tailwind CDN, immediately after the
   CDN script, so all HTML files (base template, maintenance, standalone
   pages) share the same tokens.

   Design language (2026 refresh): Vercel-style restraint.
     • Monochrome first. The old institutional palette (forest green,
       maroon, gold, cream) is mapped onto a neutral foreground scale so
       existing utility classes render calm instead of branded. Color is
       reserved for state (success / warning / danger / info).
     • One typeface for prose and controls: Geist. One for code and short
       operational identifiers: Geist Mono. Both are loaded in base.html
       and come with system fallbacks.
     • Pairs with static/css/vercel-brand.css (the vbg foundation) and the
       token layer in static/css/nexus-ui.css.
   ========================================================================== */
(function () {
  var GEIST_SANS = ['Geist', '-apple-system', 'BlinkMacSystemFont', 'Segoe UI', 'Helvetica Neue', 'Arial', 'sans-serif'];
  var GEIST_MONO = ['Geist Mono', 'SFMono-Regular', 'Consolas', 'monospace'];

  var NEXUS_THEME = {
    theme: {
      extend: {
        colors: {
          /* Monochrome brand scale. `primary` is the Vercel foreground:
             near-black in light contexts, used for headings, key actions,
             and emphasis. It intentionally does not invert per theme;
             the dark adaptation layer in nexus-ui.css handles contrast. */
          primary: '#0a0a0a',
          secondary: '#262626',
          accent: '#e4e4e7',   /* quiet neutral where the cream used to sit */
          gold: '#d4d4d8',     /* muted neutral where the gold used to sit  */
          cream: '#fafafa',
          maroon: '#404040',
          forest: '#0a0a0a'
        },
        fontFamily: {
          sans: GEIST_SANS,
          serif: GEIST_SANS,
          mono: GEIST_MONO
        },
        boxShadow: {
          /* One restrained elevation; no ornamental depth. */
          nexus: '0 1px 2px 0 rgb(0 0 0 / 0.05)'
        }
      }
    }
  };

  /* Works whether the Tailwind CDN has already booted or boots after us. */
  window.tailwind = window.tailwind || {};
  window.tailwind.config = NEXUS_THEME;
})();
