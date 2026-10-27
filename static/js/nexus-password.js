/* NExUS password fields
   ────────────────────────────────────────────────────────────────────────────
   One enhancement, applied to every password input on the page:

   * a **Show / Hide toggle** — a real <button> with aria-pressed, so it works
     from the keyboard and is announced correctly instead of being a decorative
     icon;
   * a **Caps Lock warning** — the most common reason a correct password is
     rejected, and the server cannot tell the user about it;
   * a **live requirements checklist** (`data-nx-password-rules`), so the rules
     are visible while typing instead of only after a failed submit;
   * a **match hint** on the confirmation field (`data-nx-match="<input id>"`).

   This is progressive enhancement: without JavaScript the inputs stay native
   password fields and every form still submits. The server remains the only
   validator; nothing here blocks a submit or changes a value.
   ──────────────────────────────────────────────────────────────────────────── */
(function (window, document) {
    "use strict";

    var ENHANCED = "data-nx-password-ready";

    //: The three rules the server enforces (accounts.forms.validate_nexus_password_rules).
    var RULES = {
        length: { label: "At least 8 characters", test: function (value) { return value.length >= 8; } },
        number: { label: "Contains a number", test: function (value) { return /\d/.test(value); } },
        uppercase: { label: "Contains an uppercase letter", test: function (value) { return /[A-Z]/.test(value); } }
    };
    var RULE_ORDER = ["length", "number", "uppercase"];

    var ICON_SHOW =
        '<svg class="nx-password__icon nx-password__icon--show" viewBox="0 0 20 20" fill="currentColor" aria-hidden="true" focusable="false">' +
        '<path d="M10 12a2 2 0 100-4 2 2 0 000 4z"/>' +
        '<path fill-rule="evenodd" d="M.458 10C1.732 5.943 5.522 3 10 3s8.268 2.943 9.542 7c-1.274 4.057-5.064 7-9.542 7S1.732 14.057.458 10zM14 10a4 4 0 11-8 0 4 4 0 018 0z" clip-rule="evenodd"/>' +
        "</svg>";
    var ICON_HIDE =
        '<svg class="nx-password__icon nx-password__icon--hide" viewBox="0 0 20 20" fill="currentColor" aria-hidden="true" focusable="false">' +
        '<path d="M3.28 2.22a.75.75 0 10-1.06 1.06l14.5 14.5a.75.75 0 101.06-1.06l-1.1-1.1A11.6 11.6 0 0019.54 10C18.27 5.94 14.48 3 10 3c-1.4 0-2.72.28-3.9.78L3.28 2.22zM7.8 8.86l3.34 3.34a2 2 0 01-3.34-3.34z"/>' +
        '<path d="M4.6 5.66A11.9 11.9 0 00.46 10C1.73 14.06 5.52 17 10 17c.86 0 1.68-.1 2.46-.3l-1.6-1.6A4 4 0 015.9 10c0-.2.01-.4.04-.6L4.6 5.66z"/>' +
        "</svg>";

    function attr(element, name) {
        return element.getAttribute ? element.getAttribute(name) : null;
    }

    function elementId(input, suffix) {
        var base = attr(input, "id") || attr(input, "name") || "password";
        return base + "-" + suffix;
    }

    /** Append an id to aria-describedby without dropping the ids already there. */
    function describe(input, id) {
        var described = (attr(input, "aria-describedby") || "").trim();
        if (described.split(/\s+/).indexOf(id) !== -1) return;
        input.setAttribute("aria-describedby", described ? described + " " + id : id);
    }

    function setState(element, state) {
        if (state) element.setAttribute("data-state", state);
        else element.removeAttribute("data-state");
    }

    function show(element, visible) {
        if (visible) element.removeAttribute("hidden");
        else element.setAttribute("hidden", "hidden");
    }

    function isHidden(element) {
        return element.hasAttribute ? element.hasAttribute("hidden") : false;
    }

    /* ---------------------------------------------------------------- reveal */

    function addToggle(input) {
        var wrapper = document.createElement("div");
        wrapper.className = "nx-password";
        input.parentNode.insertBefore(wrapper, input);
        wrapper.appendChild(input);

        var button = document.createElement("button");
        button.setAttribute("type", "button");
        button.className = "nx-password__toggle";
        button.setAttribute("aria-pressed", "false");
        button.setAttribute("aria-label", "Show password");
        button.setAttribute("title", "Show password");
        button.innerHTML = ICON_SHOW + ICON_HIDE;

        function setVisible(visible) {
            input.type = visible ? "text" : "password";
            button.setAttribute("aria-pressed", visible ? "true" : "false");
            // The label describes the action, not the current state: a
            // screen reader user hears what pressing it will do.
            button.setAttribute("aria-label", visible ? "Hide password" : "Show password");
            button.setAttribute("title", visible ? "Hide password" : "Show password");
            wrapper.className = visible ? "nx-password is-revealed" : "nx-password";
        }

        button.addEventListener("click", function (event) {
            if (event && event.preventDefault) event.preventDefault();
            setVisible(input.type === "password");
        });

        wrapper.appendChild(button);

        // Escape returns the field to its hidden state without moving the
        // caret or clearing what was typed — a quick way to un-see a password
        // in front of someone (user control and freedom).
        input.addEventListener("keydown", function (event) {
            if (event && event.key === "Escape" && input.type === "text") {
                setVisible(false);
            }
        });

        return setVisible;
    }

    /* -------------------------------------------------------------- caps lock */

    function addCapsLockHint(input) {
        var hint = document.createElement("p");
        hint.className = "nx-password__hint";
        hint.setAttribute("id", elementId(input, "caps"));
        hint.setAttribute("aria-live", "polite");
        hint.textContent = "Caps Lock is on.";
        hint.setAttribute("data-state", "warning");
        show(hint, false);
        input.parentNode.parentNode.appendChild(hint);

        function update(event) {
            if (!event || typeof event.getModifierState !== "function") return;
            var on = false;
            try {
                on = event.getModifierState("CapsLock");
            } catch (error) {
                on = false;
            }
            show(hint, on);
        }

        input.addEventListener("keydown", update);
        input.addEventListener("keyup", update);
        input.addEventListener("blur", function () { show(hint, false); });
        return hint;
    }

    /* ------------------------------------------------------- requirements list */

    function addRules(input) {
        var requested = (attr(input, "data-nx-password-rules") || "").split(",");
        var keys = requested
            .map(function (key) { return key.trim(); })
            .filter(function (key) { return key && RULES[key]; });
        if (!keys.length) keys = RULE_ORDER.slice();

        var list = document.createElement("ul");
        list.className = "nx-password__rules";
        list.setAttribute("id", elementId(input, "rules"));

        var items = {};
        keys.forEach(function (key) {
            var item = document.createElement("li");
            item.setAttribute("data-rule", key);
            item.setAttribute("data-met", "false");

            var mark = document.createElement("span");
            mark.className = "nx-password__rule-mark";
            mark.setAttribute("aria-hidden", "true");
            mark.textContent = "•";

            var text = document.createElement("span");
            text.className = "nx-password__rule-text";
            text.textContent = RULES[key].label;

            // The icon alone cannot carry the state, so it is also written out
            // for assistive technology.
            var status = document.createElement("span");
            status.className = "nx-password__rule-status sr-only";
            status.textContent = " — not met yet";

            item.appendChild(mark);
            item.appendChild(text);
            item.appendChild(status);
            list.appendChild(item);
            items[key] = { item: item, mark: mark, status: status };
        });

        input.parentNode.parentNode.appendChild(list);
        describe(input, attr(list, "id"));

        function update() {
            var value = input.value || "";
            keys.forEach(function (key) {
                var met = RULES[key].test(value);
                var parts = items[key];
                parts.item.setAttribute("data-met", met ? "true" : "false");
                parts.mark.textContent = met ? "✓" : "•";
                parts.status.textContent = met ? " — met" : " — not met yet";
            });
        }

        input.addEventListener("input", update);
        update();
        return list;
    }

    /* ------------------------------------------------------------- match hint */

    function addMatchHint(input) {
        var targetId = attr(input, "data-nx-match");
        if (!targetId || !document.getElementById) return null;
        var target = document.getElementById(targetId);
        if (!target) return null;

        var hint = document.createElement("p");
        hint.className = "nx-password__hint";
        hint.setAttribute("id", elementId(input, "match"));
        hint.setAttribute("aria-live", "polite");
        show(hint, false);
        input.parentNode.parentNode.appendChild(hint);
        describe(input, attr(hint, "id"));

        function update() {
            var typed = (input.value || "").length > 0;
            if (!typed) {
                show(hint, false);
                return;
            }
            var matches = input.value === (target.value || "");
            hint.textContent = matches ? "Passwords match." : "Passwords do not match yet.";
            setState(hint, matches ? "ok" : "bad");
            show(hint, true);
        }

        input.addEventListener("input", update);
        target.addEventListener("input", update);
        return hint;
    }

    /* --------------------------------------------------------------- enhance */

    function enhance(root) {
        root = root || document;
        var scope = root.querySelectorAll ? root.querySelectorAll("input") : [];
        Array.prototype.forEach.call(scope, function (input) {
            if (!input || input.type !== "password") return;
            if (input.hasAttribute && input.hasAttribute(ENHANCED)) return;
            if (input.hasAttribute && input.hasAttribute("data-no-password-toggle")) return;
            if (!input.parentNode) return;

            input.setAttribute(ENHANCED, "true");
            addToggle(input);
            addCapsLockHint(input);
            if (attr(input, "data-nx-password-rules") !== null) addRules(input);
            addMatchHint(input);
        });
    }

    window.nexusPassword = { enhance: enhance, rules: RULES };

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", function () { enhance(document); });
    } else {
        enhance(document);
    }
})(window, document);
