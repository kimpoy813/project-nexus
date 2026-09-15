/* ==========================================================================
   NExUS — one client-side script (loaded on every page via base.html).

   Consolidates what used to live in four places:
     • toast renderer for Django messages        (was inline in base.html)
     • idle-timeout logout                       (was inline in base.html)
     • dashboard table ⇄ card presentation       (was dashboard-views.js)
     • declarative progress gauges               (was duplicated inline in
                                                  every role dashboard)
   ========================================================================== */
(function () {
    "use strict";

    /* ------------------------------------------------------------------ */
    /* small helpers                                                       */
    /* ------------------------------------------------------------------ */
    function getCookie(name) {
        if (!document.cookie) return null;
        for (const raw of document.cookie.split(";")) {
            const c = raw.trim();
            if (c.startsWith(name + "=")) return decodeURIComponent(c.slice(name.length + 1));
        }
        return null;
    }
    window.nxGetCookie = getCookie;

    /* ------------------------------------------------------------------ */
    /* 1. Toast renderer                                                    */
    /* ------------------------------------------------------------------ */
    function renderToasts() {
        const data = document.getElementById("messages-data");
        const container = document.getElementById("toast-container");
        if (!data || !container) return;

        data.querySelectorAll("[data-message]").forEach((el, index) => {
            const toast = document.createElement("div");
            const tags = (el.getAttribute("data-tags") || "info").toLowerCase();
            toast.className = "nx-toast" + (tags.includes("success") ? " nx-toast--success"
                : tags.includes("error") ? " nx-toast--error"
                : tags.includes("warning") ? " nx-toast--warning" : "");
            toast.setAttribute("role", "alert");

            const text = document.createElement("span");
            text.textContent = el.getAttribute("data-message");

            const close = document.createElement("button");
            close.type = "button";
            close.setAttribute("aria-label", "Dismiss notification");
            close.textContent = "×";
            close.addEventListener("click", () => dismiss());

            toast.appendChild(text);
            toast.appendChild(close);
            container.appendChild(toast);

            const showAt = setTimeout(() => toast.classList.add("is-visible"), 90 * index);
            const hideAt = setTimeout(dismiss, 5000);

            function dismiss() {
                clearTimeout(showAt);
                clearTimeout(hideAt);
                toast.classList.remove("is-visible");
                setTimeout(() => toast.remove(), 320);
            }
        });

        data.remove();
    }

    /* ------------------------------------------------------------------ */
    /* 2. Idle-timeout logout (authenticated pages only)                    */
    /* ------------------------------------------------------------------ */
    function initIdleLogout() {
        const cfg = document.getElementById("nx-idle-config");
        if (!cfg) return; // anonymous users never idle out

        const logoutUrl = cfg.dataset.logoutUrl;
        const loginUrl = cfg.dataset.loginUrl;
        const IDLE_LIMIT_MS = 30 * 60 * 1000;
        const WARN_BEFORE_MS = 5 * 60 * 1000;
        let idleTimer = null, warnTimer = null, countdownInterval = null;

        async function logoutIdle() {
            try {
                await fetch(logoutUrl, {
                    method: "POST",
                    headers: { "Content-Type": "application/json", "X-CSRFToken": getCookie("csrftoken") },
                    body: JSON.stringify({ reason: "idle" }),
                });
            } catch (_) { /* proceed to login regardless */ }
            window.location.href = loginUrl + "?reason=idle";
        }

        function showIdleWarning() {
            const warning = document.getElementById("idle-warning");
            const countdown = document.getElementById("idle-countdown");
            if (!warning) return;
            warning.classList.remove("hidden");
            if (!countdown) return;
            let timeLeft = WARN_BEFORE_MS / 1000;
            countdown.textContent = Math.ceil(timeLeft / 60);
            clearInterval(countdownInterval);
            countdownInterval = setInterval(() => {
                timeLeft--;
                countdown.textContent = Math.max(0, Math.ceil(timeLeft / 60));
                if (timeLeft <= 0) clearInterval(countdownInterval);
            }, 1000);
        }

        window.resetIdleTimer = function () {
            clearTimeout(idleTimer); clearTimeout(warnTimer); clearInterval(countdownInterval);
            document.getElementById("idle-warning")?.classList.add("hidden");
            warnTimer = setTimeout(showIdleWarning, IDLE_LIMIT_MS - WARN_BEFORE_MS);
            idleTimer = setTimeout(logoutIdle, IDLE_LIMIT_MS);
        };

        ["mousemove", "mousedown", "keydown", "touchstart", "scroll"].forEach((evt) =>
            window.addEventListener(evt, window.resetIdleTimer, { passive: true })
        );
        document.addEventListener("visibilitychange", () => { if (!document.hidden) window.resetIdleTimer(); });
        window.resetIdleTimer();
    }

    /* ------------------------------------------------------------------ */
    /* 3. Dashboard table ⇄ card presentation toggle (opt-in per page)      */
    /* ------------------------------------------------------------------ */
    function initTableViews() {
        const STORAGE_KEY = "nexus-dashboard-data-view";

        function text(node) { return (node.textContent || "").replace(/\s+/g, " ").trim(); }

        function setView(root, view) {
            root.querySelectorAll(".dashboard-data-table").forEach((t) =>
                t.classList.toggle("dashboard-cards-view", view === "cards"));
            root.querySelectorAll(".dashboard-view-toggle").forEach((b) =>
                b.setAttribute("aria-pressed", String(b.dataset.dashboardView === view)));
            try { localStorage.setItem(STORAGE_KEY, view); } catch (_) { /* private mode */ }
        }

        document.querySelectorAll("[data-dashboard-view]").forEach((root) => {
            const tables = Array.from(root.querySelectorAll("table"));
            if (!tables.length) return;

            tables.forEach((table) => {
                table.classList.add("dashboard-data-table");
                const headings = Array.from(table.querySelectorAll("thead th")).map(text);
                table.querySelectorAll("tbody tr").forEach((row) => {
                    Array.from(row.children).forEach((cell, i) => {
                        if (cell.tagName === "TD") cell.dataset.cardLabel = headings[i] || "Details";
                    });
                });
            });

            const toolbar = document.createElement("div");
            toolbar.className = "dashboard-view-toolbar";
            toolbar.setAttribute("role", "group");
            toolbar.setAttribute("aria-label", "Choose data presentation");
            toolbar.innerHTML =
                '<span class="dashboard-view-toolbar__label">View</span>' +
                '<button type="button" class="dashboard-view-toggle" data-dashboard-view="table">Table</button>' +
                '<button type="button" class="dashboard-view-toggle" data-dashboard-view="cards">Cards</button>';
            root.insertBefore(toolbar, tables[0].closest(".overflow-x-auto") || tables[0]);
            toolbar.querySelectorAll("button").forEach((b) =>
                b.addEventListener("click", () => setView(root, b.dataset.dashboardView)));

            let preferred = "table";
            try { preferred = localStorage.getItem(STORAGE_KEY) || preferred; } catch (_) { /* ignore */ }
            setView(root, preferred);
        });
    }

    /* ------------------------------------------------------------------ */
    /* 4. Declarative progress gauges                                       */
    /*                                                                       */
    /* <canvas class="nx-gauge" data-nx-gauge="62"> renders a three-zone    */
    /* arc (proposal → MOA → implementation) with a single wipe animation.  */
    /* Pair with .nx-gauge-label for the centred percentage readout.        */
    /* ------------------------------------------------------------------ */
    function drawGauge(canvas, pct) {
        const ctx = canvas.getContext("2d");
        const size = canvas.width;
        const cx = size / 2, cy = size / 2;
        const r = size / 2 - 7, lw = 10;
        const start = (-234 * Math.PI) / 180, sweep = (288 * Math.PI) / 180;
        const zone2 = start + sweep * 0.4, zone3 = start + sweep * 0.6;
        const progressEnd = start + sweep * (Math.max(0, Math.min(pct, 100)) / 100);

        ctx.clearRect(0, 0, size, size);
        ctx.lineCap = "butt";
        for (const [s, e, color] of [[start, zone2, "#103b07"], [zone2, zone3, "#5a1113"], [zone3, start + sweep, "#d8a90f"]]) {
            ctx.beginPath();
            ctx.strokeStyle = color;
            ctx.globalAlpha = 0.22;
            ctx.lineWidth = lw;
            ctx.arc(cx, cy, r, s, e, false);
            ctx.stroke();
        }
        ctx.globalAlpha = 1;
        if (progressEnd > start) {
            for (const [s, e, color] of [[start, Math.min(progressEnd, zone2), "#103b07"],
                                         [zone2, Math.min(progressEnd, zone3), "#5a1113"],
                                         [zone3, progressEnd, "#d8a90f"]]) {
                if (e <= s) continue;
                ctx.beginPath();
                ctx.strokeStyle = color;
                ctx.lineWidth = lw;
                ctx.arc(cx, cy, r, s, Math.min(e, start + sweep), false);
                ctx.stroke();
            }
        }
    }

    function initGauges() {
        document.querySelectorAll("canvas[data-nx-gauge]").forEach((canvas) => {
            const target = Math.max(0, Math.min(100, Number(canvas.dataset.nxGauge) || 0));
            const label = canvas.closest(".nx-gauge-wrap")?.querySelector("[data-nx-gauge-label]");
            const size = 96;
            canvas.width = size; canvas.height = size;

            if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
                drawGauge(canvas, target);
                if (label) label.textContent = Math.round(target) + "%";
                return;
            }
            const duration = 900, t0 = performance.now();
            (function frame(now) {
                const t = Math.min(1, (now - t0) / duration);
                const eased = 1 - Math.pow(1 - t, 3);
                const pct = target * eased;
                drawGauge(canvas, pct);
                if (label) label.textContent = Math.round(pct) + "%";
                if (t < 1) requestAnimationFrame(frame);
            })(t0);
        });
    }

    /* Public: re-render gauges when dashboard content changes dynamically. */
    window.nxInitGauges = initGauges;

    /* ------------------------------------------------------------------ */
    /* 5. Workspace sidebar (mobile off-canvas)                             */
    /* ------------------------------------------------------------------ */
    function initSidebar() {
        const sidebar = document.getElementById("nx-app-sidebar");
        const toggle = document.getElementById("nx-sidebar-toggle");
        const scrim = document.getElementById("nx-sidebar-scrim");
        if (!sidebar || !toggle) return;

        function setOpen(open) {
            sidebar.classList.toggle("is-open", open);
            if (scrim) scrim.classList.toggle("hidden", !open);
            toggle.setAttribute("aria-expanded", String(open));
        }
        toggle.addEventListener("click", () => setOpen(!sidebar.classList.contains("is-open")));
        scrim?.addEventListener("click", () => setOpen(false));
        document.addEventListener("keydown", (e) => { if (e.key === "Escape") setOpen(false); });
    }

    /* ------------------------------------------------------------------ */
    document.addEventListener("DOMContentLoaded", () => {
        renderToasts();
        initIdleLogout();
        initTableViews();
        initGauges();
        initSidebar();
    });
})();
