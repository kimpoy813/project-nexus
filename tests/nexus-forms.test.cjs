const { test } = require('node:test');
const assert = require('node:assert/strict');
const { readFileSync } = require('node:fs');
const { runInNewContext } = require('node:vm');

const script = readFileSync('static/js/nexus-forms.js', 'utf8');

/* Same minimal-DOM approach as the other component tests: enough to run the
   module, and timers kept in a queue so the "restore a stuck button" rule can
   be checked without waiting twenty seconds. */
class Element {
    constructor(tagName) {
        this.tagName = tagName.toLowerCase();
        this.nodeType = 1;
        this.attributes = {};
        this.children = [];
        this.listeners = {};
        this.className = '';
        this.textContent = '';
        this.value = '';
        this.disabled = false;
        this.focused = false;
        this.isConnected = true;
    }

    setAttribute(name, value) { this.attributes[name] = String(value); }
    getAttribute(name) { return Object.prototype.hasOwnProperty.call(this.attributes, name) ? this.attributes[name] : null; }
    hasAttribute(name) { return Object.prototype.hasOwnProperty.call(this.attributes, name); }
    removeAttribute(name) { delete this.attributes[name]; }

    appendChild(child) {
        child.parentNode = this;
        this.children.push(child);
        return child;
    }

    addEventListener(type, handler) {
        (this.listeners[type] = this.listeners[type] || []).push(handler);
    }

    dispatch(type, event = {}) {
        let allowed = true;
        let stopped = false;
        const payload = Object.assign({
            preventDefault() { allowed = false; },
            stopImmediatePropagation() { stopped = true; },
            defaultPrevented: false,
        }, event);
        for (const handler of this.listeners[type] || []) {
            handler(payload);
            if (stopped) break;
        }
        Object.defineProperty(payload, 'cancelled', { value: allowed, enumerable: false });
        payload.defaultPrevented = !allowed;
        return payload;
    }

    focus() { this.focused = true; }

    querySelector(selector) {
        if (selector === '[data-nx-error-summary]') {
            return this.children.find(child => child.hasAttribute('data-nx-error-summary')) || null;
        }
        return null;
    }

    querySelectorAll(selector) {
        if (selector === 'form') return this.children.filter(child => child.tagName === 'form');
        if (selector === 'button[type="submit"], input[type="submit"]') {
            return this.children.filter(child => child.hasAttribute('type') && child.getAttribute('type') === 'submit');
        }
        if (selector.includes('[data-nx-confirm]')) {
            // The real selector lists the tags that can carry the attribute.
            return this.children.filter(child => child.hasAttribute('data-nx-confirm')
                && selector.includes(child.tagName));
        }
        return [];
    }
}

function setup({ summary = null, forms = [], controls = [], answer = true } = {}) {
    const document = new Element('body');
    if (summary) document.appendChild(summary);
    forms.forEach(form => document.appendChild(form));
    controls.forEach(control => document.appendChild(control));

    const timers = [];
    const asked = [];
    const window = {
        setTimeout(callback, delay) {
            timers.push({ callback, delay });
            return timers.length;
        },
        // Stands in for the browser's own confirmation dialog: records the
        // question, answers with whatever the test asked for.
        confirm(message) {
            asked.push(message);
            return answer;
        },
    };

    runInNewContext(script, { window, document });
    const runTimers = (delay) => timers.filter(timer => timer.delay === delay).forEach(timer => timer.callback());
    return { window, document, timers, runTimers, asked };
}

function summary(attributes = {}) {
    const element = new Element('div');
    element.setAttribute('data-nx-error-summary', 'true');
    Object.entries(attributes).forEach(([name, value]) => element.setAttribute(name, value));
    return element;
}

function form({ busy = true } = {}) {
    const element = new Element('form');
    if (busy) element.setAttribute('data-nx-busy', '');
    return element;
}

function button(label = 'Sign in', busyLabel = 'Signing in…') {
    const element = new Element('button');
    element.setAttribute('type', 'submit');
    if (busyLabel) element.setAttribute('data-nx-busy-label', busyLabel);
    element.textContent = label;
    return element;
}

test('a failed submit moves focus to the error summary', () => {
    const box = summary();
    box.textContent = 'Please correct the following before continuing:';
    setup({ summary: box });

    assert.equal(box.focused, true, 'the summary is announced instead of the button');
    assert.equal(box.getAttribute('tabindex'), '-1');
});

test('a hidden summary is not focused', () => {
    const box = summary({ hidden: 'hidden' });
    setup({ summary: box });
    assert.equal(box.focused, false);
});

test('a page without a summary is left alone', () => {
    const context = setup();
    assert.equal(context.window.nexusForms.focusErrorSummary(context.document), null);
});

test('submitting swaps the button label, marks the form busy and keeps its value', () => {
    const signIn = button();
    const target = form();
    target.appendChild(signIn);
    setup({ forms: [target] });

    target.dispatch('submit', { submitter: signIn });

    assert.equal(target.getAttribute('aria-busy'), 'true');
    assert.equal(signIn.textContent, 'Signing in…');
    assert.equal(signIn.getAttribute('aria-disabled'), 'true');
    assert.ok(signIn.className.includes('is-busy'));
    assert.equal(signIn.getAttribute('data-nx-busy-original'), 'Sign in');
    assert.equal(signIn.disabled, false, 'disabling inside the handler would drop the button value');
});

test('the button is disabled once the form data has been built', () => {
    const signIn = button();
    const target = form();
    target.appendChild(signIn);
    const context = setup({ forms: [target] });

    target.dispatch('submit', { submitter: signIn });
    context.runTimers(0);
    assert.equal(signIn.disabled, true);
});

test('a second submit while the first is in flight is cancelled', () => {
    const signIn = button();
    const target = form();
    target.appendChild(signIn);
    setup({ forms: [target] });

    target.dispatch('submit', { submitter: signIn });
    const second = target.dispatch('submit', { submitter: signIn });
    assert.equal(second.defaultPrevented, true);
});

test('a form that never completes gets its button back', () => {
    const signIn = button();
    const target = form();
    target.appendChild(signIn);
    const context = setup({ forms: [target] });

    target.dispatch('submit', { submitter: signIn });
    context.runTimers(20000);

    assert.equal(target.getAttribute('aria-busy'), null);
    assert.equal(signIn.disabled, false);
    assert.equal(signIn.textContent, 'Sign in');
    assert.ok(!signIn.className.includes('is-busy'));
});

test('forms without the opt-in are untouched', () => {
    const signIn = button();
    const target = form({ busy: false });
    target.appendChild(signIn);
    setup({ forms: [target] });

    target.dispatch('submit', { submitter: signIn });
    assert.equal(target.getAttribute('aria-busy'), null);
    assert.equal(signIn.textContent, 'Sign in');
});


/* ---------------------------------------------------------------- confirmations */

test('a destructive form asks before it submits', () => {
    const deleteForm = form({ busy: false });
    deleteForm.setAttribute('data-nx-confirm', 'Delete this template file for good?');
    const context = setup({ forms: [deleteForm] });

    const event = deleteForm.dispatch('submit');
    assert.deepEqual(context.asked, ['Delete this template file for good?']);
    assert.equal(event.defaultPrevented, false, 'the answer was yes, so it goes ahead');
});

test('cancelling leaves the button exactly as it was', () => {
    const remove = button('Delete', null);
    const deleteForm = form();
    deleteForm.setAttribute('data-nx-confirm', 'Delete this photo?');
    deleteForm.appendChild(remove);
    const context = setup({ forms: [deleteForm], answer: false });

    const event = deleteForm.dispatch('submit', { submitter: remove });

    assert.equal(event.defaultPrevented, true, 'the submit never reaches the browser');
    assert.equal(deleteForm.getAttribute('aria-busy'), null, 'no busy state was applied');
    assert.equal(remove.textContent, 'Delete', 'the label did not change');
    assert.equal(remove.disabled, false);
    assert.ok(!remove.className.includes('is-busy'));
});

test('a destructive link asks on click', () => {
    const link = new Element('a');
    link.setAttribute('data-nx-confirm', 'Delete this activity? This cannot be undone.');
    const context = setup({ controls: [link], answer: false });

    const event = link.dispatch('click');
    assert.deepEqual(context.asked, ['Delete this activity? This cannot be undone.']);
    assert.equal(event.defaultPrevented, true, 'navigation is cancelled');

    const other = new Element('a');
    other.setAttribute('data-nx-confirm', 'Delete this activity?');
    const allowed = setup({ controls: [other], answer: true });
    assert.equal(other.dispatch('click').defaultPrevented, false);
    assert.deepEqual(allowed.asked, ['Delete this activity?']);
});

test('a button that submits an outside form asks on click', () => {
    const buttonOutside = button('Delete', null);
    delete buttonOutside.attributes.type;
    buttonOutside.setAttribute('data-nx-confirm', 'Delete this template file for good?');
    const context = setup({ controls: [buttonOutside], answer: false });

    assert.equal(buttonOutside.dispatch('click').defaultPrevented, true);
    assert.equal(context.asked.length, 1);
});

test('an empty message still asks something rather than nothing', () => {
    const deleteForm = form({ busy: false });
    deleteForm.setAttribute('data-nx-confirm', '  ');
    setup({ forms: [deleteForm], answer: false });

    assert.equal(
        deleteForm.dispatch('submit').defaultPrevented,
        true,
        'a missing message must not silently delete'
    );
});

test('the fallback wording is written for a person', () => {
    const context = setup();
    assert.equal(context.window.nexusForms.confirmMessage(new Element('form')), 'Are you sure? This cannot be undone.');
});

test('the confirmation is only wired once per control', () => {
    const deleteForm = form({ busy: false });
    deleteForm.setAttribute('data-nx-confirm', 'Delete this?');
    const context = setup({ forms: [deleteForm] });

    context.window.nexusForms.enhance(context.document);
    deleteForm.dispatch('submit');
    assert.equal(context.asked.length, 1, 'a second enhance() must not double-ask');
});
