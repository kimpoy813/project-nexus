const { test } = require('node:test');
const assert = require('node:assert/strict');
const { readFileSync } = require('node:fs');
const { runInNewContext } = require('node:vm');

// The helper is inline in the template on purpose: a page keeps its toasts
// even when the static bundle behind them is missing. This lifts that one
// <script> out of templates/partials/_toaster.html and runs it against a DOM
// small enough to reason about, so the waiting/fallback rules are covered
// without a browser.
const template = readFileSync('templates/partials/_toaster.html', 'utf8');
const helper = template.match(/<script>\n([\s\S]*?)<\/script>/)[1];
assert.ok(helper.includes('window.nexusToast'), 'the template no longer defines window.nexusToast');

function element(tag) {
    const el = {
        tagName: String(tag).toUpperCase(),
        children: [],
        attributes: {},
        className: '',
        textContent: '',
        parentNode: null,
        classList: {
            _names: new Set(),
            add(...names) { names.forEach((n) => this._names.add(n)); },
            remove(...names) { names.forEach((n) => this._names.delete(n)); },
            contains(name) { return this._names.has(name); },
        },
        appendChild(child) {
            child.parentNode = el;
            el.children.push(child);
            return child;
        },
        remove() {
            if (!el.parentNode) return;
            el.parentNode.children = el.parentNode.children.filter((c) => c !== el);
            el.parentNode = null;
        },
        setAttribute(name, value) { el.attributes[name] = String(value); },
        getAttribute(name) { return name in el.attributes ? el.attributes[name] : null; },
        addEventListener() {},
        querySelectorAll() { return []; },
    };
    return el;
}

/** A document with the pieces the helper asks for, and nothing else. */
function page({ moduleLoaded = true, messages = [] } = {}) {
    const byId = {};
    const listeners = {};
    const timers = [];
    const moduleScript = { tagName: 'SCRIPT', getAttribute: () => 'goey/toaster.js' };

    const messageList = element('div');
    messages.forEach(({ message, tags }) => {
        const node = element('div');
        node.setAttribute('data-message', message);
        node.setAttribute('data-tags', tags);
        messageList.appendChild(node);
    });
    messageList.querySelectorAll = () => messageList.children;
    // A detached node is gone from a real document too; getElementById must
    // stop finding it once the helper has consumed it.
    messageList.remove = () => { delete byId['messages-data']; };

    const container = element('div');
    byId['toast-container'] = container;
    if (messages.length) byId['messages-data'] = messageList;

    const document = {
        readyState: 'loading',
        createElement: element,
        getElementById: (id) => byId[id] || null,
        querySelector: (selector) => (selector.includes('toaster.js') && moduleLoaded ? moduleScript : null),
        addEventListener: (type, handler) => { (listeners[type] = listeners[type] || []).push(handler); },
        fire: (type) => (listeners[type] || []).forEach((handler) => handler({ type })),
    };

    const window = {
        setTimeout: (fn) => timers.push(fn),
        clearTimeout: () => {},
        document,
    };

    return { window, document, container, messageList, timers };
}

function load(options) {
    const dom = page(options);
    runInNewContext(helper, { window: dom.window, document: dom.document });
    return dom;
}

/** A goeyToast stand-in that records (type, message) pairs. */
function recordingToaster() {
    const calls = [];
    const toaster = {};
    for (const type of ['success', 'error', 'warning', 'info']) {
        toaster[type] = (message) => calls.push([type, message]);
    }
    toaster.calls = calls;
    return toaster;
}

function texts(container) {
    return container.children.map((child) => child.children[0].children[0].textContent);
}

test('a toast waits for the module instead of decaying to the plain one', () => {
    const dom = load();

    dom.window.nexusToast('Step order saved.', 'success');
    assert.equal(dom.container.children.length, 0, 'nothing is shown before the module runs');

    const toaster = recordingToaster();
    dom.window.goeyToast = toaster;
    dom.document.fire('DOMContentLoaded');

    assert.deepEqual(toaster.calls, [['success', 'Step order saved.']]);
    assert.equal(dom.container.children.length, 0, 'the fallback never fired');
});

test('without the module the page shows the plain toast instead of losing it', () => {
    const dom = load({ moduleLoaded: false });

    dom.window.nexusToast('Draft deleted.', 'success');

    assert.equal(dom.container.children.length, 1);
    assert.deepEqual(texts(dom.container), ['Draft deleted.']);
    assert.ok(dom.container.children[0].className.includes('bg-green-700'));
});

test("Django's messages become toasts of the matching type", () => {
    const dom = load({
        messages: [
            { message: 'Login successful!', tags: 'success' },
            { message: 'You were logged out due to inactivity.', tags: 'warning' },
            { message: 'Draft not found.', tags: 'error' },
            { message: 'Session note.', tags: 'info' },
        ],
    });
    const toaster = recordingToaster();
    dom.window.goeyToast = toaster;
    dom.document.fire('DOMContentLoaded');

    assert.deepEqual(toaster.calls, [
        ['success', 'Login successful!'],
        ['warning', 'You were logged out due to inactivity.'],
        ['error', 'Draft not found.'],
        ['info', 'Session note.'],
    ]);
    assert.equal(dom.document.getElementById('messages-data'), null, 'the data node is consumed once');
});

test('an unknown type is delivered as info, and empty messages are ignored', () => {
    const dom = load({ moduleLoaded: false });
    const toaster = recordingToaster();
    dom.window.goeyToast = toaster;

    dom.window.nexusToast('Something happened', 'bogus');
    dom.window.nexusToast('');
    dom.window.nexusToast(null);

    assert.deepEqual(toaster.calls, [['info', 'Something happened']]);
});

test('the plain toast dismisses itself on the shared timers', () => {
    const dom = load({ moduleLoaded: false });

    dom.window.nexusToast('Queued while the module is absent', 'warning');

    const toast = dom.container.children[0];
    assert.ok(toast.className.includes('bg-yellow-600'));
    assert.equal(toast.getAttribute('role'), 'alert');
    assert.ok(dom.timers.length >= 2, 'both reveal and dismiss are scheduled');

    dom.timers[0]();
    assert.ok(!toast.classList.contains('opacity-0'), 'revealed');
});
