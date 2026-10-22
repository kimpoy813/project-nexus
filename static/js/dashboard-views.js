/* Lets proposals be read as a table or as a stack of cards.

   Only proposal tables are switchable. Other dashboard tables (extension
   targets, campus statistics, user lists) are matrix data whose columns
   lose their meaning once each row becomes a card, so they stay tables.

   Two presentations share one preference:
   - `data-proposal-layout` holds a hand-built table panel and a hand-built
     card panel (the faculty dashboard).
   - `table[data-proposal-table]` is a plain semantic table that is restyled
     into cards by CSS when the card view is active. */
(function () {
    'use strict';

    const STORAGE_KEY = 'nexus-proposal-view';
    const DEFAULT_VIEW = 'cards';

    /* 20x20 glyphs drawn with `currentColor`, like every other icon in the
       system, so the thumb can turn the active one white. They are drawn to
       be told apart at a glance: the table is a framed grid with a filled
       header row, the card view is a pair of content cards. */
    const ICONS = {
        table: '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor" aria-hidden="true"><path fill-rule="evenodd" d="M4.5 2.5h11a2 2 0 0 1 2 2v11a2 2 0 0 1-2 2h-11a2 2 0 0 1-2-2v-11a2 2 0 0 1 2-2Zm0 1.5a.5.5 0 0 0-.5.5v11a.5.5 0 0 0 .5.5h11a.5.5 0 0 0 .5-.5v-11a.5.5 0 0 0-.5-.5h-11Z" clip-rule="evenodd" /><path d="M4 4h12v3H4Z" /><path d="M4 10.8h12v1.4H4Z" /><path d="M9.3 7h1.4v9H9.3Z" /></svg>',
        cards: '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor" aria-hidden="true"><path fill-rule="evenodd" d="M4.25 3A1.75 1.75 0 0 0 2.5 4.75v10.5A1.75 1.75 0 0 0 4.25 17h3.5A1.75 1.75 0 0 0 9.5 15.25V4.75A1.75 1.75 0 0 0 7.75 3h-3.5Zm.45 2.6h2.6a.8.8 0 0 1 0 1.6H4.7a.8.8 0 0 1 0-1.6Zm-.1 4h1.6a.7.7 0 0 1 0 1.4H4.6a.7.7 0 0 1 0-1.4Z" clip-rule="evenodd" /><path fill-rule="evenodd" d="M12.25 3a1.75 1.75 0 0 0-1.75 1.75v10.5A1.75 1.75 0 0 0 12.25 17h3.5a1.75 1.75 0 0 0 1.75-1.75V4.75A1.75 1.75 0 0 0 15.75 3h-3.5Zm.45 2.6h2.6a.8.8 0 0 1 0 1.6h-2.6a.8.8 0 0 1 0-1.6Zm-.1 4h1.6a.7.7 0 0 1 0 1.4h-1.6a.7.7 0 0 1 0-1.4Z" clip-rule="evenodd" /></svg>',
    };

    const LABELS = { table: 'Table view', cards: 'Card view' };

    /* Every presentation on the page registers how to switch itself, so one
       click keeps the whole page (and the next visit) consistent. */
    const controllers = [];

    function text(node) {
        return (node.textContent || '').replace(/\s+/g, ' ').trim();
    }

    function readView() {
        try {
            const stored = localStorage.getItem(STORAGE_KEY);
            return stored === 'table' || stored === 'cards' ? stored : DEFAULT_VIEW;
        } catch (_) {
            return DEFAULT_VIEW; /* private browsing */
        }
    }

    function writeView(view) {
        try { localStorage.setItem(STORAGE_KEY, view); } catch (_) { /* private browsing */ }
    }

    function applyView(view, interactive) {
        controllers.forEach((controller) => controller.apply(view, Boolean(interactive)));
    }

    function toggleButton(view) {
        const button = document.createElement('button');
        button.setAttribute('type', 'button');
        button.className = 'dashboard-view-toggle';
        button.dataset.proposalView = view;
        button.setAttribute('aria-label', LABELS[view]);
        button.setAttribute('title', LABELS[view]);
        button.setAttribute('aria-pressed', 'false');
        button.innerHTML = ICONS[view];
        return button;
    }

    function buildToolbar(label) {
        const toolbar = document.createElement('div');
        toolbar.className = 'dashboard-view-toolbar';
        toolbar.setAttribute('role', 'group');
        toolbar.setAttribute('aria-label', label);
        ['table', 'cards'].forEach((view) => toolbar.appendChild(toggleButton(view)));
        return toolbar;
    }

    /* The switch sits in the panel header, at the right edge of the section
       title, so find the card that wraps a layout instead of dropping the
       switch into the panel body below the header. */
    function closestCard(root) {
        return typeof root.closest === 'function' ? root.closest('.nx-panel, .nx-card') : null;
    }

    /* A template may ship the switch in its header (the faculty dashboard), or
       leave a slot there for this script to fill, so look at both before
       building a new one. */
    function findToggles(root) {
        const own = root.querySelectorAll('[data-proposal-view]');
        if (own.length) return Array.from(own);
        const card = closestCard(root);
        return card ? Array.from(card.querySelectorAll('[data-proposal-view]')) : [];
    }

    function placeToolbar(root, toolbar) {
        const card = closestCard(root);
        const slot = card && card.querySelector('[data-proposal-view-slot]');
        if (slot) {
            slot.appendChild(toolbar);
            return;
        }
        // No header slot: keep the switch above the panels rather than lose it.
        root.insertBefore(toolbar, root.firstChild);
    }

    function markCardLabels(table) {
        const headings = Array.from(table.querySelectorAll('thead th')).map(text);
        table.querySelectorAll('tbody tr').forEach((row) => {
            Array.from(row.children).forEach((cell, index) => {
                if (cell.tagName === 'TD') cell.dataset.cardLabel = headings[index] || 'Details';
            });
        });
    }

    /* A plain proposal table: give it a switch and restyle it as cards when
       the card view is active. */
    function enhanceTable(table) {
        table.classList.add('dashboard-data-table');
        markCardLabels(table);

        const toolbar = buildToolbar('Choose proposal layout');
        const card = closestCard(table);
        const slot = card && card.querySelector('[data-proposal-view-slot]');
        if (slot) {
            slot.appendChild(toolbar);
        } else {
            const anchor = table.closest('.overflow-x-auto') || table;
            anchor.parentNode.insertBefore(toolbar, anchor);
        }

        const buttons = Array.from(toolbar.querySelectorAll('[data-proposal-view]'));
        controllers.push({
            apply(view) {
                table.classList.toggle('dashboard-cards-view', view === 'cards');
                buttons.forEach((button) => {
                    button.setAttribute('aria-pressed', String(button.dataset.proposalView === view));
                });
            },
        });
        buttons.forEach((button) => {
            button.addEventListener('click', () => {
                const view = button.dataset.proposalView;
                applyView(view, true);
                writeView(view);
            });
        });
    }

    /* A hand-built table/card pair: show the panel that matches the view. */
    function enhanceLayout(root) {
        let buttons = findToggles(root);
        if (!buttons.length) {
            // The template did not ship a switch; provide the same one in the
            // header slot beside the section title.
            const toolbar = buildToolbar('Choose proposal layout');
            placeToolbar(root, toolbar);
            buttons = Array.from(toolbar.querySelectorAll('[data-proposal-view]'));
        }
        controllers.push({
            apply(view, interactive) {
                root.querySelectorAll('[data-proposal-panel]').forEach((panel) => {
                    panel.hidden = panel.dataset.proposalPanel !== view;
                    if (
                        panel.dataset.proposalPanel === 'cards' &&
                        typeof globalThis !== 'undefined' &&
                        globalThis.nexusGauge &&
                        typeof globalThis.nexusGauge.onPanelToggle === 'function'
                    ) {
                        globalThis.nexusGauge.onPanelToggle(panel, !panel.hidden, interactive);
                    }
                });
                buttons.forEach((button) => {
                    button.setAttribute('aria-pressed', String(button.dataset.proposalView === view));
                });
            },
        });
        buttons.forEach((button) => {
            button.addEventListener('click', () => {
                const view = button.dataset.proposalView;
                applyView(view, true);
                writeView(view);
            });
        });
    }

    document.addEventListener('DOMContentLoaded', () => {
        document.querySelectorAll('[data-proposal-layout]').forEach(enhanceLayout);
        document.querySelectorAll('table[data-proposal-table]').forEach((table) => {
            // A layout already ships its own card panel; do not restyle it twice.
            if (table.closest('[data-proposal-layout]')) return;
            enhanceTable(table);
        });
        applyView(readView());
    });
})();

/* One shared tooltip for icon-only table actions (and any other control that
   opts in with `data-nx-tooltip`). It is delegated, so rows added by a filter
   or an inline editor get the same behaviour, and the bubble is appended to
   <body> so `overflow-x-auto` table wrappers cannot clip it. */
(function () {
    'use strict';

    function initActionTooltips() {
        if (!document.body || typeof document.body.appendChild !== 'function') return;

        const SHOW_DELAY = 120;
        const GAP = 8;
        const EDGE = 8;
        let bubble = null;
        let activeTrigger = null;
        let openTimer = null;

        function ensureBubble() {
            if (bubble) return bubble;
            bubble = document.createElement('div');
            bubble.className = 'nx-tooltip';
            bubble.setAttribute('role', 'presentation');
            document.body.appendChild(bubble);
            return bubble;
        }

        function place() {
            if (!bubble || !activeTrigger) return;
            const triggerRect = activeTrigger.getBoundingClientRect();
            bubble.style.left = '0px';
            bubble.style.top = '0px';
            const bubbleRect = bubble.getBoundingClientRect();
            let left = triggerRect.left + (triggerRect.width - bubbleRect.width) / 2;
            left = Math.max(EDGE, Math.min(left, window.innerWidth - bubbleRect.width - EDGE));
            let top = triggerRect.top - bubbleRect.height - GAP;
            let placement = 'top';
            if (top < EDGE) {
                top = triggerRect.bottom + GAP;
                placement = 'bottom';
            }
            bubble.dataset.placement = placement;
            bubble.style.left = left + 'px';
            bubble.style.top = top + 'px';
            const arrow = triggerRect.left + triggerRect.width / 2 - left;
            bubble.style.setProperty(
                '--nx-tooltip-arrow-left',
                Math.max(12, Math.min(bubbleRect.width - 12, arrow)) + 'px'
            );
        }

        function show(trigger) {
            if (!trigger || trigger === activeTrigger) return;
            activeTrigger = trigger;
            window.clearTimeout(openTimer);
            const label = (trigger.dataset.nxTooltip || trigger.getAttribute('aria-label') || '').trim();
            if (!label) return;
            openTimer = window.setTimeout(function () {
                if (activeTrigger !== trigger) return;
                const tip = ensureBubble();
                tip.textContent = label;
                tip.dataset.placement = 'top';
                tip.classList.add('is-visible');
                place();
            }, SHOW_DELAY);
        }

        function hide() {
            window.clearTimeout(openTimer);
            openTimer = null;
            activeTrigger = null;
            if (bubble) bubble.classList.remove('is-visible');
        }

        function triggerFrom(event) {
            const target = event.target;
            return target && target.closest ? target.closest('[data-nx-tooltip]') : null;
        }

        document.addEventListener('pointerover', function (event) {
            const trigger = triggerFrom(event);
            if (!trigger) return;
            if (event.relatedTarget && trigger.contains(event.relatedTarget)) return;
            show(trigger);
        });

        document.addEventListener('pointerout', function (event) {
            const trigger = triggerFrom(event);
            if (!trigger) return;
            if (event.relatedTarget && trigger.contains(event.relatedTarget)) return;
            hide();
        });

        document.addEventListener('focusin', function (event) {
            const trigger = triggerFrom(event);
            if (trigger) show(trigger);
        });

        document.addEventListener('focusout', function (event) {
            if (triggerFrom(event)) hide();
        });

        document.addEventListener('keydown', function (event) {
            if (event.key === 'Escape') hide();
        });

        document.addEventListener('click', function (event) {
            if (triggerFrom(event)) hide();
        });

        /* Scrolling or resizing would leave the fixed bubble behind its row. */
        window.addEventListener('scroll', hide, true);
        window.addEventListener('resize', hide);
    }

    document.addEventListener('DOMContentLoaded', initActionTooltips);
})();
