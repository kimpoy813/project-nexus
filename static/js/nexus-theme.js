/* ==========================================================================
   Phase weights behind the progress gauges, plus the shared gauge lifecycle
   orchestrator across every role dashboard.

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

/* ==========================================================================
   Speedometer gauge animation lifecycle controller.

   Why a shared controller is needed:
   1. When a user prefers Table view (or switches Table <-> Card view), card
      panels start with `[hidden]` (`display: none`). Running the 3-second
      sweep once on DOMContentLoaded burned the entire animation unseen.
   2. On tabbed dashboards (Director), `All Extensions` and `My Proposals`
      start inside `.dashboard-tab-panel.hidden` while `Overview` is shown.
   3. On data-dense dashboards (KPIs + quarterly targets above the fold),
      lower panels finish animating off-screen before the user scrolls down.
   4. On initial page load, `#nx-page-skeleton` fades out over ~180ms; waiting
      briefly for the skeleton to clear keeps the opening 0% -> 100% sweep
      completely visible instead of hidden behind the overlay.
   ========================================================================== */
(function (window, document) {
  'use strict';

  var entries = [];
  var io = null;
  var initialBootScheduled = false;
  var initialBootDone = false;

  function isHidden(el) {
    if (!el || el.isConnected === false) return true;
    if (typeof el.closest === 'function' && el.closest('[hidden], .hidden')) {
      return true;
    }
    if (typeof window.getComputedStyle === 'function') {
      var cur = el;
      while (cur && cur.nodeType === 1) {
        var style = window.getComputedStyle(cur);
        if (style && (style.display === 'none' || style.visibility === 'hidden')) {
          return true;
        }
        cur = cur.parentElement;
      }
    }
    return false;
  }

  function isInViewport(el) {
    if (typeof el.getBoundingClientRect !== 'function') return true;
    var vh = window.innerHeight || (document.documentElement && document.documentElement.clientHeight) || 0;
    var vw = window.innerWidth || (document.documentElement && document.documentElement.clientWidth) || 0;
    if (!vh || !vw) return true;
    var rect = el.getBoundingClientRect();
    // In minimal DOM mocks (zero-sized rects), treat visible elements as in-view.
    if (rect.width === 0 && rect.height === 0 && rect.top === 0 && rect.bottom === 0) {
      return true;
    }
    return rect.bottom > 0 && rect.top < vh && rect.right > 0 && rect.left < vw;
  }

  function stopEntry(entry) {
    if (entry.canvas && entry.canvas._nxGaugeRaf) {
      window.cancelAnimationFrame(entry.canvas._nxGaugeRaf);
      entry.canvas._nxGaugeRaf = null;
    }
    entry.running = false;
  }

  function resetEntry(entry) {
    stopEntry(entry);
    entry.played = false;
    if (typeof entry.drawFn === 'function') {
      entry.drawFn(entry.canvas, 0);
    }
    if (entry.textEl) {
      entry.textEl.textContent = '0%';
    }
  }

  function playEntry(entry) {
    if (!entry || !entry.canvas) return;
    if (isHidden(entry.canvas)) {
      resetEntry(entry);
      return;
    }
    stopEntry(entry);
    prepareCanvas(entry.canvas, 102);
    entry.played = true;
    entry.running = true;
    if (io) {
      io.unobserve(entry.canvas);
    }
    entry.animateFn(entry.canvas, entry.textEl, entry.target);
  }

  function ensureObserver() {
    if (io || typeof window.IntersectionObserver !== 'function') return io;
    io = new window.IntersectionObserver(
      function (records) {
        records.forEach(function (record) {
          if (!record.isIntersecting && record.intersectionRatio <= 0) return;
          var entry = findEntry(record.target);
          if (entry && !entry.played && !isHidden(entry.canvas)) {
            playEntry(entry);
          }
        });
      },
      { threshold: 0.12 }
    );
    return io;
  }

  function findEntry(canvas) {
    for (var i = 0; i < entries.length; i += 1) {
      if (entries[i].canvas === canvas) return entries[i];
    }
    return null;
  }

  function armEntry(entry) {
    if (!entry || !entry.canvas) return;
    if (isHidden(entry.canvas)) {
      if (io) io.unobserve(entry.canvas);
      resetEntry(entry);
      return;
    }
    var observer = ensureObserver();
    if (!observer || isInViewport(entry.canvas)) {
      playEntry(entry);
    } else {
      resetEntry(entry);
      observer.observe(entry.canvas);
    }
  }

  function prepareCanvas(canvas, size) {
    if (!canvas) return;
    var logical = Number(size) || 102;
    var rawDpr = Number(window.devicePixelRatio) || 1;
    var dpr = Math.max(1, Math.min(rawDpr, 2));
    canvas.dataset.logicalWidth = String(logical);
    canvas.dataset.logicalHeight = String(logical);
    canvas.width = Math.round(logical * dpr);
    canvas.height = Math.round(logical * dpr);
    canvas.style.width = logical + 'px';
    canvas.style.height = logical + 'px';
    var ctx = canvas.getContext && canvas.getContext('2d');
    if (ctx && typeof ctx.setTransform === 'function') {
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    }
  }

  function scheduleInitialBoot() {
    if (initialBootScheduled) return;
    initialBootScheduled = true;

    function runBoot() {
      var skeleton = document.getElementById('nx-page-skeleton');
      var skeletonVisible =
        skeleton &&
        !skeleton.hidden &&
        !(skeleton.classList && skeleton.classList.contains('nx-loader-hidden'));
      var delay = skeletonVisible ? 190 : 0;
      window.setTimeout(function () {
        initialBootDone = true;
        entries.forEach(armEntry);
      }, delay);
    }

    if (document.readyState === 'loading') {
      document.addEventListener('DOMContentLoaded', runBoot, { once: true });
    } else {
      window.setTimeout(runBoot, 0);
    }
  }

  function register(canvas, textEl, target, animateFn, drawFn) {
    if (!canvas || typeof animateFn !== 'function') return;
    prepareCanvas(canvas, 102);

    var existing = findEntry(canvas);
    var entry = existing || { canvas: canvas };
    entry.textEl = textEl || null;
    entry.target = Number(target) || 0;
    entry.animateFn = animateFn;
    entry.drawFn = drawFn || null;
    entry.played = false;
    entry.running = false;

    if (!existing) {
      entries.push(entry);
      if (typeof canvas.addEventListener === 'function') {
        canvas.style.cursor = 'pointer';
        canvas.addEventListener('click', function () {
          playEntry(entry);
        });
      }
    }

    resetEntry(entry);

    if (initialBootDone) {
      armEntry(entry);
    } else {
      scheduleInitialBoot();
    }
  }

  function entriesWithin(scope) {
    if (!scope || scope === document) return entries.slice();
    return entries.filter(function (entry) {
      return entry.canvas === scope || (typeof scope.contains === 'function' && scope.contains(entry.canvas));
    });
  }

  function replay(scope) {
    entriesWithin(scope).forEach(function (entry) {
      resetEntry(entry);
      armEntry(entry);
    });
  }

  function onPanelToggle(panel, visible, immediate) {
    if (!panel) return;
    if (!visible) {
      entriesWithin(panel).forEach(function (entry) {
        if (io) io.unobserve(entry.canvas);
        resetEntry(entry);
      });
      return;
    }
    if (immediate || initialBootDone) {
      replay(panel);
    }
  }

  /* Also scroll-reveal `.nx-ring` progress rings below the fold on public pages
     so their fill animation plays when scrolled into view instead of unseen. */
  function initScrollProgressRings() {
    if (typeof window.IntersectionObserver !== 'function' || !document.querySelectorAll) return;
    var rings = Array.prototype.slice.call(document.querySelectorAll('.nx-ring'));
    if (!rings.length) return;

    var ringObserver = new window.IntersectionObserver(
      function (records) {
        records.forEach(function (record) {
          if (!record.isIntersecting) return;
          var ring = record.target;
          ringObserver.unobserve(ring);
          var arc = ring.querySelector('.nx-ring__value');
          if (!arc) return;
          arc.style.animation = 'none';
          if (typeof arc.getBoundingClientRect === 'function') {
            void arc.getBoundingClientRect();
          }
          arc.style.animation = '';
        });
      },
      { threshold: 0.15 }
    );

    rings.forEach(function (ring) {
      if (!isInViewport(ring)) {
        var arc = ring.querySelector('.nx-ring__value');
        if (arc) arc.style.animation = 'none';
        ringObserver.observe(ring);
      }
    });
  }

  if (typeof window.addEventListener === 'function') {
    window.addEventListener('pageshow', function (event) {
      if (event && event.persisted) {
        replay(document);
      }
    });
  }

  if (typeof document.addEventListener === 'function') {
    document.addEventListener('DOMContentLoaded', initScrollProgressRings);
  }

  window.nexusGauge = {
    prepareCanvas: prepareCanvas,
    register: register,
    replay: replay,
    onPanelToggle: onPanelToggle,
  };
})(window, document);
