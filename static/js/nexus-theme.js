/* ==========================================================================
   NExUS — Single source of truth for the institutional design system.

   Loaded on EVERY page that uses the Tailwind CDN, immediately after the
   CDN script, so all HTML files (base template, maintenance, debug login,
   standalone pages) share the exact same brand tokens:

     • Institutional palette:
         deep gold     #a16207   vivid gold  #ca8a04
         gold          #e8c31e   cream       #f5e587
         maroon        #5a1113
     • One typeface everywhere: Inter (weights 400–900).

   Keep this file in sync with the CSS custom properties in
   static/css/nexus-ui.css (:root block).
   ========================================================================== */
(function () {
  var NEXUS_THEME = {
    theme: {
      extend: {
        colors: {
          /* Institutional brand — golden yellow primary */
          primary: '#a16207',   /* deep gold     (headings, fills, focus) */
          secondary: '#5a1113', /* maroon        (accent / MOA stage)     */
          accent: '#f5e587',    /* cream yellow  (soft highlights)        */
          gold: '#e8c31e',      /* vivid gold    (rim / emphasis)         */
          cream: '#fdf9e3',     /* soft paper tint of the accent          */
          maroon: '#5a1113',    /* alias of secondary for clarity         */
          forest: '#a16207',    /* legacy alias of primary for clarity    */
        },
        fontFamily: {
          /* ONE typeface for ALL text — headings, body, buttons, tables,
             forms, badges. sans/serif/mono are aliased to the same family
             so no markup can accidentally drift to a different font. */
          sans: ['Inter', 'ui-sans-serif', 'system-ui', '-apple-system', 'Segoe UI', 'Helvetica Neue', 'Arial', 'sans-serif'],
          serif: ['Inter', 'ui-sans-serif', 'system-ui', '-apple-system', 'Segoe UI', 'Helvetica Neue', 'Arial', 'sans-serif'],
          mono: ['Inter', 'ui-sans-serif', 'system-ui', '-apple-system', 'Segoe UI', 'Helvetica Neue', 'Arial', 'sans-serif'],
        },
        boxShadow: {
          nexus: '0 16px 40px rgba(15, 23, 42, 0.08)',
        },
      },
    },
  };

  /* Works whether the Tailwind CDN has already booted or boots after us. */
  window.tailwind = window.tailwind || {};
  window.tailwind.config = NEXUS_THEME;
})();
