/* NExUS native selected-value enhancement
   ────────────────────────────────────────────────────────────────────────────
   Styling the opened picker is CSS-only (css/nexus-select.css). Supporting
   browsers also accept a native <button><selectedcontent></selectedcontent>
   as the select's first child. Adding that slot lets long selected labels
   truncate before the arrow instead of wrapping or pushing it out of view.

   This does NOT create a dropdown, hide the select, or synchronize a copy of
   its value. The browser still owns the control, option list, validation,
   keyboard/mobile interaction and selectedcontent updates. Unsupported
   browsers keep their original native select untouched.
   ──────────────────────────────────────────────────────────────────────────── */
(function (window, document) {
    "use strict";

    var SELECTOR = "select:not([multiple]):not([size]):not(.ck-editor *):not(.flatpickr-monthDropdown-months)";

    function supported() {
        return !!(window.CSS && typeof window.CSS.supports === "function" &&
            window.CSS.supports("appearance", "base-select"));
    }

    function enhance(root) {
        if (!supported() || !root) return;

        var selects = [];
        if (root.nodeType === 1 && typeof root.matches === "function" && root.matches(SELECTOR)) {
            selects.push(root);
        }
        if (typeof root.querySelectorAll === "function") {
            Array.prototype.push.apply(selects, Array.from(root.querySelectorAll(SELECTOR)));
        }

        selects.forEach(function (select) {
            if (!select.isConnected) return;
            // Respect server-rendered native selectedcontent markup as well as
            // cloned controls. Only one native button may lead the select.
            if (select.querySelector(":scope > button")) return;

            var button = document.createElement("button");
            button.type = "button";
            button.className = "nx-select__button";
            button.appendChild(document.createElement("selectedcontent"));
            select.insertBefore(button, select.firstChild);
        });
    }

    function init() {
        if (!supported() || !document.body) return;
        enhance(document);

        // Repeaters, admin builders and in-page wizard swaps add real selects
        // after the initial render. Cascades can also use replaceChildren(),
        // which removes the native button along with stale options, so repair
        // that slot on select child mutations. Values still need no manual
        // synchronization: selectedcontent remains entirely browser-managed.
        if (typeof window.MutationObserver !== "function") return;
        var observer = new window.MutationObserver(function (records) {
            records.forEach(function (record) {
                if (record.target && record.target.nodeType === 1 &&
                    typeof record.target.matches === "function" && record.target.matches(SELECTOR)) {
                    enhance(record.target);
                }
                Array.from(record.addedNodes).forEach(function (node) {
                    if (node.nodeType === 1) enhance(node);
                });
            });
        });
        observer.observe(document.body, { childList: true, subtree: true });
    }

    if (document.body) {
        init();
    } else {
        document.addEventListener("DOMContentLoaded", init, { once: true });
    }
})(window, document);
