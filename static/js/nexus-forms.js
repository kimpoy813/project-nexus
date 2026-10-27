/* NExUS form feedback
   ────────────────────────────────────────────────────────────────────────────
   Two small pieces of feedback that every form needs and none should repeat:

   * **An error summary takes focus when validation fails** (`data-nx-error-summary`).
     A sighted user sees the red box at the top of the page; a keyboard or screen
     reader user would otherwise be left at the bottom, next to the button they
     just pressed, with no idea what went wrong. Focusing the summary announces
     the problem and puts them at the start of the form.

   * **A destructive action asks first** (`data-nx-confirm` on the form or the
     link). One attribute, so the wording lives in the template instead of in a
     JavaScript string, and every delete in the system asks the same way. The
     confirmation is in the capture phase, before the busy state is applied, so
     cancelling leaves the button exactly as it was.

   * **A submitted form says it is working** (`data-nx-busy` on the form). The
     button is disabled and relabelled from `data-nx-busy-label`, so a slow save
     cannot be double-submitted and the user is not left wondering whether the
     click registered. If the page somehow stays put for 20 seconds the button is
     restored, so a dropped connection never leaves a dead form.

   Nothing here validates anything: the server is still the source of truth.
   ──────────────────────────────────────────────────────────────────────────── */
(function (window, document) {
    "use strict";

    var RESTORE_AFTER_MS = 20000;

    /* --------------------------------------------------------- error summary */

    function focusErrorSummary(root) {
        var summary = root.querySelector ? root.querySelector("[data-nx-error-summary]") : null;
        if (!summary) return null;
        if (summary.hasAttribute && summary.hasAttribute("hidden")) return null;
        if (!summary.hasAttribute("tabindex")) summary.setAttribute("tabindex", "-1");
        if (typeof summary.focus === "function") summary.focus();
        return summary;
    }

    /* ---------------------------------------------------------- busy submits */

    function busyLabel(button) {
        return (button && button.getAttribute && button.getAttribute("data-nx-busy-label")) || "Please wait…";
    }

    function enhanceForm(form) {
        if (!form || (form.hasAttribute && form.hasAttribute("data-nx-busy-ready"))) return;
        if (form.setAttribute) form.setAttribute("data-nx-busy-ready", "true");

        form.addEventListener("submit", function (event) {
            // A form that is already submitting must not be submitted twice.
            if (form.getAttribute && form.getAttribute("aria-busy") === "true") {
                if (event && event.preventDefault) event.preventDefault();
                return;
            }
            if (form.setAttribute) form.setAttribute("aria-busy", "true");

            var submitter = (event && event.submitter) || null;
            var buttons = form.querySelectorAll ? form.querySelectorAll('button[type="submit"], input[type="submit"]') : [];
            var primary = submitter || buttons[0] || null;

            Array.prototype.forEach.call(buttons, function (button) {
                if (button === primary) {
                    if (button.tagName && button.tagName.toLowerCase() === "input") {
                        button.value = busyLabel(button);
                    } else {
                        if (button.getAttribute && !button.getAttribute("data-nx-busy-original")) {
                            button.setAttribute("data-nx-busy-original", button.textContent || "");
                        }
                        button.textContent = busyLabel(button);
                    }
                }
                button.className = (button.className || "") + " is-busy";
                if (button.setAttribute) button.setAttribute("aria-disabled", "true");
            });

            // Disabling *inside* the submit handler would drop the button's own
            // name/value from the request (several forms submit `action` that
            // way), so the controls are disabled once the data set is built.
            window.setTimeout(function () {
                Array.prototype.forEach.call(buttons, function (button) { button.disabled = true; });
            }, 0);

            window.setTimeout(function () {
                // Still here: the request never completed. Give the button back
                // rather than leaving the user stuck with a form they cannot send.
                if (!form.isConnected) return;
                if (form.getAttribute && form.getAttribute("aria-busy") === "true") {
                    form.removeAttribute("aria-busy");
                    Array.prototype.forEach.call(buttons, function (button) {
                        button.disabled = false;
                        button.className = (button.className || "").replace(/\s*is-busy/g, "");
                        if (button.removeAttribute) button.removeAttribute("aria-disabled");
                    });
                    if (primary && primary.getAttribute) {
                        var original = primary.getAttribute("data-nx-busy-original");
                        if (original !== null) primary.textContent = original;
                    }
                }
            }, RESTORE_AFTER_MS);
        });
    }

    /* ------------------------------------------------------------ confirmations */

    function confirmMessage(element) {
        var message = element && element.getAttribute ? element.getAttribute("data-nx-confirm") : "";
        message = (message || "").trim();
        return message || "Are you sure? This cannot be undone.";
    }

    function askConfirmation(element) {
        // ``window.confirm`` is used on purpose: it is modal, keyboard
        // accessible, announced by screen readers, and blocks long enough that a
        // second click cannot slip through. The message is the only thing the
        // page has to supply.
        if (typeof window.confirm !== "function") return true;
        return window.confirm(confirmMessage(element));
    }

    function guardSubmit(form) {
        if (!form || !form.addEventListener) return;
        if (form.getAttribute && form.getAttribute("data-nx-confirm-ready")) return;
        if (form.setAttribute) form.setAttribute("data-nx-confirm-ready", "true");

        // Capture phase: cancelling here stops the busy handler from ever
        // running, so the button still reads "Delete" after a change of heart.
        form.addEventListener("submit", function (event) {
            if (askConfirmation(form)) return;
            if (event && event.preventDefault) event.preventDefault();
            if (event && event.stopImmediatePropagation) event.stopImmediatePropagation();
        }, true);
    }

    // Links, and buttons that submit a form they do not sit inside (`form=` attr),
    // ask on click; a form that carries the attribute is guarded on submit instead.
    function guardControl(control) {
        if (!control || !control.addEventListener) return;
        if (control.getAttribute && control.getAttribute("data-nx-confirm-ready")) return;
        if (control.setAttribute) control.setAttribute("data-nx-confirm-ready", "true");

        control.addEventListener("click", function (event) {
            if (askConfirmation(control)) return;
            if (event && event.preventDefault) event.preventDefault();
            if (event && event.stopImmediatePropagation) event.stopImmediatePropagation();
        });
    }

    /* --------------------------------------------------------------- enhance */

    function enhance(root) {
        root = root || document;

        var summary = focusErrorSummary(root);
        var forms = root.querySelectorAll ? root.querySelectorAll("form") : [];
        Array.prototype.forEach.call(forms, function (form) {
            if (form.getAttribute && form.getAttribute("data-nx-confirm") !== null) guardSubmit(form);
            if (form.getAttribute && form.getAttribute("data-nx-busy") !== null) enhanceForm(form);
        });

        var controls = root.querySelectorAll
            ? root.querySelectorAll("a[data-nx-confirm], button[data-nx-confirm], input[data-nx-confirm]")
            : [];
        Array.prototype.forEach.call(controls, guardControl);

        return summary;
    }

    window.nexusForms = {
        enhance: enhance,
        focusErrorSummary: focusErrorSummary,
        confirmMessage: confirmMessage,
    };

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", function () { enhance(document); });
    } else {
        enhance(document);
    }
})(window, document);
