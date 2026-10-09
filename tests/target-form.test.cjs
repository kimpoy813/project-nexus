const { test } = require('node:test');
const assert = require('node:assert/strict');
const { readFileSync } = require('node:fs');
const { runInNewContext } = require('node:vm');
const template = readFileSync('accounts/templates/dashboard/admin/target_form.html', 'utf8');
const script = template.match(/<script>([\s\S]*?)<\/script>/)[1];

function setup(target, quarters) {
    const input = value => ({ value: String(value), addEventListener(event, cb) { this[event] = cb; } });
    const targetInput = input(target);
    const actualInputs = quarters.map(input);
    const nodes = Object.fromEntries(['live-total', 'live-total-main', 'live-target-main', 'live-percent', 'live-bar'].map(id => [id, { style: {} }]));
    nodes['target-form'] = {
        querySelector: () => targetInput,
        querySelectorAll: () => actualInputs,
    };
    runInNewContext(script, { document: { getElementById: id => nodes[id] || null } });
    return { nodes, targetInput, actualInputs };
}

test('opening an edit form with no actuals shows 0%, not 100%', () => {
    const { nodes } = setup(200, [0, 0, 0, 0]);
    assert.equal(nodes['live-total'].textContent, '0');
    assert.equal(nodes['live-percent'].textContent, '0% of target');
    assert.equal(nodes['live-bar'].style.width, '0%');
});

test('sums only quarterly actuals and recalculates both kinds of edits', () => {
    const { nodes, targetInput, actualInputs } = setup(200, [10, 20, 30, 40]);
    assert.equal(nodes['live-total-main'].textContent, '100');
    assert.equal(nodes['live-percent'].textContent, '50% of target');
    targetInput.value = '400';
    targetInput.input();
    assert.equal(nodes['live-percent'].textContent, '25% of target');
    assert.equal(nodes['live-total-main'].textContent, '100');
    actualInputs[0].value = '110';
    actualInputs[0].input();
    assert.equal(nodes['live-percent'].textContent, '50% of target');
});

test('handles blank targets and actuals, completion and overachievement', () => {
    assert.equal(setup('', ['', '', '', '']).nodes['live-percent'].textContent, 'Set a target to track progress');
    assert.equal(setup(100, [25, 25, 25, 25]).nodes['live-percent'].textContent, '100% of target');
    const { nodes } = setup(100, [50, 50, 50, 0]);
    assert.equal(nodes['live-percent'].textContent, '150% of target');
    assert.equal(nodes['live-bar'].style.width, '100%');
});
