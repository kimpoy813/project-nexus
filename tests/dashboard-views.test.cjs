const { test } = require('node:test');
const assert = require('node:assert/strict');
const { readFileSync } = require('node:fs');
const { runInNewContext } = require('node:vm');
const script = readFileSync('static/js/dashboard-views.js', 'utf8');

function setup(saved, blocked = false) {
    const panels = ['table', 'cards'].map(view => ({ dataset: { proposalPanel: view } }));
    const buttons = ['table', 'cards'].map(view => ({
        dataset: { proposalView: view },
        setAttribute(name, value) { this[name] = value; },
        addEventListener(event, callback) { this.click = callback; },
    }));
    const root = { querySelectorAll: selector => selector === '[data-proposal-panel]' ? panels : buttons };
    const storage = { value: saved };
    runInNewContext(script, {
        document: {
            addEventListener(event, callback) { callback(); },
            querySelectorAll: selector => selector === '[data-proposal-layout]' ? [root] : [],
        },
        localStorage: {
            getItem() { if (blocked) throw Error('Blocked'); return storage.value; },
            setItem(key, value) { if (blocked) throw Error('Blocked'); storage.value = value; },
        },
    });
    return { panels, buttons, storage };
}

test('defaults to cards, toggles both ways and saves preference', () => {
    const { panels, buttons, storage } = setup();
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
    assert.equal(setup('table').panels[0].hidden, false);
    assert.equal(setup('invalid').panels[1].hidden, false);
});

test('works when browser storage is blocked', () => {
    const { panels, buttons } = setup(null, true);
    buttons[0].click();
    assert.equal(panels[0].hidden, false);
});
