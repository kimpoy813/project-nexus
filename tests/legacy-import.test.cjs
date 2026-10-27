const { test } = require('node:test');
const assert = require('node:assert/strict');
const { readFileSync } = require('node:fs');
const { runInNewContext } = require('node:vm');
const script = readFileSync('static/js/legacy-import.js', 'utf8');

function setup(initial = 'HISTORICAL') {
    const nodes = {};
    const element = () => ({
        value: '', textContent: '', hidden: false, disabled: false, checked: false,
        files: [], selectedOptions: [{ textContent: 'Not Started' }], dataset: {}, attributes: {}, events: {},
        addEventListener(type, fn) { this.events[type] = fn; },
        setAttribute(key, value) { this.attributes[key] = value; },
        getAttribute(key) { return this.attributes[key] ?? null; },
        removeAttribute(key) { delete this.attributes[key]; },
        querySelectorAll() { return []; },
        closest() { return this.parent; },
        focus() { this.focused = true; },
    });
    const get = (id) => nodes[id] ??= element();
    const form = get('legacy-import-form');
    const selected = { value: initial };
    const accounts = ['Maria Santos — Main Campus', 'Jose Reyes — South Campus'].map(name => {
        const input = element(); input.parent = element(); input.parent.textContent = name; return input;
    });
    for (const [wrapper, control] of [
        ['historical-status-field', 'id_proposal_status'], ['moa-stage-field', 'id_moa_stage'],
        ['implementation-stage-field', 'id_implementation_stage'],
        ['terminal-report-field', 'id_terminal_report_file'], ['moa-file-field', 'id_moa_draft_file'],
    ]) get(wrapper).querySelectorAll = () => [get(control)];
    // The photo block holds a multi-file picker plus its shared caption box.
    get('photo-documentation-field').querySelectorAll =
        () => [get('id_documentation_photos'), get('id_documentation_caption')];
    for (const id of ['review-proposal', 'review-moa', 'review-implementation']) get(id).parent = element();
    get('id_proposal_status').value = 'APPROVED';
    get('id_proposal_status').selectedOptions = [{ textContent: 'Approved / Claiming' }];
    get('id_moa_stage').value = 'NOT_STARTED';
    get('id_implementation_stage').value = 'IMPLEMENTATION';
    get('id_implementation_stage').selectedOptions = [{ textContent: 'Implementation of Extension Activity' }];
    get('assignment-error').hidden = true;
    const files = [
        'id_legacy_proposal_file', 'id_moa_draft_file', 'id_terminal_report_file',
        'id_documentation_photos', 'id_attachments',
    ].map(get);
    form.querySelector = () => selected;
    form.querySelectorAll = (selector) => selector.includes('assigned_proponents') ? accounts : files.filter(input => !input.disabled);
    const window = element();
    runInNewContext(script, {
        document: { getElementById: (id) => id === 'legacy-errors' ? null : get(id), querySelector: get },
        window,
    });
    const change = () => form.events.change();
    const setState = value => { selected.value = value; change(); };
    const submit = () => {
        const event = { prevented: false, preventDefault() { this.prevented = true; } };
        form.events.submit(event); return event.prevented;
    };
    return { get, accounts, form, change, setState, submit, window };
}

test('pending MOA never starts either unfinished phase in the preview', () => {
    const { get, setState } = setup();
    assert.equal(get('historical-status-field').hidden, false);
    setState('MOA_PENDING');
    assert.equal(get('historical-status-field').hidden, true);
    assert.equal(get('moa-stage-field').hidden, false);
    assert.equal(get('review-proposal').textContent, 'Completed');
    assert.equal(get('review-moa').textContent, 'Not Started');
    assert.equal(get('review-implementation').textContent, 'Not Started');
    assert.equal(get('review-reporting').textContent, 'Director view: MOA · In progress.');
});

test('phase cards update the preview and disable irrelevant controls', () => {
    const { get, setState } = setup();
    setState('ONGOING');
    assert.equal(get('id_moa_stage').disabled, true);
    assert.equal(get('id_implementation_stage').disabled, false);
    assert.equal(get('id_terminal_report_file').disabled, true);
    assert.equal(get('id_documentation_photos').disabled, true);
    assert.equal(get('review-moa').textContent, 'Completed');
    assert.equal(get('review-reporting').textContent, 'Director view: Implementation · In progress.');
    setState('COMPLETED');
    assert.equal(get('id_implementation_stage').disabled, true);
    assert.equal(get('id_terminal_report_file').disabled, false);
    assert.equal(get('id_documentation_photos').disabled, false);
    assert.equal(get('review-reporting').textContent, 'Director view: Completed · Completed.');
});

test('hidden files are excluded, but selections are preserved when switching back', () => {
    const { get, setState, change } = setup('COMPLETED');
    get('id_terminal_report_file').files = [{}];
    get('id_moa_draft_file').files = [{}];
    change();
    assert.equal(get('review-files').textContent, '2');
    setState('MOA_PENDING');
    assert.equal(get('review-files').textContent, '0');
    get('id_moa_stage').value = 'DRAFT'; change();
    assert.equal(get('review-files').textContent, '1');
    setState('COMPLETED');
    assert.equal(get('review-files').textContent, '2');
});

test('historical summary matches file-inferred progress without assuming proposal completion', () => {
    const { get, change } = setup();
    get('id_moa_draft_file').files = [{}];
    get('id_terminal_report_file').files = [{}]; change();
    assert.equal(get('review-reporting').textContent, 'Director view: Implementation · In progress.');
    get('id_proposal_status').value = 'COMPLETED'; change();
    assert.equal(get('review-reporting').textContent, 'Director view: Completed · Completed.');
});

test('photo documentation opens only once the activity is completed', () => {
    const { get, setState, change } = setup('HISTORICAL');
    assert.equal(get('photo-documentation-field').hidden, true);
    assert.equal(get('id_documentation_photos').disabled, true);
    assert.equal(get('id_documentation_caption').disabled, true);
    for (const state of ['MOA_PENDING', 'ONGOING']) {
        setState(state);
        assert.equal(get('photo-documentation-field').hidden, true, `${state} keeps the photo block closed`);
        assert.equal(get('id_documentation_photos').disabled, true);
    }
    setState('COMPLETED');
    assert.equal(get('photo-documentation-field').hidden, false);
    assert.equal(get('id_documentation_photos').disabled, false);
    assert.equal(get('id_documentation_caption').disabled, false);
    // Photos count towards the attached-files summary only while they are filed.
    get('id_documentation_photos').files = [{}, {}];
    change();
    assert.equal(get('review-files').textContent, '2');
    setState('ONGOING');
    assert.equal(get('review-files').textContent, '0');
    setState('COMPLETED');
    assert.equal(get('review-files').textContent, '2');
});

test('search and selected-only filtering never clear assignments', () => {
    const { get, accounts, change } = setup('MOA_PENDING');
    accounts[0].checked = true;
    get('account-search').value = 'South Campus'; change();
    assert.equal(accounts[0].parent.hidden, true);
    assert.equal(accounts[1].parent.hidden, false);
    assert.equal(get('review-accounts').textContent, '1');
    get('show-selected').events.click();
    assert.equal(get('account-empty').hidden, false);
    assert.equal(accounts[0].checked, true);
    get('account-search').value = ''; get('account-search').events.input();
    assert.equal(accounts[0].parent.hidden, false);
    assert.equal(accounts[1].parent.hidden, true);
});

test('required assignments block submission and focus the account finder', () => {
    const { get, accounts, submit, change } = setup('MOA_PENDING');
    assert.equal(submit(), true);
    assert.equal(get('assignment-error').hidden, false);
    assert.equal(get('account-search').focused, true);
    accounts[0].checked = true; change();
    assert.equal(get('assignment-error').hidden, true);
    assert.equal(submit(), false);
    assert.equal(get('import-submit').disabled, true);
    assert.equal(submit(), true, 'second click is blocked');
});

test('returning with browser back restores an enabled submit button', () => {
    const { get, submit, window } = setup('HISTORICAL');
    assert.equal(submit(), false);
    window.events.pageshow();
    assert.equal(get('import-submit').disabled, false);
    assert.equal(submit(), false);
});

test('shared animation initialization tolerates an unavailable animation library', () => {
    const template = readFileSync('templates/base.html', 'utf8');
    const inline = [...template.matchAll(/<script>([\s\S]*?)<\/script>/g)]
        .map(match => match[1]).find(code => code.includes('AOS.init'));
    const code = inline.replace(/{%[\s\S]*?%}/g, '');
    assert.doesNotThrow(() => runInNewContext(code, {
        document: { addEventListener(type, fn) { if (type === 'DOMContentLoaded') fn(); }, getElementById: () => null },
        window: { addEventListener() {} },
        setTimeout() {}, clearTimeout() {}, clearInterval() {},
    }));
    assert.ok(!template.includes('enhanceDropdowns'));
});
