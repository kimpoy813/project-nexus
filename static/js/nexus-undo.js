/* NExUS undo countdown
   ────────────────────────────────────────────────────────────────────────────
   The undo bar is server-rendered (`templates/partials/_undo.html`): without
   JavaScript it works, it just has no countdown — the record is still restorable
   until the session drops the snapshot.

   With JavaScript it says how long is left, in seconds, and removes itself at
   zero so nobody clicks "Undo" on something that has already expired. The
   deadline is taken from the server's own remaining time (`data-nx-undo-seconds`),
   so a slow page load cannot make the bar outlive the snapshot.

   Nothing here sends a request: undoing is a normal form POST, which keeps the
   action out of reach of a prefetcher or a link scanner.
   ──────────────────────────────────────────────────────────────────────────── */
(function (window, document) {
    "use strict";

    var TICK_MS = 1000;

    function expiryFor(item) {
        var seconds = parseInt(item.getAttribute("data-nx-undo-seconds"), 10);
        if (isNaN(seconds) || seconds < 0) return null;
        return Date.now() + seconds * 1000;
    }

    function label(item, seconds) {
        var remaining = item.querySelector("[data-nx-undo-remaining]");
        if (!remaining) return;
        remaining.textContent = String(Math.max(0, seconds));
    }

    function expire(item) {
        // Removing the row (rather than hiding it) also removes its forms, so a
        // stale undo cannot be submitted from the keyboard.
        if (item.parentNode) item.parentNode.removeChild(item);
    }

    function start(item) {
        var expiresAt = expiryFor(item);
        if (expiresAt === null) return;

        var update = function () {
            var left = Math.ceil((expiresAt - Date.now()) / 1000);
            if (left <= 0) {
                window.clearInterval(timer);
                expire(item);
                return;
            }
            label(item, left);
        };

        var timer = window.setInterval(update, TICK_MS);
        update();
    }

    function enhance(root) {
        root = root || document;
        if (!root.querySelectorAll) return;

        // Escape closes the newest bar, matching every other dismissible
        // surface on the page. It does not undo anything.
        root.addEventListener("keydown", function (event) {
            if (!event || event.key !== "Escape") return;
            var items = root.querySelectorAll("[data-nx-undo]");
            if (!items.length) return;
            expire(items[items.length - 1]);
        });

        Array.prototype.forEach.call(root.querySelectorAll("[data-nx-undo]"), start);
    }

    window.nexusUndo = { enhance: enhance };

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", function () { enhance(document); });
    } else {
        enhance(document);
    }
})(window, document);
