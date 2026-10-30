const { test } = require('node:test');
const assert = require('node:assert/strict');
const { readFileSync } = require('node:fs');
const { runInNewContext } = require('node:vm');

const script = readFileSync('static/js/nexus-select.js', 'utf8');

class Element {
    constructor(tagName, { connected = true } = {}) {
        this.nodeType = 1;
        this.tagName = tagName.toLowerCase();
        this.isConnected = connected;
        this.children = [];
        this.parentNode = null;
        this.className = '';
    }

    get firstChild() { return this.children[0] || null; }

    matches() {
        return this.tagName === 'select' && !this.multiple && !this.size && !this.inEditor && !this.flatpickr;
    }

    appendChild(child) {
        child.parentNode = this;
        this.children.push(child);
        return child;
    }

    insertBefore(child, reference) {
        child.parentNode = this;
        const index = reference ? this.children.indexOf(reference) : 0;
        this.children.splice(index < 0 ? 0 : index, 0, child);
        return child;
    }

    querySelector(selector) {
        if (selector === ':scope > button') {
            return this.children.find(child => child.tagName === 'button') || null;
        }
        return null;
    }

    querySelectorAll() {
        const found = [];
        for (const child of this.children) {
            if (child.matches()) found.push(child);
            found.push(...child.querySelectorAll());
        }
        return found;
    }
}

function setup({ supported = true, selects = [] } = {}) {
    const document = {
        body: new Element('body'),
        createElement: tag => new Element(tag),
        querySelectorAll() { return selects.filter(select => select.matches()); },
        addEventListener() { throw new Error('body-ready script should not need a DOMContentLoaded listener'); },
    };
    let observer = null;
    class MutationObserver {
        constructor(callback) { this.callback = callback; observer = this; }
        observe(target, options) { this.target = target; this.options = options; }
    }
    const window = {
        CSS: { supports: (property, value) => supported && property === 'appearance' && value === 'base-select' },
        MutationObserver,
    };
    runInNewContext(script, { window, document });
    return { document, window, selects, observer: () => observer };
}

function nativeButton(select) {
    return select.children.find(child => child.tagName === 'button');
}

test('adds one browser-native selectedcontent slot without changing the select', () => {
    const option = new Element('option');
    const select = new Element('select');
    select.appendChild(option);
    const context = setup({ selects: [select] });

    const button = nativeButton(select);
    assert.ok(button, 'the native button leads the select');
    assert.equal(select.children[0], button);
    assert.equal(select.children[1], option, 'existing options stay in place');
    assert.equal(button.type, 'button');
    assert.equal(button.className, 'nx-select__button');
    assert.equal(button.children.length, 1);
    assert.equal(button.children[0].tagName, 'selectedcontent');
    assert.equal(select.style, undefined, 'the real control is not hidden or restyled inline');

    context.observer().callback([{ addedNodes: [select] }]);
    assert.equal(select.children.filter(child => child.tagName === 'button').length, 1, 'repeated scans do not duplicate the slot');
});

test('enhances selects inside dynamically added repeaters and wizard subtrees', () => {
    const context = setup();
    const row = new Element('div');
    const select = new Element('select');
    row.appendChild(select);

    context.observer().callback([{ addedNodes: [row] }]);
    assert.ok(nativeButton(select));

    // replaceChildren() in the AJAX cascades removes the slot with the stale
    // options. The observer restores the native slot, not a copied value/menu.
    const option = new Element('option');
    select.children = [option];
    context.observer().callback([{ target: select, addedNodes: [option] }]);
    assert.ok(nativeButton(select));
    assert.equal(select.children.filter(child => child.tagName === 'button').length, 1);
    assert.equal(select.children.at(-1), option);
});

test('respects existing native markup and skips listboxes, editors and detached controls', () => {
    const existing = new Element('select');
    const button = new Element('button');
    existing.appendChild(button);
    const multiple = new Element('select'); multiple.multiple = true;
    const listbox = new Element('select'); listbox.size = 4;
    const editor = new Element('select'); editor.inEditor = true;
    const flatpickr = new Element('select'); flatpickr.flatpickr = true;
    const detached = new Element('select', { connected: false });

    setup({ selects: [existing, multiple, listbox, editor, flatpickr, detached] });

    assert.equal(existing.children.filter(child => child.tagName === 'button').length, 1);
    for (const select of [multiple, listbox, editor, flatpickr, detached]) {
        assert.equal(nativeButton(select), undefined);
    }
});

test('unsupported browsers keep the untouched native select and no observer', () => {
    const select = new Element('select');
    const context = setup({ supported: false, selects: [select] });
    assert.equal(nativeButton(select), undefined);
    assert.equal(context.observer(), null);
});

test('preserves selectedIndex when inserting the native button ahead of dynamic options', () => {
    const select = new Element('select');
    const optA = new Element('option');
    const optB = new Element('option');
    select.appendChild(optA);
    select.appendChild(optB);
    let currentIndex = 0;
    Object.defineProperty(select, 'selectedIndex', {
        get() { return currentIndex; },
        set(val) { currentIndex = val; },
    });
    const origInsertBefore = select.insertBefore.bind(select);
    select.insertBefore = function (child, reference) {
        const res = origInsertBefore(child, reference);
        if (child.tagName === 'button') currentIndex = -1;
        return res;
    };

    setup({ selects: [select] });
    assert.ok(nativeButton(select));
    assert.equal(select.selectedIndex, 0);
});
