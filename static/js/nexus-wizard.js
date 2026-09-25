/* NExUS proposal wizard in-page navigator
   ────────────────────────────────────────────────────────────────────────────
   The wizard is still server-rendered, one step per URL. Without this script
   every "Save & Next", Back, Skip, Add member, and stepper click would unload
   the whole page (navbar, overlay, footer) and paint it again.

   This intercepts those navigations *inside* `#nx-wizard-root` and swaps only
   the three-rail wizard. Leaving the wizard (submit, dashboard, a download)
   is a real navigation. Without JavaScript the forms and links still work.
   ──────────────────────────────────────────────────────────────────────────── */

(function (window, document) {
    "use strict";

    var ROOT_ID = "nx-wizard-root";
    var WIZARD_PATH = /\/proposals\/[0-9a-f-]+\/edit\/step\/\d+\/?$/i;
    var PING_MS = 20000;
    var pingTimer = null;
    var inflight = null;
    var busy = false;

    function rootEl() {
        return document.getElementById(ROOT_ID);
    }

    function toUrl(href) {
        try {
            return new window.URL(href, window.location.href);
        } catch (e) {
            return null;
        }
    }

    function isWizardUrl(href) {
        var url = toUrl(href);
        return !!(url && url.origin === window.location.origin && WIZARD_PATH.test(url.pathname));
    }

    function sameLocation(href) {
        var url = toUrl(href);
        if (!url) return false;
        return url.pathname === window.location.pathname && url.search === window.location.search;
    }

    function isPlainLeftClick(event) {
        return event.button === 0 && !event.metaKey && !event.ctrlKey &&
            !event.shiftKey && !event.altKey;
    }

    function getCookie(name) {
        var value = "; " + document.cookie;
        var parts = value.split("; " + name + "=");
        if (parts.length === 2) return parts.pop().split(";").shift();
        return "";
    }

    function setLoading(on) {
        var root = rootEl();
        if (!root) return;
        root.classList.toggle("is-nx-wizard-loading", !!on);
        root.setAttribute("aria-busy", on ? "true" : "false");
    }

    function cleanupOrphanDropdowns() {
        // Custom <select> skins are appended to <body>, so they survive a
        // wizard swap unless we drop them. The next enhance pass rebuilds.
        Array.prototype.slice.call(document.querySelectorAll("body > div")).forEach(function (el) {
            var cls = el.className || "";
            if (String(cls).indexOf("z-[9999]") !== -1) el.remove();
        });
    }

    function activateScripts(root) {
        // DOMParser marks <script> as non-executable. Re-insert so step chips,
        // repeaters, and search boxes bind on the new markup.
        Array.prototype.slice.call(root.querySelectorAll("script")).forEach(function (old) {
            var neu = document.createElement("script");
            Array.prototype.slice.call(old.attributes).forEach(function (attr) {
                neu.setAttribute(attr.name, attr.value);
            });
            neu.textContent = old.textContent;
            old.parentNode.replaceChild(neu, old);
        });
    }

    function showToastsFrom(doc) {
        var data = doc.getElementById("messages-data");
        var container = document.getElementById("toast-container");
        var toaster = window.goeyToast;
        if (!data || (!container && !toaster)) return;

        Array.prototype.slice.call(data.querySelectorAll("[data-message]")).forEach(function (msgElement, index) {
            var message = msgElement.getAttribute("data-message") || "";
            var tags = msgElement.getAttribute("data-tags") || "info";
            var toastType = tags.indexOf("success") !== -1 ? "success"
                : tags.indexOf("error") !== -1 ? "error"
                : tags.indexOf("warning") !== -1 ? "warning"
                : "info";
            if (toaster && typeof toaster[toastType] === "function") {
                toaster[toastType](message);
                return;
            }
            if (!container) return;
            var bgColor = "bg-gray-900";
            if (tags.indexOf("success") !== -1) bgColor = "bg-green-700";
            else if (tags.indexOf("error") !== -1) bgColor = "bg-red-700";
            else if (tags.indexOf("warning") !== -1) bgColor = "bg-yellow-600";
            else if (tags.indexOf("info") !== -1) bgColor = "bg-blue-700";

            var toast = document.createElement("div");
            toast.className = bgColor + " text-white px-5 py-4 rounded-2xl shadow-xl max-w-sm w-full transform transition-all duration-500 opacity-0 translate-x-5";
            toast.setAttribute("role", "alert");

            var row = document.createElement("div");
            row.className = "flex items-start justify-between gap-3";

            var text = document.createElement("span");
            text.className = "flex-1 text-sm font-medium leading-5";
            text.textContent = message;

            var close = document.createElement("button");
            close.type = "button";
            close.className = "text-xl leading-none opacity-80 hover:opacity-100";
            close.setAttribute("aria-label", "Dismiss notification");
            close.textContent = "×";
            close.addEventListener("click", function () { toast.remove(); });

            row.appendChild(text);
            row.appendChild(close);
            toast.appendChild(row);
            container.appendChild(toast);

            window.setTimeout(function () {
                toast.classList.remove("opacity-0", "translate-x-5");
            }, 100 * index);
            window.setTimeout(function () {
                if (!toast.parentNode) return;
                toast.classList.add("opacity-0", "translate-x-5");
                window.setTimeout(function () { toast.remove(); }, 500);
            }, 4500);
        });
    }

    function scrollCurrentStep() {
        var scrollBox = document.getElementById("wizard-stepper-scroll");
        var target = document.querySelector("[data-current-step='true']");
        if (!scrollBox || !target) return;
        var boxRect = scrollBox.getBoundingClientRect();
        var stepRect = target.getBoundingClientRect();
        scrollBox.scrollTop += stepRect.top - boxRect.top - 24;
    }

    function scrollFormIntoView() {
        var main = document.querySelector(".nx-wizard-main");
        if (!main) return;
        var top = main.getBoundingClientRect().top + window.pageYOffset - 96;
        if (top < 0) top = 0;
        if (Math.abs(window.pageYOffset - top) < 48) return;
        try {
            window.scrollTo({ top: top, behavior: "smooth" });
        } catch (e) {
            window.scrollTo(0, top);
        }
    }

    function stopPing() {
        if (pingTimer) {
            window.clearInterval(pingTimer);
            pingTimer = null;
        }
    }

    function startPing() {
        stopPing();
        var root = rootEl();
        var pingUrl = root && root.getAttribute("data-nx-ping-url");
        if (!pingUrl) return;

        function ping() {
            fetch(pingUrl, {
                method: "POST",
                headers: {
                    "X-CSRFToken": getCookie("csrftoken"),
                    "X-Requested-With": "XMLHttpRequest"
                }
            }).catch(function () {});
        }
        ping();
        pingTimer = window.setInterval(ping, PING_MS);
    }

    function afterSwap(options) {
        options = options || {};
        if (window.NexusRepeaters && typeof window.NexusRepeaters.init === "function") {
            window.NexusRepeaters.init();
        }
        startPing();
        scrollCurrentStep();
        if (!options.keepScroll) scrollFormIntoView();
    }

    function leave(url) {
        stopPing();
        window.location.href = url;
    }

    function applyDocument(html, url, options) {
        options = options || {};
        var doc;
        try {
            doc = new window.DOMParser().parseFromString(html, "text/html");
        } catch (e) {
            leave(url);
            return;
        }
        var incoming = doc.getElementById(ROOT_ID);
        var current = rootEl();
        if (!incoming || !current || !isWizardUrl(url)) {
            leave(url);
            return;
        }

        cleanupOrphanDropdowns();
        current.replaceWith(incoming);
        activateScripts(incoming);
        showToastsFrom(doc);
        if (doc.title) document.title = doc.title;

        if (options.history !== "none") {
            var method = options.history === "replace" ? "replaceState" : "pushState";
            history[method]({ nxWizard: true }, "", url);
        }
        afterSwap({ keepScroll: !!options.keepScroll });
    }

    function visit(url, options) {
        options = options || {};
        if (!rootEl()) {
            leave(url);
            return;
        }
        if (options.method !== "POST" && sameLocation(url) && options.history !== "none") {
            return;
        }
        // One round-trip at a time: aborting a save mid-POST would drop the draft.
        if (busy) return;

        var controller = new window.AbortController();
        inflight = controller;
        busy = true;
        setLoading(true);

        var headers = {
            "X-Requested-With": "XMLHttpRequest",
            "Accept": "text/html"
        };
        var init = {
            method: options.method || "GET",
            credentials: "same-origin",
            redirect: "follow",
            headers: headers,
            signal: controller.signal
        };
        if (options.body) init.body = options.body;

        fetch(url, init).then(function (response) {
            var finalUrl = response.url || url;
            if (!response.ok) {
                leave(finalUrl);
                return null;
            }
            if (!isWizardUrl(finalUrl)) {
                leave(finalUrl);
                return null;
            }
            return response.text().then(function (html) {
                applyDocument(html, finalUrl, {
                    history: options.history,
                    keepScroll: options.keepScroll || sameLocation(finalUrl)
                });
            });
        }).catch(function (err) {
            if (err && err.name === "AbortError") return;
            leave(url);
        }).then(function () {
            if (inflight === controller) inflight = null;
            busy = false;
            setLoading(false);
        });
    }

    function formBody(form, submitter) {
        var data;
        try {
            data = submitter ? new window.FormData(form, submitter) : new window.FormData(form);
        } catch (e) {
            data = new window.FormData(form);
            if (submitter && submitter.name) data.set(submitter.name, submitter.value);
        }
        return data;
    }

    function onClick(event) {
        if (event.defaultPrevented || !isPlainLeftClick(event)) return;
        var root = rootEl();
        if (!root) return;
        var link = event.target && event.target.closest ? event.target.closest("a[href]") : null;
        if (!link || !root.contains(link)) return;
        if (link.hasAttribute("download") || (link.target && link.target !== "_self")) return;
        var href = link.getAttribute("href") || "";
        if (!href || href.charAt(0) === "#") return;
        if (!isWizardUrl(link.href)) return;
        event.preventDefault();
        visit(link.href, { method: "GET" });
    }

    function onSubmit(event) {
        if (event.defaultPrevented) return;
        var root = rootEl();
        if (!root) return;
        var form = event.target;
        if (!form || form.nodeName !== "FORM" || !root.contains(form)) return;
        if (form.target && form.target !== "_self") return;
        var action = form.getAttribute("action") || window.location.href;
        if (!isWizardUrl(action)) return;
        event.preventDefault();
        visit(action, {
            method: (form.getAttribute("method") || form.method || "POST").toUpperCase(),
            body: formBody(form, event.submitter)
        });
    }

    function onPopState() {
        if (!rootEl()) return;
        if (!isWizardUrl(window.location.href)) {
            window.location.reload();
            return;
        }
        visit(window.location.href, { method: "GET", history: "none" });
    }

    function start() {
        if (!rootEl()) return;
        document.addEventListener("click", onClick);
        document.addEventListener("submit", onSubmit);
        window.addEventListener("popstate", onPopState);
        try {
            history.replaceState({ nxWizard: true }, "", window.location.href);
        } catch (e) {}
        afterSwap({ keepScroll: true });
    }

    window.NexusWizard = {
        visit: visit,
        isWizardUrl: isWizardUrl
    };

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", start, { once: true });
    } else {
        start();
    }
})(window, document);
