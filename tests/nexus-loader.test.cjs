const { test } = require('node:test');
const assert = require('node:assert/strict');
const { readFileSync } = require('node:fs');
const { runInNewContext } = require('node:vm');

// The controller is a plain <script> in base.html, so it is loaded here into a
// DOM small enough to reason about. Timers are collected rather than run, which
// is what makes the waiting rules testable: the 12-second offer and the
// 90-second backstop fire on demand instead of in real time.
const script = readFileSync('static/js/nexus-loader.js', 'utf8');

function element(tag, id) {
    const el = {
        tagName: String(tag).toUpperCase(),
        id: id || '',
        hidden: false,
        attributes: {},
        className: '',
        classList: {
            _names: new Set(),
            add(...names) { names.forEach((n) => this._names.add(n)); },
            remove(...names) { names.forEach((n) => this._names.delete(n)); },
            contains(name) { return this._names.has(name); },
        },
        setAttribute(name, value) { this.attributes[name] = String(value); },
        getAttribute(name) { return name in this.attributes ? this.attributes[name] : null; },
        removeAttribute(name) { delete this.attributes[name]; },
        // The controller uses `closest` to read skeleton hints off the clicked
        // control; nothing in these tests clicks through the overlay.
        closest() { return null; },
    };
    // `className` and classList are the same state in a real DOM.
    Object.defineProperty(el, 'classList', { value: el.classList });
    return el;
}

/** A document carrying just the two nodes the controller looks for. */
function document_(options = {}) {
    const html = element('html');
    const overlay = element('div', 'nx-page-skeleton');
    overlay.hidden = false;
    const escape = element('button', 'nx-skel-escape');
    escape.hidden = true;
    overlay.setAttribute('data-nx-variant', 'auth');
    overlay.setAttribute('data-nx-variant-default', 'auth');
    overlay.querySelector = () => ({}) /* every layout is "present" */;

    const byId = { 'nx-page-skeleton': overlay, 'nx-skel-escape': escape };
    const listeners = {};
    return {
        readyState: options.readyState || 'complete',
        documentElement: html,
        getElementById: (id) => byId[id] || null,
        addEventListener: (type, handler) => { (listeners[type] = listeners[type] || []).push(handler); },
        fire: (type, event) => (listeners[type] || []).forEach((handler) => handler(event || { type })),
        hasListener: (type) => Boolean((listeners[type] || []).length),
    };
}

function page(options = {}) {
    const document = document_(options);
    const nodes = {
        overlay: document.getElementById('nx-page-skeleton'),
        escape: document.getElementById('nx-skel-escape'),
    };
    const timers = [];
    const windowListeners = {};
    const window = {
        location: { pathname: options.path || '/dashboard/', search: '', href: 'http://localhost' },
        addEventListener: (type, handler) => { (windowListeners[type] = windowListeners[type] || []).push(handler); },
        fireWindow: (type, event) => (windowListeners[type] || []).forEach((handler) => handler(event || { type })),
        matchMedia: () => ({ matches: false }),
        URLSearchParams: class { has() { return Boolean(options.pin); } get() { return options.pin || null; } },
        URL: class { constructor(href) { this.pathname = String(href); } },
        setTimeout: (fn, ms) => { const timer = { fn, ms }; timers.push(timer); return timer; },
        clearTimeout: (timer) => {
            const index = timers.indexOf(timer);
            if (index >= 0) timers.splice(index, 1);
        },
        document,
    };
    // The controller reaches these through the window it closes over.
    window.window = window;
    runInNewContext(script, {
        window,
        document,
        // `window.URL` is read off the window object inside the script.
        URL: window.URL,
        URLSearchParams: window.URLSearchParams,
    });
    const dom = {
        window, document, nodes,
        /** Fire the timer registered for `ms` (the controller only uses one per delay). */
        runTimer(ms) {
            const timer = timers.find((t) => t.ms === ms);
            assert.ok(timer, `no pending timer for ${ms}ms (pending: ${timers.map((t) => t.ms).join(', ')})`);
            window.clearTimeout(timer);
            timer.fn();
        },
        pending: () => timers.map((t) => t.ms),
        /** The fade-out has finished: only now is the overlay really gone. */
        settle() {
            if (timers.some((t) => t.ms === 180)) dom.runTimer(180);
        },
        /** A navigation is under way: the overlay is up and belongs to this page. */
        depart() { dom.window.NexusSkeleton.show('dashboard'); dom.runTimer(120); },
    };
    return dom;
}

test('the page being left cannot take a departure skeleton down', () => {
    // The regression: a slow response outlived the old 12s watchdog, which
    // revealed the page being left on top of the skeleton (skeleton → old page
    // → new page). Its load signals now belong to it and are ignored.
    const dom = page();
    dom.depart();

    assert.equal(dom.nodes.overlay.hidden, false, 'the skeleton is up for the navigation');

    dom.document.fire('DOMContentLoaded');
    dom.window.fireWindow('load');
    dom.window.fireWindow('pageshow', { persisted: false });
    dom.document.fire('DOMContentLoaded');

    assert.equal(dom.nodes.overlay.hidden, false,
        'the page being left must not take the skeleton down while a navigation is in flight');
    assert.equal(dom.nodes.overlay.classList.contains('is-leaving'), false,
        'and must not start fading it out either');
    assert.equal(dom.pending().includes(180), false, 'no fade is pending');
    assert.deepEqual(dom.pending().sort((a, b) => a - b), [12000, 90000],
        'the wait it was given is still the one in force');
});

test('a page that is not navigating takes its own skeleton away', () => {
    // The server paints the overlay into every page; the page it belongs to
    // takes it away as soon as it is up.
    const dom = page();
    assert.equal(dom.nodes.overlay.hidden, false, 'the server leaves the overlay up');

    dom.document.fire('DOMContentLoaded');
    dom.settle();

    assert.equal(dom.nodes.overlay.hidden, true, 'the page it belongs to takes it away');
});

test('an overshooting load event still clears a stuck skeleton', () => {
    const dom = page();
    dom.window.fireWindow('load');
    dom.settle();
    assert.equal(dom.nodes.overlay.hidden, true);
});

test('a long wait offers the page back instead of guessing', () => {
    const dom = page();
    dom.depart();

    assert.equal(dom.nodes.escape.hidden, true, 'nothing is offered while the wait is normal');

    dom.runTimer(12000);

    assert.equal(dom.nodes.escape.hidden, false, 'the way out appears once the wait is clearly long');
    assert.ok(dom.nodes.overlay.classList.contains('is-wait-exit'));
    assert.equal(dom.nodes.overlay.hidden, false, 'the skeleton is still up: the response may still arrive');
});

test('clicking the way out gives the page back', () => {
    const dom = page();
    dom.depart();
    dom.runTimer(12000);

    let prevented = false;
    dom.document.fire('click', { preventDefault() { prevented = true; } });
    dom.settle();

    assert.ok(prevented, 'the click is consumed by the overlay');
    assert.equal(dom.nodes.overlay.hidden, true);
    assert.equal(dom.nodes.escape.hidden, true);
    assert.equal(dom.nodes.overlay.getAttribute('data-nx-variant'), 'auth',
        'released, the overlay goes back to this page\'s own shape for the next attempt');
});

test('Escape gives the page back too', () => {
    const dom = page();
    dom.depart();
    dom.runTimer(12000);
    assert.equal(dom.nodes.escape.hidden, false, 'the way out is offered first');

    dom.document.fire('keydown', { key: 'Escape' });
    dom.settle();

    assert.equal(dom.nodes.overlay.hidden, true);
});

test('an accidental click while the wait is normal cannot dismiss the skeleton', () => {
    const dom = page();
    dom.depart();

    let prevented = false;
    dom.document.fire('click', { preventDefault() { prevented = true; } });

    assert.equal(prevented, false, 'the overlay does not consume ordinary clicks');
    assert.equal(dom.nodes.overlay.hidden, false, 'and stays up for the navigation in flight');
});

test('a page that never finishes loading also offers a way out', () => {
    // The skeleton is on screen before the page is up — that is its whole job.
    // If the page's own load hangs (a blocked stylesheet, a stalled request),
    // the same way out applies rather than a wall nobody can get past.
    const dom = page({ readyState: 'loading' });
    assert.equal(dom.nodes.overlay.hidden, false, 'the server paints it into the page');
    // The controller itself runs on DOMContentLoaded, from the bottom of the
    // body. The page is then "up" as far as the parser is concerned, but the
    // overlay is still standing in for it.
    dom.document.fire('DOMContentLoaded');
    assert.deepEqual(dom.pending().sort((a, b) => a - b), [12000, 90000],
        'the wait is armed as soon as the controller runs');

    dom.runTimer(12000);
    assert.equal(dom.nodes.escape.hidden, false, 'the way out is offered');

    let prevented = false;
    dom.document.fire('click', { preventDefault() { prevented = true; } });
    dom.settle();
    assert.ok(prevented);
    assert.equal(dom.nodes.overlay.hidden, true, 'and it gives the page back');
});

test('the backstop releases the page even if nobody asks', () => {
    const dom = page();
    dom.depart();

    dom.runTimer(90000);
    dom.settle();

    assert.equal(dom.nodes.overlay.hidden, true);
});

test('a navigation that never happened leaves the next one free to paint', () => {
    const dom = page();
    dom.depart();
    dom.runTimer(90000);                      // the backstop fires
    dom.settle();
    dom.document.fire('DOMContentLoaded');    // ...then the page catches up

    assert.equal(dom.nodes.overlay.hidden, true);

    dom.depart();                             // the next click paints again
    assert.equal(dom.nodes.overlay.hidden, false);
});

test('the review pin is still held open and never offers a way out', () => {
    // `?nx-skeleton` holds a layout on screen for review; it is not a
    // navigation, so it must not grow the escape control or time out.
    const dom = page({ pin: 'wizard' });

    assert.equal(dom.document.hasListener('click'), false, 'the nav hooks are not wired for a pin');
    dom.runTimer(120);                       // the paint delay, not a wait
    assert.deepEqual(dom.pending(), [], 'a pinned layout is held open, not timed');
    dom.document.fire('DOMContentLoaded');
    assert.equal(dom.nodes.overlay.hidden, false, 'the pin stays up');
    assert.equal(dom.nodes.escape.hidden, true, 'no way out is offered: nothing is being waited for');
});

module.exports = {};
