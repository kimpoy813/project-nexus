const { test } = require('node:test');
const assert = require('node:assert/strict');
const { readFileSync } = require('node:fs');
const { runInNewContext } = require('node:vm');

const script = readFileSync('static/js/nexus-select.js', 'utf8');

/* ── Minimal standalone setup (outside .nexus-shell, e.g. Django /admin/) ── */
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
        return this.tagName === 'select' && !this.multiple && !this.size && !this.inEditor && !this.flatpickr && !this.legacyNative;
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
    const legacyNative = new Element('select'); legacyNative.legacyNative = true;
    const detached = new Element('select', { connected: false });

    setup({ selects: [existing, multiple, listbox, editor, flatpickr, legacyNative, detached] });

    assert.equal(existing.children.filter(child => child.tagName === 'button').length, 1);
    for (const select of [multiple, listbox, editor, flatpickr, legacyNative, detached]) {
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

/* ── Rich .nexus-shell setup for system-wide custom popover dropdown tests ── */
function splitDescendantTokens(selector) {
    const tokens = [];
    let current = '';
    let bracketDepth = 0;
    let parenDepth = 0;
    let quote = '';
    for (const ch of selector.trim()) {
        if (quote) {
            current += ch;
            if (ch === quote) quote = '';
            continue;
        }
        if (ch === '"' || ch === "'") {
            quote = ch;
            current += ch;
            continue;
        }
        if (ch === '[') bracketDepth += 1;
        else if (ch === ']') bracketDepth = Math.max(0, bracketDepth - 1);
        else if (ch === '(') parenDepth += 1;
        else if (ch === ')') parenDepth = Math.max(0, parenDepth - 1);

        if (/\s/.test(ch) && bracketDepth === 0 && parenDepth === 0) {
            if (current) {
                tokens.push(current);
                current = '';
            }
        } else {
            current += ch;
        }
    }
    if (current) tokens.push(current);
    return tokens;
}

function matchesSimple(el, token) {
    if (!el || el.nodeType !== 1) return false;
    let rest = token;

    while (rest.includes(':not(')) {
        const start = rest.indexOf(':not(');
        let depth = 0;
        let end = -1;
        for (let i = start + 5; i < rest.length; i += 1) {
            if (rest[i] === '(') depth += 1;
            else if (rest[i] === ')') {
                if (depth === 0) { end = i; break; }
                depth -= 1;
            }
        }
        if (end < 0) break;
        const inner = rest.slice(start + 5, end);
        if (matchesSelector(el, inner)) return false;
        rest = rest.slice(0, start) + rest.slice(end + 1);
    }

    if (rest.includes(':disabled')) {
        if (!el.disabled) return false;
        rest = rest.replace(/:disabled/g, '');
    }

    const attrRe = /\[([^\]=]+)(?:="([^"]*)")?\]/g;
    let match;
    while ((match = attrRe.exec(rest)) !== null) {
        const [, attr, val] = match;
        if (val === undefined) {
            if (!el.hasAttribute(attr)) return false;
        } else if (el.getAttribute(attr) !== val) {
            return false;
        }
    }
    rest = rest.replace(attrRe, '');

    const classTokens = [];
    rest = rest.replace(/\.([A-Za-z0-9_-]+)/g, (_, cls) => {
        classTokens.push(cls);
        return '';
    });
    for (const cls of classTokens) {
        if (!el.classList.contains(cls)) return false;
    }

    const idMatch = rest.match(/#([A-Za-z0-9_-]+)/);
    if (idMatch) {
        if (el.id !== idMatch[1]) return false;
        rest = rest.replace(/#[A-Za-z0-9_-]+/, '');
    }

    const tag = rest.trim().toLowerCase();
    if (tag && tag !== '*' && el.tagName !== tag) return false;
    return true;
}

function matchesSelector(el, selector) {
    return selector.split(',').some((branch) => {
        const parts = splitDescendantTokens(branch);
        if (!parts.length) return false;
        if (!matchesSimple(el, parts[parts.length - 1])) return false;
        let cur = el.parentNode;
        for (let i = parts.length - 2; i >= 0; i -= 1) {
            while (cur && !matchesSimple(cur, parts[i])) {
                cur = cur.parentNode;
            }
            if (!cur) return false;
            cur = cur.parentNode;
        }
        return true;
    });
}

function setupShellEnv({ supported = false, viewportH = 800, viewportW = 1280 } = {}) {
    let activeElement = null;
    const observers = [];

    class ShellNode {
        constructor(tagName, ownerDoc) {
            this.nodeType = 1;
            this.tagName = String(tagName).toLowerCase();
            this.ownerDocument = ownerDoc;
            this.parentNode = null;
            this.children = [];
            this.attributes = {};
            this.listeners = {};
            this.style = {};
            this.hidden = false;
            this.disabled = false;
            this._className = '';
            this._id = '';
            this._text = '';
            this._rect = { top: 120, bottom: 162, left: 40, right: 280, width: 240, height: 42 };
            this._value = '';
            this._selectedIndex = 0;

            const self = this;
            this.classList = {
                add(...names) {
                    const set = new Set(self._className.split(/\s+/).filter(Boolean));
                    names.forEach(n => set.add(n));
                    self._className = [...set].join(' ');
                },
                remove(...names) {
                    const set = new Set(self._className.split(/\s+/).filter(Boolean));
                    names.forEach(n => set.delete(n));
                    self._className = [...set].join(' ');
                },
                toggle(name, force) {
                    const has = this.contains(name);
                    const next = force === undefined ? !has : Boolean(force);
                    if (next) this.add(name);
                    else this.remove(name);
                    return next;
                },
                contains(name) {
                    return self._className.split(/\s+/).filter(Boolean).includes(name);
                },
            };
        }

        get isConnected() {
            let cur = this;
            while (cur) {
                if (cur === this.ownerDocument.body) return true;
                cur = cur.parentNode;
            }
            return false;
        }

        get parentElement() { return this.parentNode; }
        get firstChild() { return this.children[0] || null; }
        get nextSibling() {
            if (!this.parentNode) return null;
            const i = this.parentNode.children.indexOf(this);
            return i >= 0 ? (this.parentNode.children[i + 1] || null) : null;
        }

        get id() { return this._id; }
        set id(v) { this._id = String(v); this.attributes.id = String(v); }

        get className() { return this._className; }
        set className(v) { this._className = String(v || ''); }

        get textContent() {
            if (this.children.length) return this.children.map(c => c.textContent).join('');
            return this._text;
        }
        set textContent(v) {
            this.children = [];
            this._text = String(v ?? '');
        }

        get options() {
            if (this.tagName !== 'select') return [];
            const opts = [];
            const collect = (node) => {
                for (const ch of node.children) {
                    if (ch.tagName === 'option') opts.push(ch);
                    else if (ch.tagName === 'optgroup') collect(ch);
                }
            };
            collect(this);
            return opts;
        }

        get selectedIndex() {
            if (this.tagName !== 'select') return -1;
            const opts = this.options;
            const idx = opts.findIndex(o => o.selected);
            return idx >= 0 ? idx : (opts.length ? 0 : -1);
        }
        set selectedIndex(idx) {
            const opts = this.options;
            opts.forEach((o, i) => { o.selected = i === idx; });
        }

        get value() {
            if (this.tagName === 'option') {
                return Object.prototype.hasOwnProperty.call(this.attributes, 'value')
                    ? this.attributes.value
                    : this.textContent.trim();
            }
            if (this.tagName === 'select') {
                const opts = this.options;
                const sel = opts[this.selectedIndex];
                return sel ? sel.value : '';
            }
            return this._value;
        }
        set value(val) {
            const s = String(val ?? '');
            if (this.tagName === 'option') {
                this.attributes.value = s;
                return;
            }
            if (this.tagName === 'select') {
                const opts = this.options;
                const match = opts.find(o => o.value === s);
                if (match) opts.forEach(o => { o.selected = o === match; });
                return;
            }
            this._value = s;
        }

        setAttribute(name, val) {
            const s = String(val);
            this.attributes[name] = s;
            if (name === 'id') this._id = s;
            if (name === 'class') this._className = s;
            if (name === 'disabled') this.disabled = true;
            if (name === 'hidden') this.hidden = true;
            notifyMutation(this, { type: 'attributes', attributeName: name, target: this });
        }
        getAttribute(name) {
            if (name === 'class') return this._className;
            if (name === 'id') return this._id || null;
            return Object.prototype.hasOwnProperty.call(this.attributes, name) ? this.attributes[name] : null;
        }
        hasAttribute(name) {
            if (name === 'disabled') return this.disabled || Object.prototype.hasOwnProperty.call(this.attributes, 'disabled');
            if (name === 'hidden') return this.hidden || Object.prototype.hasOwnProperty.call(this.attributes, 'hidden');
            return Object.prototype.hasOwnProperty.call(this.attributes, name);
        }
        removeAttribute(name) {
            delete this.attributes[name];
            if (name === 'disabled') this.disabled = false;
            if (name === 'hidden') this.hidden = false;
            notifyMutation(this, { type: 'attributes', attributeName: name, target: this });
        }

        appendChild(child) {
            if (child.parentNode) child.parentNode.removeChild(child);
            child.parentNode = this;
            this.children.push(child);
            notifyMutation(this, { type: 'childList', target: this, addedNodes: [child], removedNodes: [] });
            return child;
        }

        insertBefore(child, ref) {
            if (child.parentNode) child.parentNode.removeChild(child);
            child.parentNode = this;
            if (!ref) {
                this.children.push(child);
            } else {
                const idx = this.children.indexOf(ref);
                this.children.splice(idx < 0 ? this.children.length : idx, 0, child);
            }
            notifyMutation(this, { type: 'childList', target: this, addedNodes: [child], removedNodes: [] });
            return child;
        }

        removeChild(child) {
            const idx = this.children.indexOf(child);
            if (idx >= 0) {
                this.children.splice(idx, 1);
                child.parentNode = null;
                notifyMutation(this, { type: 'childList', target: this, addedNodes: [], removedNodes: [child] });
            }
            return child;
        }

        replaceChildren(...nodes) {
            const removed = [...this.children];
            removed.forEach(c => { c.parentNode = null; });
            this.children = [];
            nodes.forEach(n => {
                n.parentNode = this;
                this.children.push(n);
            });
            notifyMutation(this, { type: 'childList', target: this, addedNodes: nodes, removedNodes: removed });
        }

        remove() {
            if (this.parentNode) this.parentNode.removeChild(this);
        }

        contains(other) {
            let cur = other;
            while (cur) {
                if (cur === this) return true;
                cur = cur.parentNode;
            }
            return false;
        }

        matches(selector) {
            return matchesSelector(this, selector);
        }

        closest(selector) {
            let cur = this;
            while (cur && cur.nodeType === 1) {
                if (cur.matches(selector)) return cur;
                cur = cur.parentNode;
            }
            return null;
        }

        querySelectorAll(selector) {
            const out = [];
            const walk = (node) => {
                for (const ch of node.children) {
                    if (ch.matches(selector)) out.push(ch);
                    walk(ch);
                }
            };
            walk(this);
            return out;
        }

        querySelector(selector) {
            if (selector === ':scope > button') {
                return this.children.find(c => c.tagName === 'button') || null;
            }
            return this.querySelectorAll(selector)[0] || null;
        }

        addEventListener(type, fn) {
            (this.listeners[type] = this.listeners[type] || []).push(fn);
        }

        dispatchEvent(event) {
            event.target = event.target || this;
            let cur = this;
            while (cur) {
                for (const fn of cur.listeners[event.type] || []) {
                    fn.call(cur, event);
                }
                if (cur === this && typeof cur['on' + event.type] === 'function') {
                    cur['on' + event.type].call(cur, event);
                }
                if (!event.bubbles || event._stopped) break;
                cur = cur.parentNode;
            }
            if (!event._stopped && event.bubbles && this.ownerDocument) {
                for (const fn of this.ownerDocument.listeners[event.type] || []) {
                    fn.call(this.ownerDocument, event);
                }
            }
            return !event.defaultPrevented;
        }

        focus() {
            activeElement = this;
            this.dispatchEvent({ type: 'focus', bubbles: false, preventDefault() {} });
        }
        scrollIntoView() {}
        getBoundingClientRect() { return this._rect; }
    }

    let suppressingNotify = false;
    function notifyMutation(target, record) {
        if (suppressingNotify) return;
        for (const obs of observers) {
            if (!obs.active || !obs.target) continue;
            const applies = obs.target === target || (obs.options?.subtree && obs.target.contains(target));
            if (!applies) continue;
            if (record.type === 'attributes') {
                if (!obs.options?.attributes) continue;
                if (obs.options.attributeFilter && !obs.options.attributeFilter.includes(record.attributeName)) continue;
            } else if (record.type === 'childList' && !obs.options?.childList) {
                continue;
            }
            obs.pending.push(record);
        }
    }

    function flushMutations() {
        let guard = 0;
        while (guard < 10 && observers.some(o => o.active && o.pending.length)) {
            guard += 1;
            for (const obs of [...observers]) {
                if (!obs.active || !obs.pending.length) continue;
                const batch = obs.pending.splice(0, obs.pending.length);
                obs.callback(batch);
            }
        }
    }

    const doc = {
        listeners: {},
        body: null,
        get activeElement() { return activeElement; },
        createElement: tag => new ShellNode(tag, doc),
        createElementNS: (_ns, tag) => new ShellNode(tag, doc),
        addEventListener(type, fn) {
            (this.listeners[type] = this.listeners[type] || []).push(fn);
        },
        querySelector(sel) { return doc.body.querySelector(sel); },
        querySelectorAll(sel) { return doc.body.querySelectorAll(sel); },
        getElementById(id) {
            return doc.body.querySelectorAll('*').find(el => el.id === id) || null;
        },
    };
    doc.body = new ShellNode('body', doc);
    doc.body.className = 'nexus-shell';

    class MutationObserver {
        constructor(callback) {
            this.callback = callback;
            this.pending = [];
            this.active = false;
            observers.push(this);
        }
        observe(target, options) {
            this.target = target;
            this.options = options;
            this.active = true;
        }
        disconnect() {
            this.active = false;
            this.pending = [];
        }
    }

    class CustomEventSim {
        constructor(type, init = {}) {
            this.type = type;
            this.bubbles = Boolean(init.bubbles);
            this.defaultPrevented = false;
            this._stopped = false;
        }
        preventDefault() { this.defaultPrevented = true; }
        stopPropagation() { this._stopped = true; }
    }

    const winListeners = {};
    const win = {
        innerHeight: viewportH,
        innerWidth: viewportW,
        Event: CustomEventSim,
        CSS: { supports: (p, v) => supported && p === 'appearance' && v === 'base-select' },
        MutationObserver,
        HTMLSelectElement: { prototype: Object.getOwnPropertyDescriptor(ShellNode.prototype, 'value') ? ShellNode.prototype : null },
        addEventListener(type, fn) {
            (winListeners[type] = winListeners[type] || []).push(fn);
        },
        dispatchWindowEvent(type, event = {}) {
            for (const fn of winListeners[type] || []) {
                fn(event);
            }
        },
        setTimeout: fn => fn(),
        requestAnimationFrame: fn => { fn(); return 1; },
    };

    function createSelect({ id = '', name = '', className = 'w-full', style = '', options = [] } = {}) {
        suppressingNotify = true;
        try {
            const sel = doc.createElement('select');
            if (id) sel.id = id;
            if (name) sel.setAttribute('name', name);
            sel.className = className;
            if (style) sel.setAttribute('style', style);
            for (const o of options) {
                const opt = doc.createElement('option');
                opt.value = o.value;
                opt.textContent = o.label;
                if (o.disabled) opt.setAttribute('disabled', '');
                if (o.selected) opt.selected = true;
                sel.appendChild(opt);
            }
            if (!options.some(o => o.selected) && sel.options[0]) {
                sel.options[0].selected = true;
            }
            return sel;
        } finally {
            suppressingNotify = false;
        }
    }

    function boot() {
        runInNewContext(script, { window: win, document: doc, Event: CustomEventSim, setTimeout: win.setTimeout });
        flushMutations();
    }

    function click(node) {
        const ev = new CustomEventSim('click', { bubbles: true });
        ev.target = node;
        node.dispatchEvent(ev);
        flushMutations();
    }

    function keydown(node, key) {
        const ev = new CustomEventSim('keydown', { bubbles: true });
        ev.key = key;
        ev.target = node;
        node.dispatchEvent(ev);
        flushMutations();
        return ev;
    }

    return { doc, win, createSelect, boot, click, keydown, flushMutations };
}

test('.nexus-shell upgrades selects into custom popovers even when base-select is unsupported', () => {
    const env = setupShellEnv({ supported: false });
    const field = env.doc.createElement('div');
    const label = env.doc.createElement('label');
    label.setAttribute('for', 'id_campus');
    label.textContent = 'Campus';
    const select = env.createSelect({
        id: 'id_campus',
        name: 'campus',
        className: 'w-full rounded-xl',
        options: [
            { value: '', label: 'Select campus' },
            { value: 'Main', label: 'Main Campus' },
            { value: 'Tagudin', label: 'Tagudin Campus' },
        ],
    });
    field.appendChild(label);
    field.appendChild(select);
    env.doc.body.appendChild(field);
    env.boot();

    // Real <select> stays in its original parentElement so organization-fields.js
    // `department.parentElement.append(feedback)` continues to target `field`.
    assert.equal(select.parentElement, field);
    assert.ok(select.classList.contains('nx-select-native'));

    const popover = field.querySelector('[data-nx-select-popover]');
    assert.ok(popover, 'custom popover sibling is mounted');
    assert.ok(popover.classList.contains('w-full'));
    const trigger = popover.querySelector('[data-nx-select-trigger]');
    const labelSpan = popover.querySelector('[data-nx-select-label]');
    assert.equal(labelSpan.textContent, 'Select campus');
    assert.ok(labelSpan.classList.contains('is-placeholder'), 'Select... prompt uses placeholder tone');
    assert.equal(trigger.getAttribute('aria-labelledby'), label.id);
});

test('filter selects keep crisp non-placeholder labels and mirror compact/width utilities', () => {
    const env = setupShellEnv();
    const toolbar = env.doc.createElement('div');
    const roleFilter = env.createSelect({
        id: 'roleFilter',
        className: 'adm-input w-full sm:w-44',
        options: [
            { value: '', label: 'All roles' },
            { value: 'FACULTY', label: 'Faculty' },
        ],
    });
    const inlineYear = env.createSelect({
        id: 'target-year',
        className: 'dir-input',
        style: 'width:auto; min-width:110px;',
        options: [
            { value: '2026', label: '2026', selected: true },
            { value: '2025', label: '2025' },
        ],
    });
    toolbar.appendChild(roleFilter);
    toolbar.appendChild(inlineYear);
    env.doc.body.appendChild(toolbar);
    env.boot();

    const rolePopover = roleFilter.nextSibling;
    assert.ok(rolePopover.classList.contains('w-full'));
    assert.ok(rolePopover.classList.contains('sm:w-44'));
    const roleLabel = rolePopover.querySelector('[data-nx-select-label]');
    assert.equal(roleLabel.textContent, 'All roles');
    assert.ok(!roleLabel.classList.contains('is-placeholder'), '"All roles" is an active filter, not a muted placeholder');

    const yearPopover = inlineYear.nextSibling;
    assert.ok(yearPopover.classList.contains('nx-select-popover--auto'));
    assert.ok(yearPopover.classList.contains('nx-select-popover--compact'));
    assert.equal(yearPopover.style.minWidth, '110px');
});

test('opening portals menu to body to avoid overflow-hidden clipping and selecting fires input/change + onchange', () => {
    const env = setupShellEnv({ viewportH: 760, viewportW: 1200 });
    const card = env.doc.createElement('div');
    card.className = 'overflow-hidden nx-panel';
    let submitted = 0;
    const form = env.doc.createElement('form');
    form.submit = () => { submitted += 1; };
    const select = env.createSelect({
        id: 'role_row_1',
        name: 'role',
        className: 'adm-input adm-input--sm',
        options: [
            { value: 'FACULTY', label: 'Faculty', selected: true },
            { value: 'EVALUATOR', label: 'Evaluator' },
            { value: 'DIRECTOR', label: 'Director' },
        ],
    });
    select.form = form;
    select.onchange = function () { this.form.submit(); };
    let changeEvents = 0;
    let inputEvents = 0;
    select.addEventListener('input', () => { inputEvents += 1; });
    select.addEventListener('change', () => { changeEvents += 1; });

    form.appendChild(select);
    card.appendChild(form);
    env.doc.body.appendChild(card);
    env.boot();

    const popover = select.nextSibling;
    assert.ok(popover.classList.contains('nx-select-popover--sm'));
    const trigger = popover.querySelector('[data-nx-select-trigger]');

    env.click(trigger);
    assert.equal(trigger.getAttribute('aria-expanded'), 'true');
    const portaledMenu = env.doc.body.children.find(ch => ch.hasAttribute('data-nx-select-menu'));
    assert.ok(portaledMenu, 'open menu portals to document.body so overflow-hidden cards never clip it');
    assert.ok(portaledMenu.classList.contains('is-portaled'));

    const directorBtn = portaledMenu.querySelectorAll('[data-nx-select-option]')[2];
    env.click(directorBtn);

    assert.equal(select.value, 'DIRECTOR');
    assert.equal(popover.querySelector('[data-nx-select-label]').textContent, 'Director');
    assert.equal(trigger.getAttribute('aria-expanded'), 'false');
    assert.equal(portaledMenu.parentNode, popover, 'closed menu returns cleanly inside its popover wrapper');
    assert.equal(inputEvents, 1);
    assert.equal(changeEvents, 1);
    assert.equal(submitted, 1, 'inline onchange="this.form.submit()" fires on custom selection');
});

test('flips menu upward when trigger sits near the bottom of the viewport', () => {
    const env = setupShellEnv({ viewportH: 500, viewportW: 1024 });
    const select = env.createSelect({
        options: [
            { value: '1', label: 'January' },
            { value: '2', label: 'February' },
            { value: '3', label: 'March' },
            { value: '4', label: 'April' },
            { value: '5', label: 'May' },
            { value: '6', label: 'June' },
        ],
    });
    env.doc.body.appendChild(select);
    env.boot();

    const popover = select.nextSibling;
    const trigger = popover.querySelector('[data-nx-select-trigger]');
    trigger._rect = { top: 430, bottom: 472, left: 60, right: 300, width: 240, height: 42 };

    env.click(trigger);
    const menu = env.doc.body.children.find(ch => ch.hasAttribute('data-nx-select-menu'));
    assert.ok(menu.classList.contains('is-flipped'));
    assert.equal(menu.style.top, 'auto');
    assert.equal(menu.style.bottom, '76px');
});

test('supports keyboard navigation, disabled placeholder skipping, Escape, and outside click', () => {
    const env = setupShellEnv();
    const outside = env.doc.createElement('div');
    const select = env.createSelect({
        id: 'field-metric',
        options: [
            { value: '', label: 'Select metric', disabled: true, selected: true },
            { value: 'PROGRAMS', label: 'Programs' },
            { value: 'PARTICIPANTS', label: 'Participants' },
            { value: 'PARTNERS', label: 'Partners' },
        ],
    });
    env.doc.body.appendChild(select);
    env.doc.body.appendChild(outside);
    env.boot();

    const popover = select.nextSibling;
    const trigger = popover.querySelector('[data-nx-select-trigger]');
    assert.equal(popover.querySelector('[data-nx-select-label]').textContent, 'Select metric');
    assert.ok(popover.querySelector('[data-nx-select-label]').classList.contains('is-placeholder'));

    // ArrowDown opens and focuses first enabled option (skipping disabled placeholder)
    env.keydown(trigger, 'ArrowDown');
    assert.equal(trigger.getAttribute('aria-expanded'), 'true');
    const menu = env.doc.body.children.find(ch => ch.hasAttribute('data-nx-select-menu'));
    const allOpts = menu.querySelectorAll('[data-nx-select-option]');
    assert.equal(allOpts[0].disabled, true);
    assert.equal(env.doc.activeElement, allOpts[1]);

    // ArrowDown moves to Participants, End jumps to Partners, Enter selects it
    env.keydown(env.doc.activeElement, 'ArrowDown');
    assert.equal(env.doc.activeElement, allOpts[2]);
    env.keydown(env.doc.activeElement, 'End');
    assert.equal(env.doc.activeElement, allOpts[3]);
    env.keydown(env.doc.activeElement, 'Enter');

    assert.equal(select.value, 'PARTNERS');
    assert.equal(popover.querySelector('[data-nx-select-label]').textContent, 'Partners');
    assert.equal(trigger.getAttribute('aria-expanded'), 'false');
    assert.equal(env.doc.activeElement, trigger);

    // Reopen and close with Escape, then reopen and close via outside click
    env.click(trigger);
    assert.equal(trigger.getAttribute('aria-expanded'), 'true');
    env.keydown(env.doc.activeElement, 'Escape');
    assert.equal(trigger.getAttribute('aria-expanded'), 'false');

    env.click(trigger);
    assert.equal(trigger.getAttribute('aria-expanded'), 'true');
    env.click(outside);
    assert.equal(trigger.getAttribute('aria-expanded'), 'false');
});

test('live-syncs AJAX cascades (replaceChildren / disabled) and programmatic .value updates', () => {
    const env = setupShellEnv();
    const select = env.createSelect({
        id: 'id_college',
        options: [{ value: '', label: 'Select College (Optional)' }],
    });
    env.doc.body.appendChild(select);
    env.boot();

    const popover = select.nextSibling;
    const trigger = popover.querySelector('[data-nx-select-trigger]');

    // Simulate organization-fields.js loading state
    select.setAttribute('disabled', '');
    env.flushMutations();
    assert.equal(trigger.disabled, true);

    // Simulate AJAX populate via replaceChildren() + value assignment
    const optPlaceholder = env.doc.createElement('option');
    optPlaceholder.value = '';
    optPlaceholder.textContent = 'Select College (Optional)';
    const optCas = env.doc.createElement('option');
    optCas.value = 'CAS';
    optCas.textContent = 'College of Arts and Sciences';
    const optCte = env.doc.createElement('option');
    optCte.value = 'CTE';
    optCte.textContent = 'College of Teacher Education';

    select.replaceChildren(optPlaceholder, optCas, optCte);
    select.removeAttribute('disabled');
    env.flushMutations();

    assert.equal(trigger.disabled, false);
    select.value = 'CTE';
    assert.equal(popover.querySelector('[data-nx-select-label]').textContent, 'College of Teacher Education');
});

test('skips inert <template> selects until cloned into the live repeater DOM and cleans up on removal', () => {
    const env = setupShellEnv();
    const tpl = env.doc.createElement('template');
    const tplSelect = env.createSelect({
        name: 'repeater_1_row___INDEX___field_2',
        options: [{ value: '', label: 'Select...' }, { value: 'A', label: 'Role A' }],
    });
    tpl.appendChild(tplSelect);
    const repeaterRows = env.doc.createElement('div');
    env.doc.body.appendChild(tpl);
    env.doc.body.appendChild(repeaterRows);
    env.boot();

    assert.equal(tpl.querySelector('[data-nx-select-popover]'), null, 'inert <template> select stays unenhanced');

    // Simulate repeater adding a cloned row
    const liveRow = env.doc.createElement('div');
    const liveSelect = env.createSelect({
        name: 'repeater_1_row_0_field_2',
        options: [{ value: '', label: 'Select...' }, { value: 'A', label: 'Role A' }],
    });
    liveRow.appendChild(liveSelect);
    repeaterRows.appendChild(liveRow);
    env.flushMutations();

    const livePopover = liveRow.querySelector('[data-nx-select-popover]');
    assert.ok(livePopover, 'cloned live repeater select is enhanced automatically');

    // Open menu, then remove row (wizard swap / unsaved repeater drop) -> no orphan menu on body
    env.click(livePopover.querySelector('[data-nx-select-trigger]'));
    assert.ok(env.doc.body.children.some(ch => ch.hasAttribute('data-nx-select-menu')));
    liveRow.remove();
    env.flushMutations();
    assert.ok(!env.doc.body.children.some(ch => ch.hasAttribute('data-nx-select-menu')), 'portaled menu is cleaned up when select disconnects');
});

test('keeps full-width component selects full-width, keeps dir-input standard height, and makes adm-input--sm compact auto-width', () => {
    const env = setupShellEnv();
    const dirSelect = env.createSelect({
        id: 'ext-filter-campus',
        className: 'dir-input w-full',
        options: [{ value: '', label: 'All Campuses' }, { value: 'Main', label: 'Main' }],
    });
    const pcSelect = env.createSelect({
        name: 'color_class',
        className: 'pc-input',
        options: [{ value: 'primary', label: 'Primary' }],
    });
    const roleSelect = env.createSelect({
        name: 'role',
        className: 'adm-input adm-input--sm',
        options: [{ value: 'FACULTY', label: 'Faculty' }, { value: 'DIRECTOR', label: 'Director' }],
    });

    env.doc.body.appendChild(dirSelect);
    env.doc.body.appendChild(pcSelect);
    env.doc.body.appendChild(roleSelect);
    env.boot();

    const dirPopover = dirSelect.nextSibling;
    const pcPopover = pcSelect.nextSibling;
    const rolePopover = roleSelect.nextSibling;

    assert.equal(dirPopover.classList.contains('nx-select-popover--auto'), false, 'dir-input w-full stays full-width');
    assert.equal(dirPopover.classList.contains('nx-select-popover--compact'), false, 'dir-input matches standard 44px filter inputs');

    assert.equal(pcPopover.classList.contains('nx-select-popover--auto'), false, 'pc-input stays full-width');
    assert.equal(pcPopover.classList.contains('nx-select-popover--compact'), true, 'pc-input uses compact 36px control height');

    assert.equal(rolePopover.classList.contains('nx-select-popover--auto'), true, 'adm-input--sm in table cells uses auto width');
    assert.equal(rolePopover.classList.contains('nx-select-popover--sm'), true, 'adm-input--sm gets compact role sizing');
});

test('toggles via associated <label> and dismisses portaled menu when trigger scrolls behind fixed .nexus-navbar', () => {
    const env = setupShellEnv({ viewportH: 640 });
    const nav = env.doc.createElement('nav');
    nav.className = 'nexus-navbar';
    nav._rect = { top: 0, bottom: 76, left: 0, right: 1280, width: 1280, height: 76 };
    env.doc.body.appendChild(nav);

    const label = env.doc.createElement('label');
    label.setAttribute('for', 'id_campus');
    label.textContent = 'Campus';
    const select = env.createSelect({
        id: 'id_campus',
        className: 'w-full',
        options: [{ value: '', label: 'Select Campus' }, { value: 'Tagudin', label: 'Tagudin' }],
    });
    env.doc.body.appendChild(label);
    env.doc.body.appendChild(select);
    env.boot();

    const popover = select.nextSibling;
    const trigger = popover.querySelector('[data-nx-select-trigger]');
    trigger._rect = { top: 140, bottom: 184, left: 40, right: 320, width: 280, height: 44 };

    // Clicking the label opens and closes the custom popover cleanly
    env.click(label);
    assert.equal(trigger.getAttribute('aria-expanded'), 'true');
    env.click(label);
    assert.equal(trigger.getAttribute('aria-expanded'), 'false');

    // Reopen, then scroll trigger underneath fixed .nexus-navbar (bottom <= 76)
    env.click(trigger);
    assert.equal(trigger.getAttribute('aria-expanded'), 'true');
    trigger._rect = { top: 24, bottom: 68, left: 40, right: 320, width: 280, height: 44 };
    env.win.dispatchWindowEvent('scroll', { target: env.doc });
    assert.equal(trigger.getAttribute('aria-expanded'), 'false', 'closes cleanly once scrolled behind fixed navbar');
});

