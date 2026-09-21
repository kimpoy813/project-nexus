/* NExUS page-load skeleton controller
   ────────────────────────────────────────────────────────────────────────────
   The server-rendered pages in this system navigate with full document loads,
   so the browser paints nothing between "link clicked" and "response started".
   This script paints a skeleton instead.

   It is deliberately tiny and dependency-free, and it never blocks a
   navigation: the overlay is decoration that is taken away again on load,
   after a timeout, and whenever the page is restored from the bfcache.

   Window API (also used by templates that fill a region later):

     NexusSkeleton.show()                     // paint the page skeleton
     NexusSkeleton.hide()                     // take it away
     NexusSkeleton.variant(name)              // show another page family's shape
     NexusSkeleton.fill(el, {rows, avatar})   // put list-row shapes in `el`
     NexusSkeleton.region(el, isLoading)      // flip a `.nx-skel-region`
     NexusSkeleton.busy(el, isLoading)        // shimmer a waiting control

   The overlay carries one layout per page family (landing, auth, dashboard,
   wizard, tracker, list, form, record) and the server picks the one that
   matches the current route. A link or form that leads somewhere of a
   *different* shape can say so with `data-nx-skeleton="dashboard"`, and the
   controller switches before it paints — so leaving the landing page for a
   dashboard shows the dashboard's rail, not the hero it came from.

   Opt outs: add `data-nx-no-skeleton` to a link or form that should not paint
   the page skeleton (downloads, print views, anything that stays on the page).
   ──────────────────────────────────────────────────────────────────────────── */

(function (window, document) {
    "use strict";

    var OVERLAY_ID = "nx-page-skeleton";
    var LEAVING_CLASS = "is-leaving";
    var FADE_MS = 180;

    // A navigation that never completes (server hang, cancelled download)
    // must not leave the overlay stuck over the page.
    var STUCK_MS = 12000;

    // Clicks wait this long before painting: a local page that answers in a
    // few milliseconds should not flash a skeleton at the user.
    var CLICK_DELAY_MS = 120;

    // Which page-family layout the overlay paints, and the one this page
    // belongs to (restored after a navigation that never happened).
    var VARIANT_ATTR = "data-nx-variant";
    var VARIANT_DEFAULT_ATTR = "data-nx-variant-default";
    var VARIANT_HINT_ATTR = "data-nx-skeleton";

    // Review affordance: `?nx-skeleton` holds the overlay on screen instead of
    // letting the page take over, so a layout can actually be looked at. Give
    // it a value (`?nx-skeleton=wizard`) to force a particular one.
    var PIN_PARAM = "nx-skeleton";

    var overlay = null;
    var hideTimer = null;
    var stuckTimer = null;
    var showTimer = null;
    var pinned = false;

    function prefersReducedMotion() {
        return window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    }

    function element() {
        if (!overlay) overlay = document.getElementById(OVERLAY_ID);
        return overlay;
    }

    /* ── Layout variants ─────────────────────────────────────────────────── */

    // Is this a layout the overlay actually ships? Checked against the markup
    // rather than a hard-coded list, so the two can never drift apart.
    function hasLayout(el, name) {
        if (!el || !name) return false;
        return !!el.querySelector(".nx-skel-l--" + name);
    }

    function variant(name) {
        var el = element();
        if (!hasLayout(el, name)) return;
        el.setAttribute(VARIANT_ATTR, name);
    }

    // The layout the clicked link/form is leading to, if it says.
    function variantHint(event) {
        var target = event && event.target;
        var hint = target && target.closest ? target.closest("[" + VARIANT_HINT_ATTR + "]") : null;
        return hint ? hint.getAttribute(VARIANT_HINT_ATTR) : null;
    }

    function restoreVariant() {
        var el = element();
        if (!el) return;
        var fallback = el.getAttribute(VARIANT_DEFAULT_ATTR);
        if (fallback && el.getAttribute(VARIANT_ATTR) !== fallback) {
            el.setAttribute(VARIANT_ATTR, fallback);
        }
    }

    function show(triggerEvent) {
        var el = element();
        if (!el) return;
        if (showTimer) return;
        // Read the hint now: by the time the delay elapses the browser may have
        // started unloading and the event target is no longer reachable.
        var hint = variantHint(triggerEvent);
        showTimer = window.setTimeout(function () {
            showTimer = null;
            // A handler called preventDefault() while we waited: the click was
            // an in-page action (modal, AJAX form), not a navigation, so there
            // is nothing to cover.
            if (triggerEvent && triggerEvent.defaultPrevented) return;
            // A fade-out may still be pending from the page we just landed on
            // (click during the first ~200ms): cancel it, or it would hide the
            // skeleton again while the next page is loading.
            if (hideTimer) {
                window.clearTimeout(hideTimer);
                hideTimer = null;
            }
            variant(hint);
            el.hidden = false;
            el.classList.remove(LEAVING_CLASS);
            document.documentElement.setAttribute("data-nx-loading", "true");
            if (stuckTimer) window.clearTimeout(stuckTimer);
            stuckTimer = window.setTimeout(hide, STUCK_MS);
        }, CLICK_DELAY_MS);
    }

    function hide() {
        // Held open for review: the page must not take the screen back.
        if (pinned) return;
        if (showTimer) {
            window.clearTimeout(showTimer);
            showTimer = null;
        }
        if (stuckTimer) {
            window.clearTimeout(stuckTimer);
            stuckTimer = null;
        }
        if (hideTimer) {
            window.clearTimeout(hideTimer);
            hideTimer = null;
        }
        var el = element();
        document.documentElement.removeAttribute("data-nx-loading");
        // The navigation never happened (cancelled, or the stuck timer fired):
        // go back to this page's own shape for the next attempt.
        restoreVariant();
        if (!el) return;

        if (prefersReducedMotion()) {
            el.hidden = true;
            el.classList.remove(LEAVING_CLASS);
            return;
        }
        el.classList.add(LEAVING_CLASS);
        hideTimer = window.setTimeout(function () {
            hideTimer = null;
            el.hidden = true;
            el.classList.remove(LEAVING_CLASS);
        }, FADE_MS);
    }

    /* ── Content skeletons ─────────────────────────────────────────────────── */

    // List-row placeholders (avatar + two lines), the shape of a search result.
    function fill(el, options) {
        if (!el) return;
        options = options || {};
        var rows = typeof options.rows === "number" ? options.rows : 3;
        var avatar = options.avatar !== false;
        var html = "";
        for (var i = 0; i < rows; i++) {
            html += '<div class="nx-skel-row" aria-hidden="true">' +
                (avatar ? '<div class="nx-skel nx-skel--avatar"></div>' : "") +
                '<div class="nx-skel-lines">' +
                '<div class="nx-skel nx-skel--text nx-skel--w-40"></div>' +
                '<div class="nx-skel nx-skel--text-sm nx-skel--w-70"></div>' +
                "</div></div>";
        }
        el.innerHTML = html;
    }

    // Flip a region between its skeleton and its real content.
    function region(el, isLoading) {
        if (!el) return;
        var loading = isLoading !== false;
        el.setAttribute("data-loading", loading ? "true" : "false");
        el.setAttribute("aria-busy", loading ? "true" : "false");
    }

    // A control that is waiting on the server (a select whose options are
    // still loading) gets the shimmer and stops taking input.
    function busy(el, isLoading) {
        if (!el) return;
        var loading = isLoading !== false;
        el.classList.toggle("is-nx-loading", loading);
        if ("disabled" in el) el.disabled = loading;
        el.setAttribute("aria-busy", loading ? "true" : "false");
    }

    /* ── Navigation hooks ──────────────────────────────────────────────────── */

    function isPlainLeftClick(event) {
        return event.button === 0 && !event.metaKey && !event.ctrlKey &&
            !event.shiftKey && !event.altKey;
    }

    function shouldSkipLink(link) {
        if (link.hasAttribute("data-nx-no-skeleton")) return true;
        if (link.hasAttribute("download")) return true;
        if (link.target && link.target !== "_self") return true;

        var href = link.getAttribute("href") || "";
        if (!href || href.charAt(0) === "#") return true;
        if (/^(mailto:|tel:|javascript:|blob:|data:)/i.test(href)) return true;

        var url;
        try {
            url = new window.URL(link.href, window.location.href);
        } catch (e) {
            return true;
        }
        if (url.origin !== window.location.origin) return true;

        // Same document, only a different hash: the browser does not reload.
        var samePage = url.pathname === window.location.pathname &&
            url.search === window.location.search;
        if (samePage) return true;

        return false;
    }

    function onClick(event) {
        if (event.defaultPrevented || !isPlainLeftClick(event)) return;
        var link = event.target && event.target.closest ? event.target.closest("a[href]") : null;
        if (!link || shouldSkipLink(link)) return;
        show(event);
    }

    function onSubmit(event) {
        if (event.defaultPrevented) return;
        var form = event.target;
        if (!form || form.nodeName !== "FORM") return;
        if (form.hasAttribute("data-nx-no-skeleton")) return;
        if (form.target && form.target !== "_self") return;
        show(event);
    }

    // The layout held open by `?nx-skeleton[=<layout>]`, or null.
    function pinRequest() {
        try {
            var params = new window.URLSearchParams(window.location.search);
            return params.has(PIN_PARAM) ? params.get(PIN_PARAM) || null : undefined;
        } catch (e) {
            return undefined;
        }
    }

    function start() {
        var pin = pinRequest();
        if (pin !== undefined) {
            // Held open for review, so the navigation hooks and the "the page
            // is up, take it away" listeners are not wired at all.
            pinned = true;
            variant(pin);
            show();
            return;
        }

        document.addEventListener("click", onClick, true);
        document.addEventListener("submit", onSubmit, true);

        // The document is parsed and every blocking script has run: the real
        // page is on screen, so the skeleton has done its job. (`load` is kept
        // as a backstop for pages that finish later.)
        if (document.readyState === "loading") {
            document.addEventListener("DOMContentLoaded", hide, { once: true });
        } else {
            hide();
        }
        window.addEventListener("load", hide);

        // Back/forward cache restores: the page never unloaded, so clear any
        // skeleton the previous navigation painted.
        window.addEventListener("pageshow", hide);
    }

    window.NexusSkeleton = {
        show: show,
        hide: hide,
        variant: variant,
        fill: fill,
        region: region,
        busy: busy
    };

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", start, { once: true });
    } else {
        start();
    }
})(window, document);
