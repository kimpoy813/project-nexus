/* ==========================================================================
   NExUS — Single source of truth for the institutional design system.

   Loaded on EVERY page that uses the Tailwind CDN, immediately after the
   CDN script, so all HTML files (base template, maintenance, debug login,
   standalone pages) share the exact same brand tokens:

     • Logo-derived palette (ISPSC-RDEI Extension Office emblem):
         forest green  #103b07   maroon  #5a1113
         gold          #e8c31e   cream   #f5e587
     • One typeface everywhere: Inter (weights 400–900).

   Keep this file in sync with the CSS custom properties in
   static/css/nexus-ui.css (:root block).
   ========================================================================== */
(function () {
  var NEXUS_THEME = {
    theme: {
      extend: {
        colors: {
          /* Institutional brand — sampled from the Extension Office logo */
          primary: '#103b07',   /* forest green  (logo gear greens)   */
          secondary: '#5a1113', /* maroon        (logo gear / hands)  */
          tertiary: '#e8c31e',  /* gold          (logo rim outline)   */
          accent: '#f5e587',    /* cream yellow  (logo inner quadrants) */
          gold: '#e8c31e',      /* vivid gold    (logo rim outline)   */
          cream: '#fdf9e3',     /* soft paper tint of the accent      */
          maroon: '#5a1113',    /* alias of secondary for clarity     */
          forest: '#103b07',    /* alias of primary for clarity       */
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

/* ==========================================================================
   Phase weights behind the progress gauges.

   base.html emits the admin-editable WorkflowPhase split as JSON in
   #nexus-phase-shares (the same numbers drawn as rings on the public Services
   page). The dashboard doughnut gauges colour-band their arcs with it, so the
   zone boundaries always agree with Proposal.overall_progress.

   Exposed as a function rather than a constant: this file loads in <head>,
   before the JSON node is parsed, and the weights may be re-read after an
   administrator edits them.
   ========================================================================== */
window.nexusPhaseShares = function () {
  var FALLBACK = { proposal: 0.5, moa: 0.2, implementation: 0.3 };

  try {
    var node = document.getElementById('nexus-phase-shares');
    var data = node ? JSON.parse(node.textContent) : null;

    if (!data || typeof data !== 'object') {
      return FALLBACK;
    }

    return {
      proposal: Number(data.proposal) || 0,
      moa: Number(data.moa) || 0,
      implementation: Number(data.implementation) || 0,
    };
  } catch (error) {
    return FALLBACK;
  }
};
