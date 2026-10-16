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

    /* 20x20 heroicons drawn with `currentColor`, like every other icon in the
       system, so the pressed state can invert them. */
    const ICONS = {
        table: '<svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4" viewBox="0 0 20 20" fill="currentColor" aria-hidden="true"><path fill-rule="evenodd" d="M3 3.5A1.5 1.5 0 0 1 4.5 2h11A1.5 1.5 0 0 1 17 3.5v13a1.5 1.5 0 0 1-1.5 1.5h-11A1.5 1.5 0 0 1 3 16.5v-13ZM4.5 3.5a.5.5 0 0 0-.5.5V7h4V3.5h-3.5ZM9.5 3.5V7h6V3.5h-6ZM4.5 8.5v4h4v-4h-4ZM9.5 8.5v4h6v-4h-6ZM4.5 14v1.5a.5.5 0 0 0 .5.5H7v-2H4.5ZM8.5 14v2h6.5a.5.5 0 0 0 .5-.5V14h-7Z" clip-rule="evenodd" /></svg>',
        cards: '<svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4" viewBox="0 0 20 20" fill="currentColor" aria-hidden="true"><path d="M2 4.5A1.5 1.5 0 0 1 3.5 3h4A1.5 1.5 0 0 1 9 4.5v4A1.5 1.5 0 0 1 7.5 10h-4A1.5 1.5 0 0 1 2 8.5v-4ZM11 4.5A1.5 1.5 0 0 1 12.5 3h4A1.5 1.5 0 0 1 18 4.5v4a1.5 1.5 0 0 1-1.5 1.5h-4A1.5 1.5 0 0 1 11 8.5v-4ZM2 13.5A1.5 1.5 0 0 1 3.5 12h4a1.5 1.5 0 0 1 1.5 1.5v1A1.5 1.5 0 0 1 7.5 16h-4A1.5 1.5 0 0 1 2 14.5v-1ZM12.5 12h4a1.5 1.5 0 0 1 1.5 1.5v1a1.5 1.5 0 0 1-1.5 1.5h-4a1.5 1.5 0 0 1-1.5-1.5v-1a1.5 1.5 0 0 1 1.5-1.5Z" /></svg>',
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

    function applyView(view) {
        controllers.forEach((controller) => controller.apply(view));
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
        const anchor = table.closest('.overflow-x-auto') || table;
        anchor.parentNode.insertBefore(toolbar, anchor);

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
                applyView(view);
                writeView(view);
            });
        });
    }

    /* A hand-built table/card pair: show the panel that matches the view. */
    function enhanceLayout(root) {
        let buttons = Array.from(root.querySelectorAll('[data-proposal-view]'));
        if (!buttons.length) {
            // The template did not ship a switch; provide the same one.
            const toolbar = buildToolbar('Choose proposal layout');
            root.insertBefore(toolbar, root.firstChild);
            buttons = Array.from(toolbar.querySelectorAll('[data-proposal-view]'));
        }
        controllers.push({
            apply(view) {
                root.querySelectorAll('[data-proposal-panel]').forEach((panel) => {
                    panel.hidden = panel.dataset.proposalPanel !== view;
                });
                buttons.forEach((button) => {
                    button.setAttribute('aria-pressed', String(button.dataset.proposalView === view));
                });
            },
        });
        buttons.forEach((button) => {
            button.addEventListener('click', () => {
                const view = button.dataset.proposalView;
                applyView(view);
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
