const { test } = require('node:test');
const assert = require('node:assert/strict');
// The helpers run inside a vm, so their objects come from another realm and
// deepStrictEqual would fail on prototype identity alone.
const { deepEqual: samePlan } = require('node:assert');
const { readFileSync } = require('node:fs');
const { runInNewContext } = require('node:vm');

const script = readFileSync('static/js/process-steps-editor.js', 'utf8');

// The script self-initialises against the page; hand it an inert document so
// it exposes its API without touching a DOM.
const sandbox = { document: { readyState: 'complete', querySelectorAll: () => [] } };
runInNewContext(script, sandbox);
const { planDrop, planIndent, planOutdent, withoutSubtree, INDENT_PX } = sandbox.NexusProcessSteps;

/** rows: [ref, depth, parentRef] -> the shape the DOM reader produces. */
function rows(list) {
    return list.map(([ref, depth, parentRef]) => ({ ref, depth, parentRef: parentRef || null }));
}

const FLAT = rows([['a', 0], ['b', 0], ['c', 0]]);
const NESTED = rows([['a', 0], ['a1', 1, 'a'], ['a2', 1, 'a'], ['b', 0]]);
const DEEP = rows([['a', 0], ['a1', 1, 'a'], ['a11', 2, 'a1'], ['b', 0]]);

test('withoutSubtree drops a row and everything nested under it', () => {
    assert.deepEqual(withoutSubtree(DEEP, 'a1').map(r => r.ref), ['a', 'b']);
    assert.deepEqual(withoutSubtree(DEEP, 'a').map(r => r.ref), ['b']);
    assert.deepEqual(withoutSubtree(DEEP, 'b').map(r => r.ref), ['a', 'a1', 'a11']);
    assert.deepEqual(withoutSubtree(DEEP, 'missing').map(r => r.ref), ['a', 'a1', 'a11', 'b']);
});

test('dragging sideways nests a step under the one above it', () => {
    const others = withoutSubtree(FLAT, 'c');           // a, b
    const plan = planDrop(others, 1, INDENT_PX, 0, INDENT_PX);  // dropped one indent right of the left edge

    samePlan(plan, { depth: 1, parentRef: 'a', beforeRef: null });
});

test('a step dropped at the left edge stays at the top level', () => {
    const plan = planDrop(withoutSubtree(FLAT, 'c'), 1, 4, 0, INDENT_PX);
    samePlan(plan, { depth: 0, parentRef: null, beforeRef: 'b' });
});

test('nesting can only ever go one level deeper than the row above', () => {
    // Dropped three indents deep right after a1 (depth 1): clamped to depth 2.
    const others = withoutSubtree(DEEP, 'b');           // a, a1, a11
    const plan = planDrop(others, 2, INDENT_PX * 3, 0, INDENT_PX);

    assert.equal(plan.depth, 2);
    assert.equal(plan.parentRef, 'a1');
});

test('the first row of a list cannot be nested', () => {
    const plan = planDrop(withoutSubtree(FLAT, 'a'), 0, INDENT_PX * 2, 0, INDENT_PX);
    samePlan(plan, { depth: 0, parentRef: null, beforeRef: 'b' });
});

test('a drop lands before the next sibling at that level', () => {
    // Between a1 and a2, still nested under a.
    const others = withoutSubtree(NESTED, 'b');
    const plan = planDrop(others, 2, INDENT_PX, 0, INDENT_PX);

    assert.equal(plan.depth, 1);
    assert.equal(plan.parentRef, 'a');
    assert.equal(plan.beforeRef, 'a2');
});

test('a drop with no pointer position leaves the nesting alone', () => {
    assert.equal(planDrop(withoutSubtree(FLAT, 'c'), 1, undefined, 0, INDENT_PX), null);
    assert.equal(planDrop(withoutSubtree(FLAT, 'c'), 1, NaN, 0, INDENT_PX), null);
});

test('indent nests under the row above and outdent promotes to its next sibling', () => {
    // Nest b under a2, then promote it back out again.
    const indented = planIndent(NESTED, 'b');
    samePlan(indented, { depth: 2, parentRef: 'a2', beforeRef: null });

    const outdented = planOutdent(NESTED, 'a1');
    samePlan(outdented, { depth: 0, parentRef: null, beforeRef: 'b' });
});

test('indent and outdent refuse moves that make no sense', () => {
    assert.equal(planIndent(FLAT, 'a'), null);          // nothing above it
    assert.equal(planOutdent(FLAT, 'a'), null);         // already top level
    assert.equal(planIndent(FLAT, 'nope'), null);
    assert.equal(planOutdent(FLAT, 'nope'), null);
});

test('outdenting keeps the row ahead of its former parent subtree', () => {
    // a11 leaves a1 and lands right after a1's whole subtree.
    const plan = planOutdent(DEEP, 'a11');
    samePlan(plan, { depth: 1, parentRef: 'a', beforeRef: null });
});

test('a dangling parent link is repaired by promoting to the top level', () => {
    const plan = planOutdent(rows([['a', 0], ['x', 1, 'ghost']]), 'x');
    samePlan(plan, { depth: 0, parentRef: null, beforeRef: null });
});
