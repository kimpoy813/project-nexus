const { test } = require('node:test');
const assert = require('node:assert/strict');
const { readFileSync } = require('node:fs');
const { runInNewContext } = require('node:vm');

const script = readFileSync('static/js/nexus-password.js', 'utf8');

/* A DOM just large enough for the component: elements with attributes, a
   class list, children, listeners and a focus method. Keeping the stub small
   means the test is about the rules the component promises (what the button
   says, when the hint shows), not about the stub itself. */
class Element {
    constructor(tagName) {
        this.tagName = tagName.toLowerCase();
        this.nodeType = 1;
        this.attributes = {};
        this.children = [];
        this.parentNode = null;
        this.listeners = {};
        this.className = '';
        this.textContent = '';
        this.value = '';
        this.focused = false;
        this.classList = {
            names: new Set(),
            add: (...names) => names.forEach(name => this.classList.names.add(name)),
            remove: (...names) => names.forEach(name => this.classList.names.delete(name)),
            contains: name => this.classList.names.has(name),
        };
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

    insertBefore(child, reference) {
        child.parentNode = this;
        const index = this.children.indexOf(reference);
        this.children.splice(index < 0 ? this.children.length : index, 0, child);
        return child;
    }

    addEventListener(type, handler) {
        (this.listeners[type] = this.listeners[type] || []).push(handler);
    }

    dispatch(type, event = {}) {
        (this.listeners[type] || []).forEach(handler => handler(event));
    }

    focus() { this.focused = true; }

    findById(id) {
        for (const child of this.children) {
            if (child.getAttribute && child.getAttribute('id') === id) return child;
            const deeper = child.findById ? child.findById(id) : null;
            if (deeper) return deeper;
        }
        return null;
    }

    querySelectorAll(selector) {
        const found = [];
        const visit = node => {
            for (const child of node.children) {
                if (selector === 'input' && child.tagName === 'input') found.push(child);
                visit(child);
            }
        };
        visit(this);
        return found;
    }
}

function input(attributes = {}) {
    const element = new Element('input');
    element.type = 'password';
    Object.entries(attributes).forEach(([name, value]) => element.setAttribute(name, value));
    return element;
}

function setup({ inputs = [], documentExtras = {} } = {}) {
    // The fields live in a host, the way they do in a real document: the
    // component inserts its wrapper before each input.
    const host = new Element('div');
    inputs.forEach(field => host.appendChild(field));
    const document = {
        readyState: 'complete',
        createElement: tag => new Element(tag),
        querySelectorAll: selector => (selector === 'input' ? host.querySelectorAll('input') : []),
        getElementById: id => host.findById(id) || documentExtras[id] || null,
        addEventListener() { throw new Error('a ready document should not wait for DOMContentLoaded'); },
    };
    const window = {};
    runInNewContext(script, { window, document });
    return { window, document };
}

function toggleOf(element) {
    const wrapper = element.parentNode;
    return wrapper.children.find(child => child.tagName === 'button');
}

function rulesOf(element) {
    const host = element.parentNode.parentNode;
    return host.children.find(child => child.tagName === 'ul') || null;
}

function hintsOf(element) {
    const host = element.parentNode.parentNode;
    return host.children.filter(child => child.tagName === 'p');
}

test('every password field gets a labelled reveal button', () => {
    const password = input({ id: 'id_password', name: 'password' });
    setup({ inputs: [password] });

    const toggle = toggleOf(password);
    assert.ok(toggle, 'the field is wrapped with a toggle beside it');
    assert.equal(toggle.getAttribute('type'), 'button', 'never submits the form');
    assert.equal(toggle.getAttribute('aria-pressed'), 'false');
    assert.equal(toggle.getAttribute('aria-label'), 'Show password');
    assert.equal(toggle.className, 'nx-password__toggle');
    assert.ok(toggle.innerHTML.includes('nx-password__icon--show'));
});

test('the toggle shows the password and says what pressing it will do next', () => {
    const password = input({ id: 'id_password' });
    setup({ inputs: [password] });
    const toggle = toggleOf(password);

    toggle.dispatch('click', { preventDefault() {} });
    assert.equal(password.type, 'text');
    assert.equal(toggle.getAttribute('aria-pressed'), 'true');
    assert.equal(toggle.getAttribute('aria-label'), 'Hide password');
    assert.equal(toggle.getAttribute('title'), 'Hide password');

    toggle.dispatch('click', { preventDefault() {} });
    assert.equal(password.type, 'password');
    assert.equal(toggle.getAttribute('aria-pressed'), 'false');
    assert.equal(toggle.getAttribute('aria-label'), 'Show password');
});

test('Escape hides a revealed password again without clearing it', () => {
    const password = input({ id: 'id_password' });
    password.value = 'Secret123';
    setup({ inputs: [password] });
    toggleOf(password).dispatch('click', { preventDefault() {} });
    assert.equal(password.type, 'text');

    password.dispatch('keydown', { key: 'Escape' });
    assert.equal(password.type, 'password');
    assert.equal(password.value, 'Secret123', 'nothing typed is lost');
});

test('Caps Lock is announced while it is on, and forgotten on blur', () => {
    const password = input({ id: 'id_password' });
    const context = setup({ inputs: [password] });
    const hint = context.document.getElementById('id_password-caps');
    assert.ok(hint, 'the hint exists next to the field');
    assert.equal(hint.getAttribute('hidden'), 'hidden');
    assert.equal(hint.getAttribute('aria-live'), 'polite');

    password.dispatch('keydown', { key: 'A', getModifierState: name => name === 'CapsLock' });
    assert.equal(hint.hasAttribute('hidden'), false);
    assert.equal(hint.textContent, 'Caps Lock is on.');

    password.dispatch('keydown', { key: 'a', getModifierState: () => false });
    assert.equal(hint.hasAttribute('hidden'), true);

    password.dispatch('keydown', { getModifierState: () => true });
    password.dispatch('blur', {});
    assert.equal(hint.hasAttribute('hidden'), true, 'a hint must not outlive the field');
});

test('the requirements are visible while typing, not only after a failed submit', () => {
    const password = input({ id: 'id_password', 'data-nx-password-rules': 'length,number,uppercase' });
    setup({ inputs: [password] });

    const rules = rulesOf(password);
    assert.ok(rules, 'the checklist is rendered under the field');
    assert.equal(rules.children.length, 3);
    assert.equal(rules.children[0].getAttribute('data-rule'), 'length');
    assert.equal(rules.children[0].getAttribute('data-met'), 'false');
    assert.equal(rules.children[1].children[1].textContent, 'Contains a number');

    const described = password.getAttribute('aria-describedby');
    assert.equal(described, 'id_password-rules', 'the rules are read with the field');

    password.value = 'Secret';
    password.dispatch('input', {});
    const met = rules.children.map(item => item.getAttribute('data-met'));
    assert.deepEqual(met, ['false', 'false', 'true'], 'uppercase is met before the others');

    password.value = 'Secret123';
    password.dispatch('input', {});
    assert.deepEqual(
        rules.children.map(item => item.getAttribute('data-met')),
        ['true', 'true', 'true']
    );
});

test('a field without the rules attribute gets no checklist', () => {
    const password = input({ id: 'id_password' });
    setup({ inputs: [password] });
    assert.equal(rulesOf(password), null);
});

test('the confirmation field reports a mismatch while typing', () => {
    const password = input({ id: 'id_password' });
    const confirm = input({ id: 'id_confirm', 'data-nx-match': 'id_password' });
    const context = setup({ inputs: [password, confirm] });
    const hint = context.document.getElementById('id_confirm-match');
    assert.ok(hint);
    assert.equal(hint.hasAttribute('hidden'), true, 'nothing to say until something is typed');

    confirm.value = 'Secret12';
    confirm.dispatch('input', {});
    assert.equal(hint.hasAttribute('hidden'), false);
    assert.equal(hint.textContent, 'Passwords do not match yet.');
    assert.equal(hint.getAttribute('data-state'), 'bad');

    password.value = 'Secret123';
    confirm.value = 'Secret123';
    password.dispatch('input', {});
    assert.equal(hint.textContent, 'Passwords match.');
    assert.equal(hint.getAttribute('data-state'), 'ok');

    confirm.value = '';
    confirm.dispatch('input', {});
    assert.equal(hint.hasAttribute('hidden'), true);
});

test('enhancing twice does not stack buttons, and opt-outs are respected', () => {
    const password = input({ id: 'id_password' });
    const optedOut = input({ id: 'id_other', 'data-no-password-toggle': 'true' });
    const context = setup({ inputs: [password, optedOut] });

    context.window.nexusPassword.enhance(context.document);
    assert.equal(password.parentNode.children.filter(child => child.tagName === 'button').length, 1);
    assert.equal(optedOut.hasAttribute('data-nx-password-ready'), false);
    assert.equal(
        optedOut.parentNode.children.filter(child => child.tagName === 'button').length,
        0,
        'an opted-out field is left exactly as it was'
    );
});

test('a password field is left alone when it is not in the document', () => {
    const detached = input({ id: 'id_detached' });
    const context = setup({ inputs: [detached] });
    assert.ok(toggleOf(detached), 'the in-document field is enhanced');
    const second = input({ id: 'id_second' });
    context.window.nexusPassword.enhance({ querySelectorAll: () => [second] });
    assert.equal(second.parentNode, null, 'a detached node has no wrapper to insert');
});
