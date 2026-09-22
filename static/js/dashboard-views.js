/* Gives every dashboard data table an accessible table/card presentation switch. */
(function () {
    const STORAGE_KEY = 'nexus-dashboard-data-view';

    function text(node) {
        return (node.textContent || '').replace(/\s+/g, ' ').trim();
    }

    function setView(root, view) {
        root.querySelectorAll('.dashboard-data-table').forEach((table) => {
            table.classList.toggle('dashboard-cards-view', view === 'cards');
        });
        root.querySelectorAll('.dashboard-view-toggle').forEach((button) => {
            button.setAttribute('aria-pressed', String(button.dataset.dashboardView === view));
        });
        try { localStorage.setItem(STORAGE_KEY, view); } catch (_) { /* private browsing */ }
    }

    function addToolbar(root) {
        const tables = Array.from(root.querySelectorAll('table:not([data-proposal-table])'));
        if (!tables.length) return;

        tables.forEach((table) => {
            table.classList.add('dashboard-data-table');
            const headings = Array.from(table.querySelectorAll('thead th')).map(text);
            table.querySelectorAll('tbody tr').forEach((row) => {
                Array.from(row.children).forEach((cell, index) => {
                    if (cell.tagName === 'TD') cell.dataset.cardLabel = headings[index] || 'Details';
                });
            });
        });

        const toolbar = document.createElement('div');
        toolbar.className = 'dashboard-view-toolbar';
        toolbar.setAttribute('role', 'group');
        toolbar.setAttribute('aria-label', 'Choose data presentation');
        toolbar.innerHTML = '<span class="dashboard-view-toolbar__label">View</span>' +
            '<button type="button" class="dashboard-view-toggle" data-dashboard-view="table">Table View</button>' +
            '<button type="button" class="dashboard-view-toggle" data-dashboard-view="cards">Card View</button>';
        const anchor = tables[0].closest('.overflow-x-auto') || tables[0];
        anchor.parentNode.insertBefore(toolbar, anchor);
        toolbar.querySelectorAll('button').forEach((button) => {
            button.addEventListener('click', () => setView(root, button.dataset.dashboardView));
        });

        let preferred = 'table';
        try { preferred = localStorage.getItem(STORAGE_KEY) === 'cards' ? 'cards' : 'table'; } catch (_) { /* ignore */ }
        setView(root, preferred);
    }

    document.addEventListener('DOMContentLoaded', () => {
        document.querySelectorAll('[data-dashboard-view]').forEach(addToolbar);
        document.querySelectorAll('[data-proposal-layout]').forEach((root) => {
            const key = 'nexus-proposal-layout';
            const apply = (view) => {
                root.querySelectorAll('[data-proposal-panel]').forEach((panel) => {
                    panel.hidden = panel.dataset.proposalPanel !== view;
                });
                root.querySelectorAll('[data-proposal-view]').forEach((button) => {
                    button.setAttribute('aria-pressed', String(button.dataset.proposalView === view));
                });
            };
            let view = 'cards';
            try { if (localStorage.getItem(key) === 'table') view = 'table'; } catch (_) { /* ignore */ }
            apply(view);
            root.querySelectorAll('[data-proposal-view]').forEach((button) => {
                button.addEventListener('click', () => {
                    apply(button.dataset.proposalView);
                    try { localStorage.setItem(key, button.dataset.proposalView); } catch (_) { /* ignore */ }
                });
            });
        });
    });
})();
