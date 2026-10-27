/* NExUS page-load skeleton controller
   ────────────────────────────────────────────────────────────────────────────
   The server-rendered pages in this system navigate with full document loads,
   so the browser paints nothing between "link clicked" and "response started".
   This script paints a skeleton instead.

   It is deliberately tiny and dependency-free, and it never blocks a
   navigation: the overlay is decoration that is taken away as soon as the
   page it stands in for is up (on DOMContentLoaded, with `load` and the
   bfcache's pageshow as backstops), or by the user, see below.

   Window API (also used by templates that fill a region later):

     NexusSkeleton.show()                     // paint the page skeleton
     NexusSkeleton.show("dashboard")          // paint a specific destination shape
     NexusSkeleton.hide()                     // take it away
     NexusSkeleton.variant(name)              // show another page family's shape
     NexusSkeleton.variantForPath(path)       // layout the destination URL uses
     NexusSkeleton.fill(el, {rows, avatar})   // put list-row shapes in `el`
     NexusSkeleton.region(el, isLoading)      // flip a `.nx-skel-region`
     NexusSkeleton.busy(el, isLoading)        // shimmer a waiting control

   The overlay carries one layout per page family (landing, auth, dashboard,
   wizard, tracker, list, form, record) and the server picks the one that
   matches the *current* route. On the way out, the controller paints the
   *destination* instead: a POST to /login/ shows the dashboard (that is
   where a successful sign-in goes), /logout/ shows the auth screen, and
   any other link or form is resolved from its href/action. A control can
   still override that with `data-nx-skeleton="dashboard"`.

   Once the overlay has been painted *for a navigation*, it belongs to the
   page being left, and the page being left no longer gets to take it away:
   its DOMContentLoaded / load / pageshow say "the page is up", but that page
   is on its way out, and honouring them flashes it back over the skeleton
   (skeleton → old page → new page) whenever the next response is slow. Only
   the next document, an explicit NexusSkeleton.hide(), or the way out below
   takes the overlay down.

   A navigation that never arrives (a cancelled one, a download, a hung
   server) cannot be told apart from a slow one — the browser has no "a
   navigation is in flight" signal — so the wait is held rather than guessed
   at: after ESCAPE_MS the overlay offers a way out ("Taking longer than
   usual — show the page"), which a click or Escape takes. HARD_MS is the
   backstop that gives the page back even if nobody asks.

   Opt outs: add `data-nx-no-skeleton` to a link or form that should not paint
   the page skeleton (downloads, print views, anything that stays on the page).
   ──────────────────────────────────────────────────────────────────────────── */

(function (window, document) {
    "use strict";

    var OVERLAY_ID = "nx-page-skeleton";
    var LEAVING_CLASS = "is-leaving";
    var ESCAPABLE_CLASS = "is-wait-exit";
    var ESCAPE_ID = "nx-skel-escape";
    var FADE_MS = 180;

    // A navigation that never arrives must not leave the overlay stuck over the
    // page — and it must not flash the page being left back either, because a
    // slow response looks exactly the same from here. So the wait is held, and
    // once it is clearly longer than usual the overlay offers a way out
    // instead: this is when that offer appears...
    var ESCAPE_MS = 12000;

    // ...and this is the backstop, for a page nobody is watching any more.
    var HARD_MS = 90000;

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
    var escapeTimer = null;
    var hardTimer = null;
    var showTimer = null;
    var pinned = false;

    // True while the overlay covers the page for a navigation still in flight.
    // The "the page is up" signals of the page being left must not take it
    // down; see the header comment.
    var departing = false;

    // The wait got long enough to offer a way out (see ESCAPE_MS).
    var escapable = false;

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

    function pathnameOf(href) {
        if (href == null || href === "") {
            return window.location.pathname || "/";
        }
        try {
            return new window.URL(href, window.location.href).pathname || "/";
        } catch (e) {
            return window.location.pathname || "/";
        }
    }

    function normalizePath(path) {
        if (!path) return "/";
        return path.length > 1 ? path.replace(/\/+$/, "") : path;
    }

    // Mirror of accounts.context_processors._resolve_skeleton_variant, keyed
    // by path because the click/submit only has a URL, not a Django url name.
    // Destination, not origin: POST /login/ → dashboard; GET /logout/ → auth.
    function variantForPath(path) {
        var p = normalizePath(path);

        if (p === "/logout" || p === "/logout-idle") return "auth";

        if (
            p === "/" || p === "/programs" || p === "/gallery" || p === "/about"
            || p === "/reports" || p === "/achievements" || p === "/proposals"
        ) {
            return "marketing";
        }

        if (p === "/login" || p === "/register" || p === "/debug-login") return "auth";
        if (p.indexOf("/verify/") === 0) return "auth";
        if (p.indexOf("/password") === 0) return "auth";

        if (p === "/dashboard" || p.indexOf("/dashboard/") === 0) return "dashboard";

        if (p === "/profile/edit") return "form";
        if (p === "/profile") return "record";

        if (p === "/accomplishments/create") return "form";
        if (p === "/accomplishments") return "list";
        // The quarterly report request list; /new is a form (see the generic
        // create/edit/new rule below) and /<pk>/toggle is a POST back to it.
        if (p === "/accomplishments/requests") return "list";

        if (p === "/manage-roles") return "record";

        if (p === "/proposals/new" || p === "/proposals/admin/new-legacy") return "wizard";
        if (/\/edit\/step\/\d+$/.test(p)) return "wizard";

        if (/\/moa\/upload$/.test(p) || /\/moa\/\d+$/.test(p)) return "tracker";
        if (/\/(moa|implementation|storage|upload-signed|release-docs|moa-draft)$/.test(p)) {
            return "tracker";
        }

        if (/\/review\/step\/\d+$/.test(p)) return "record";
        if (/\/(comments-summary|comment-summary|view-summary)$/.test(p)) return "record";
        if (/\/version\/\d+\/view$/.test(p)) return "record";

        if (p === "/admin/content") return "record";
        if (/^\/admin\/users\/\d+$/.test(p)) return "record";

        if (p === "/admin/site-control") return "dashboard";
        if (p === "/admin/create-account") return "form";
        // The content change log is a list; the section editors are forms.
        if (p === "/admin/pages/logs") return "list";
        // CMS page editor: /admin/pages/<slug>/ is a form, not the pages list.
        if (/^\/admin\/pages\/[^/]+$/.test(p)) return "form";

        if (/\/(create|edit|new)$/.test(p)) return "form";

        if (p === "/admin" || p.indexOf("/admin/") === 0) return "list";

        return "record";
    }

    function variantForUrl(href, options) {
        options = options || {};
        var path = pathnameOf(href);
        var method = String(options.method || "GET").toUpperCase();
        // These POST to themselves (or to a bounce URL) then redirect. Painting
        // the origin/action path would be the page being left, not the next one.
        if (normalizePath(path) === "/login" && method === "POST") return "dashboard";
        if (normalizePath(path) === "/manage-roles" && method === "POST") return "dashboard";
        if (normalizePath(path) === "/admin/site-control" && method === "POST") return "dashboard";
        return variantForPath(path);
    }

    function nextFieldValue(form) {
        if (!form || !form.elements) return "";
        var field = form.elements.namedItem("next");
        if (!field || field.value == null) return "";
        return String(field.value).trim();
    }

    function explicitHint(node) {
        if (!node || !node.closest) return "";
        var hinted = node.closest("[" + VARIANT_HINT_ATTR + "]");
        return hinted ? (hinted.getAttribute(VARIANT_HINT_ATTR) || "") : "";
    }

    function variantFromLink(link) {
        var hint = explicitHint(link);
        if (hint) return hint;
        return variantForUrl(link.href, { method: "GET" });
    }

    function variantFromForm(form) {
        // `next` is the page the login view will actually send the user to.
        var nextVal = nextFieldValue(form);
        if (nextVal) {
            var fromNext = variantForUrl(nextVal, { method: "GET" });
            if (fromNext) return fromNext;
        }
        var hint = explicitHint(form);
        if (hint) return hint;
        var action = form.getAttribute("action");
        var method = (form.getAttribute("method") || form.method || "GET").toUpperCase();
        return variantForUrl(action || window.location.href, { method: method });
    }

    // The layout the clicked link/form is leading to.
    function destinationHint(event) {
        if (typeof event === "string") return event;
        var target = event && event.target;
        if (!target) return null;
        if (event.type === "submit" && target.nodeName === "FORM") {
            return variantFromForm(target);
        }
        if (target.closest) {
            var link = target.closest("a[href]");
            if (link) return variantFromLink(link);
            var form = target.closest("form");
            if (form) return variantFromForm(form);
        }
        return null;
    }

    function restoreVariant() {
        var el = element();
        if (!el) return;
        var fallback = el.getAttribute(VARIANT_DEFAULT_ATTR);
        if (fallback && el.getAttribute(VARIANT_ATTR) !== fallback) {
            el.setAttribute(VARIANT_ATTR, fallback);
        }
    }

    function show(triggerEvent, precomputedHint) {
        var el = element();
        if (!el) return;
        if (showTimer) return;
        // Read the hint now: by the time the delay elapses the browser may have
        // started unloading and the event target is no longer reachable.
        var hint = precomputedHint;
        if (typeof triggerEvent === "string") {
            hint = triggerEvent;
            triggerEvent = null;
        } else if (hint == null) {
            hint = destinationHint(triggerEvent);
        }
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
            departing = true;
            // The review pin (?nx-skeleton) is held open on purpose, so it gets
            // no timing of its own.
            if (!pinned) armWait();
        }, CLICK_DELAY_MS);
    }

    /* ── The way out of a wait that never ends ─────────────────────────────── */

    function escapeControl() {
        return document.getElementById(ESCAPE_ID);
    }

    // Held, not guessed at: the overlay stays over the page until the next
    // document arrives (or until this page finishes loading). If it is still
    // there long after a page load should have finished, offer the page back —
    // a cancelled navigation, an upload that turned into a download, a server
    // that stopped answering, a render-blocking request that never resolves.
    function armWait() {
        clearWaitTimers();
        escapeTimer = window.setTimeout(function () {
            escapeTimer = null;
            // `hide()` clears this timer, so reaching here means the overlay is
            // still up; the check is for the review pin, which never arms.
            var el = element();
            if (!el || el.hidden) return;
            escapable = true;
            el.classList.add(ESCAPABLE_CLASS);
            var control = escapeControl();
            if (control) control.hidden = false;
        }, ESCAPE_MS);
        hardTimer = window.setTimeout(function () {
            hardTimer = null;
            hide();
        }, HARD_MS);
    }

    function clearWaitTimers() {
        if (escapeTimer) {
            window.clearTimeout(escapeTimer);
            escapeTimer = null;
        }
        if (hardTimer) {
            window.clearTimeout(hardTimer);
            hardTimer = null;
        }
        var el = element();
        if (el) el.classList.remove(ESCAPABLE_CLASS);
        var control = escapeControl();
        if (control) control.hidden = true;
        escapable = false;
    }

    // While the wait is long, the overlay stops being a wall: a deliberate
    // click or Escape means "show me the page, I will wait no longer".
    function onEscapeClick(event) {
        if (!escapable) return;
        event.preventDefault();
        hide();
    }

    function onEscapeKey(event) {
        if (!escapable) return;
        if (event.key !== "Escape" && event.keyCode !== 27) return;
        hide();
    }

    function hide() {
        // Held open for review: the page must not take the screen back.
        if (pinned) return;
        if (showTimer) {
            window.clearTimeout(showTimer);
            showTimer = null;
        }
        clearWaitTimers();
        departing = false;
        if (hideTimer) {
            window.clearTimeout(hideTimer);
            hideTimer = null;
        }
        var el = element();
        document.documentElement.removeAttribute("data-nx-loading");
        // No navigation happened after all (the wait was given up on): go back
        // to this page's own shape for the next attempt.
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
        // In-wizard step changes swap the three-rail body; they are not a page load.
        if (link.closest && link.closest("[data-nx-wizard]")) return true;
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
        show(event, variantFromLink(link));
    }

    function onSubmit(event) {
        if (event.defaultPrevented) return;
        var form = event.target;
        if (!form || form.nodeName !== "FORM") return;
        if (form.hasAttribute("data-nx-no-skeleton")) return;
        if (form.closest && form.closest("[data-nx-wizard]")) return;
        if (form.target && form.target !== "_self") return;
        show(event, variantFromForm(form));
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

    // "The page is up" — but which page? These events fire in the document they
    // belong to, so while the overlay is up for a navigation, they belong to
    // the page being left and must not take it down: that is the flash this
    // controller exists to prevent. A new document starts with `departing`
    // false, and takes its own overlay away on its own DOMContentLoaded.
    function pageIsUp() {
        if (departing) return;
        hide();
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

        // The way out of a wait that got long (see ESCAPE_MS). Both only act
        // once the overlay has offered it.
        document.addEventListener("click", onEscapeClick, true);
        document.addEventListener("keydown", onEscapeKey, true);

        // The document is parsed and every blocking script has run: the real
        // page is on screen, so the skeleton has done its job. (`load` is kept
        // as a backstop for pages that finish later.)
        if (document.readyState === "loading") {
            document.addEventListener("DOMContentLoaded", pageIsUp, { once: true });
        } else {
            pageIsUp();
        }
        window.addEventListener("load", pageIsUp);

        // This page's own load can hang too (a blocked stylesheet, a stalled
        // image). The skeleton is up and nothing has taken it down, so the same
        // way out applies: see armWait().
        var showing = element();
        if (showing && !showing.hidden) armWait();

        // Back/forward cache restores: the page never unloaded, so clear any
        // skeleton the previous navigation painted.
        window.addEventListener("pageshow", pageIsUp);
    }

    window.NexusSkeleton = {
        show: show,
        hide: hide,
        variant: variant,
        variantForPath: variantForPath,
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

