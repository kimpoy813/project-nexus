/* ==========================================================================
   NExUS — Tailwind CDN tokens. Loaded immediately after the Tailwind CDN
   script so every page shares the same brand tokens (palette + one font).
   Keep in sync with static/css/nexus.css (:root).
   ========================================================================== */
(function () {
  window.tailwind = window.tailwind || {};
  window.tailwind.config = {
    theme: {
      extend: {
        colors: {
          primary: '#103b07',   /* forest green  */
          secondary: '#5a1113', /* maroon        */
          accent: '#f5e587',    /* cream yellow  */
          gold: '#e8c31e',      /* vivid gold    */
        },
        fontFamily: {
          sans: ['Inter', 'ui-sans-serif', 'system-ui', '-apple-system', 'Segoe UI', 'Arial', 'sans-serif'],
        },
      },
    },
  };
})();
