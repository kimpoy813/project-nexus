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
