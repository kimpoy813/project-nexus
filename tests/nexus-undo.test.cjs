const { test } = require('node:test');
const assert = require('node:assert/strict');
const { readFileSync } = require('node:fs');
const { runInNewContext } = require('node:vm');

const script = readFileSync('static/js/nexus-undo.js', 'utf8');

/* Same minimal-DOM approach as the other component tests: just enough to run
   the module, with a clock and a timer list so the countdown can be driven
   without waiting fifteen minutes for a real expiry. */
class Element {
    constructor(tagName) {
        this.tagName = tagName.toLowerCase();
        this.nodeType = 1;
        this.attributes = {};
        this.children = [];
        this.listeners = {};
        this.textContent = '';
        this.parentNode = null;
    }

    setAttribute(name, value) { this.attributes[name] = String(value); }
    getAttribute(name) { return Object.prototype.hasOwnProperty.call(this.attributes, name) ? this.attributes[name] : null; }
    hasAttribute(name) { return Object.prototype.hasOwnProperty.call(this.attributes, name); }

    appendChild(child) {
        child.parentNode = this;
        this.children.push(child);
        return child;
    }

    removeChild(child) {
        const index = this.children.indexOf(child);
        if (index !== -1) this.children.splice(index, 1);
        child.parentNode = null;
        return child;
    }

    addEventListener(type, handler) {
        (this.listeners[type] = this.listeners[type] || []).push(handler);
    }

    dispatch(type, event = {}) {
        const payload = Object.assign({ key: '', preventDefault() {} }, event);
        (this.listeners[type] || []).forEach(handler => handler(payload));
        return payload;
    }

    querySelector(selector) {
        const match = this.querySelectorAll(selector);
        return match.length ? match[0] : null;
    }

    querySelectorAll(selector) {
        if (selector === '[data-nx-undo]') {
            return this.children.filter(child => child.hasAttribute('data-nx-undo'));
        }
        if (selector === '[data-nx-undo-remaining]') {
            return this.descendants().filter(child => child.hasAttribute('data-nx-undo-remaining'));
        }
        return [];
    }

    descendants() {
        return this.children.reduce(
            (all, child) => all.concat([child], child.descendants()),
            []
        );
    }
}

function bar(seconds, token = 'abc') {
    const item = new Element('div');
    item.setAttribute('data-nx-undo', '');
    item.setAttribute('data-nx-undo-seconds', String(seconds));
    item.setAttribute('data-nx-undo-token', token);

    const text = new Element('span');
    const remaining = new Element('span');
    remaining.setAttribute('data-nx-undo-remaining', '');
    text.appendChild(remaining);
    item.appendChild(text);
    return item;
}

function setup(items, { now = 0 } = {}) {
    const document = new Element('body');
    items.forEach(item => document.appendChild(item));

    const clock = { now };
    const intervals = [];

    const window = {
        setInterval(callback, delay) {
            intervals.push({ callback, delay });
            return intervals.length;
        },
        clearInterval(id) { intervals[id - 1] = null; },
    };
    const Date = { now: () => clock.now };

    runInNewContext(script, { window, document, Date });

    const tick = () => intervals.filter(Boolean).forEach(timer => timer.callback());
    return { document, clock, tick, intervals };
}

test('the countdown starts from the seconds the server sent', () => {
    const item = bar(900);
    setup([item]);

    assert.equal(item.querySelector('[data-nx-undo-remaining]').textContent, '900');
});

test('the countdown follows the clock', () => {
    const item = bar(900);
    const { clock, tick } = setup([item]);

    clock.now += 30_000;
    tick();
    assert.equal(item.querySelector('[data-nx-undo-remaining]').textContent, '870');
});

test('the bar removes itself when the undo window closes', () => {
    const item = bar(5);
    const { clock, tick, document } = setup([item]);

    clock.now += 5_000;
    tick();

    assert.equal(document.querySelectorAll('[data-nx-undo]').length, 0);
    assert.equal(item.parentNode, null, 'its forms go with it, so a stale undo cannot be submitted');
});

test('a bar with no deadline is left alone instead of hiding immediately', () => {
    const item = bar('not-a-number');
    const { tick, document } = setup([item]);

    tick();
    assert.equal(document.querySelectorAll('[data-nx-undo]').length, 1);
});

test('Escape closes the newest bar', () => {
    const first = bar(900, 'one');
    const second = bar(900, 'two');
    const { document } = setup([first, second]);

    document.dispatch('keydown', { key: 'Escape' });

    assert.equal(document.querySelectorAll('[data-nx-undo]').length, 1);
    assert.equal(document.querySelectorAll('[data-nx-undo]')[0], first, 'the older bar stays');
});

test('Escape on a page with nothing to undo does nothing', () => {
    const { document } = setup([]);
    assert.doesNotThrow(() => document.dispatch('keydown', { key: 'Escape' }));
});

test('other keys are ignored', () => {
    const item = bar(900);
    const { document } = setup([item]);

    document.dispatch('keydown', { key: 'a' });
    assert.equal(document.querySelectorAll('[data-nx-undo]').length, 1);
});

test('the module exposes one entry point so a new bar can be enhanced later', () => {
    const window = { setInterval() {}, clearInterval() {} };
    runInNewContext(script, { window, document: new Element('body'), Date: { now: () => 0 } });
    assert.equal(typeof window.nexusUndo.enhance, 'function');
});
