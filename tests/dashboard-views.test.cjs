const { test } = require('node:test');
const assert = require('node:assert/strict');
const { readFileSync } = require('node:fs');
const { runInNewContext } = require('node:vm');
const script = readFileSync('static/js/dashboard-views.js', 'utf8');

/* ---------------------------------------------------------------------------
 * A very small DOM stand-in: enough for the switch, not a browser.
 * ------------------------------------------------------------------------ */

function createElement(tagName) {
    const element = {
        tagName: tagName.toUpperCase(),
        className: '',
        innerHTML: '',
        dataset: {},
        children: [],
        attributes: {},
        listeners: {},
        setAttribute(name, value) { this.attributes[name] = value; },
        getAttribute(name) { return this.attributes[name]; },
        appendChild(child) { this.children.push(child); child.parentNode = this; return child; },
        addEventListener(event, callback) { (this.listeners[event] ||= []).push(callback); },
        click() { (this.listeners.click || []).forEach((callback) => callback()); },
        querySelectorAll(selector) {
            if (selector === '[data-proposal-view]') {
                return this.children.filter((child) => child.dataset.proposalView);
            }
            return [];
        },
        closest() { return null; },
    };
    element.classList = {
        add(name) { element.className = (element.className + ' ' + name).trim(); },
        toggle(name, on) {
            const classes = element.className.split(' ').filter(Boolean);
            const index = classes.indexOf(name);
            if (on && index === -1) classes.push(name);
            if (!on && index !== -1) classes.splice(index, 1);
            element.className = classes.join(' ');
        },
        contains(name) { return element.className.split(' ').includes(name); },
    };
    return element;
}

function createCell(tagName, text) {
    const cell = createElement(tagName);
    cell.textContent = text || '';
    return cell;
}

function createRow(cells) {
    const row = createElement('tr');
    row.children = cells;
    cells.forEach((cell) => { cell.parentNode = row; });
    return row;
}

function createTable(headings, rows) {
    const table = createElement('table');
    table.dataset.proposalTable = '';

    const head = createElement('thead');
    const headRow = createRow(headings.map((heading) => createCell('th', heading)));
    head.children = [headRow];
    headRow.parentNode = head;

    const body = createElement('tbody');
    body.children = rows;

    table.children = [head, body];
    table.querySelectorAll = (selector) => {
        if (selector === 'thead th') return headRow.children;
        if (selector === 'tbody tr') return rows;
        return [];
    };
    return table;
}

function createDocument({ layouts = [], tables = [] } = {}) {
    const doc = {
        createElement,
        addEventListener(event, callback) { callback(); },
        querySelectorAll(selector) {
            if (selector === '[data-proposal-layout]') return layouts;
            if (selector === 'table[data-proposal-table]') return tables;
            return [];
        },
    };
    return doc;
}

function run({ layouts = [], tables = [], saved = null, blocked = false } = {}) {
    const storage = { value: saved };
    const doc = createDocument({ layouts, tables });
    runInNewContext(script, {
        document: doc,
        localStorage: {
            getItem() { if (blocked) throw Error('Blocked'); return storage.value; },
            setItem(key, value) { if (blocked) throw Error('Blocked'); storage.value = value; },
        },
    });
    return { storage, doc };
}

/* ---------------------------------------------------------------------------
 * Hand-built table/card panels (the faculty dashboard).
 * ------------------------------------------------------------------------ */

function setupLayout() {
    const panels = ['table', 'cards'].map((view) => ({ dataset: { proposalPanel: view } }));
    const buttons = ['table', 'cards'].map((view) => ({
        dataset: { proposalView: view },
        setAttribute(name, value) { this[name] = value; },
        addEventListener(event, callback) { this.click = callback; },
    }));
    const root = { querySelectorAll: (selector) => (selector === '[data-proposal-panel]' ? panels : buttons) };
    return { panels, buttons, root };
}

test('defaults to cards, toggles both ways and saves preference', () => {
    const { panels, buttons, root } = setupLayout();
    const { storage } = run({ layouts: [root] });
    assert.equal(panels[0].hidden, true);
    assert.equal(buttons[1]['aria-pressed'], 'true');
    buttons[0].click();
    assert.equal(panels[0].hidden, false);
    assert.equal(panels[1].hidden, true);
    assert.equal(buttons[0]['aria-pressed'], 'true');
    assert.equal(storage.value, 'table');
    buttons[1].click();
    assert.equal(panels[1].hidden, false);
    assert.equal(storage.value, 'cards');
});

test('restores table preference and ignores invalid preferences', () => {
    const first = setupLayout();
    run({ layouts: [first.root], saved: 'table' });
    assert.equal(first.panels[0].hidden, false);

    const second = setupLayout();
    run({ layouts: [second.root], saved: 'invalid' });
    assert.equal(second.panels[1].hidden, false);
});

test('works when browser storage is blocked', () => {
    const { panels, buttons, root } = setupLayout();
    run({ layouts: [root], blocked: true });
    buttons[0].click();
    assert.equal(panels[0].hidden, false);
});

/* ---------------------------------------------------------------------------
 * Plain proposal tables.
 * ------------------------------------------------------------------------ */

test('adds an icon-only switch above a proposal table', () => {
    const table = createTable(['Title', 'Proponent'], [createRow([createCell('td', 'A proposal'), createCell('td', 'Ana')])]);
    const parent = { insertBefore(node) { this.inserted = node; } };
    table.closest = () => null;
    Object.defineProperty(table, 'parentNode', { value: parent });

    run({ tables: [table] });
    const toolbar = parent.inserted;
    assert.ok(toolbar, 'a toolbar is inserted before the table');
    assert.equal(toolbar.className, 'dashboard-view-toolbar');
    assert.equal(toolbar.getAttribute('aria-label'), 'Choose proposal layout');

    const buttons = toolbar.querySelectorAll('[data-proposal-view]');
    assert.equal(buttons.length, 2);
    assert.deepEqual(buttons.map((button) => button.dataset.proposalView), ['table', 'cards']);
    // Icon-only: no "Table View"/"Card View" wording and no "View" caption.
    for (const button of buttons) {
        assert.doesNotMatch(button.innerHTML, /Table View|Card View|View/);
        assert.match(button.innerHTML, /^<svg /);
        assert.equal(button.getAttribute('aria-label'), button.dataset.proposalView === 'table' ? 'Table view' : 'Card view');
    }
    // The two glyphs must not read as the same shape: a framed grid with a
    // header row for the table, a pair of content cards for the card view.
    const [tableButton, cardsButton] = buttons;
    assert.notEqual(tableButton.innerHTML, cardsButton.innerHTML, 'the table and card glyphs must be distinguishable');
    assert.match(tableButton.innerHTML, /fill-rule="evenodd"/);
    assert.equal((cardsButton.innerHTML.match(/<path/g) || []).length, 2, 'the card view draws two cards');
    assert.equal(toolbar.children.length, 2, 'the switch holds nothing but the two icons');
});

test('marks the cells with their column heading and restyles the table as cards', () => {
    const row = createRow([createCell('td', 'A proposal'), createCell('td', 'Ana Reyes')]);
    const table = createTable(['Title', 'Proponent'], [row]);
    table.closest = () => null;
    Object.defineProperty(table, 'parentNode', { value: { insertBefore() {} } });

    run({ tables: [table] });

    assert.ok(table.classList.contains('dashboard-data-table'));
    assert.equal(row.children[0].dataset.cardLabel, 'Title');
    assert.equal(row.children[1].dataset.cardLabel, 'Proponent');
    // Cards are the default presentation.
    assert.ok(table.classList.contains('dashboard-cards-view'));
});

test('the switch flips the table between cards and rows and remembers the choice', () => {
    const table = createTable(['Title'], [createRow([createCell('td', 'A proposal')])]);
    const parent = { insertBefore(node) { this.inserted = node; } };
    table.closest = () => null;
    Object.defineProperty(table, 'parentNode', { value: parent });

    const { storage } = run({ tables: [table] });
    const [tableButton, cardsButton] = parent.inserted.querySelectorAll('[data-proposal-view]');

    assert.ok(table.classList.contains('dashboard-cards-view'));
    assert.equal(cardsButton.getAttribute('aria-pressed'), 'true');

    tableButton.click();
    assert.ok(!table.classList.contains('dashboard-cards-view'));
    assert.equal(tableButton.getAttribute('aria-pressed'), 'true');
    assert.equal(cardsButton.getAttribute('aria-pressed'), 'false');
    assert.equal(storage.value, 'table');

    cardsButton.click();
    assert.ok(table.classList.contains('dashboard-cards-view'));
    assert.equal(storage.value, 'cards');
});

test('a restored table preference starts every proposal table as a table', () => {
    const table = createTable(['Title'], [createRow([createCell('td', 'A proposal')])]);
    table.closest = () => null;
    Object.defineProperty(table, 'parentNode', { value: { insertBefore() {} } });

    run({ tables: [table], saved: 'table' });
    assert.ok(!table.classList.contains('dashboard-cards-view'));
});

test('one switch keeps every proposal table on the page in step', () => {
    const first = createTable(['Title'], [createRow([createCell('td', 'One')])]);
    const second = createTable(['Title'], [createRow([createCell('td', 'Two')])]);
    [first, second].forEach((table) => {
        table.closest = () => null;
        const parent = { insertBefore(node) { this.inserted = node; } };
        Object.defineProperty(table, 'parentNode', { value: parent });
    });

    const { storage } = run({ tables: [first, second] });
    assert.equal(storage.value, null);

    // The second table's switch drives both tables.
    const [secondTableButton] = second.parentNode.inserted.querySelectorAll('[data-proposal-view]');
    secondTableButton.click();
    assert.ok(!first.classList.contains('dashboard-cards-view'));
    assert.ok(!second.classList.contains('dashboard-cards-view'));
    assert.equal(storage.value, 'table');
});
