/* Tailwind utilities are compiled into css/nexus-tailwind.css using
   frontend/tailwind.config.cjs. Institutional colors are CSS variables in
   css/nexus-ui.css so admin branding can still override them at runtime.
   Keep this file for the phase-share helper used by dashboard gauges. */

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
