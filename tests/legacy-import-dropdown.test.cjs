const { test } = require('node:test');
const assert = require('node:assert/strict');
const { readFileSync } = require('node:fs');
const { runInNewContext } = require('node:vm');

const script = readFileSync('static/js/legacy-import.js', 'utf8');
const flush = () => new Promise(resolve => setImmediate(resolve));

class ClassList {
    constructor(owner, initial = '') {
        this.owner = owner;
        this.set = new Set(initial.split(/\s+/).filter(Boolean));
    }
    _sync() { this.owner._className = Array.from(this.set).join(' '); }
    add(...tokens) { tokens.filter(Boolean).forEach(t => this.set.add(t)); this._sync(); }
    remove(...tokens) { tokens.filter(Boolean).forEach(t => this.set.delete(t)); this._sync(); }
    contains(token) { return this.set.has(token); }
    toggle(token, force) {
        const shouldAdd = force === undefined ? !this.set.has(token) : Boolean(force);
        if (shouldAdd) this.set.add(token);
        else this.set.delete(token);
        this._sync();
        return shouldAdd;
    }
}

function splitSelectors(group) {
    const parts = [];
    let depth = 0;
    let quote = null;
    let cur = '';
    for (const ch of group) {
        if (quote) {
            if (ch === quote) quote = null;
        } else if (ch === '"' || ch === "'") {
            quote = ch;
        } else if (ch === '[' || ch === '(') {
            depth += 1;
        } else if (ch === ']' || ch === ')') {
            depth = Math.max(0, depth - 1);
        } else if (ch === ',' && depth === 0) {
            if (cur.trim()) parts.push(cur.trim());
            cur = '';
            continue;
        }
        cur += ch;
    }
    if (cur.trim()) parts.push(cur.trim());
    return parts;
}

function matchesCompound(el, compound) {
    if (!el || el.nodeType !== 1) return false;
    let rest = compound.trim();
    if (rest.startsWith(':scope')) {
        rest = rest.slice(':scope'.length).trim();
        if (!rest) return true;
    }

    const idMatch = rest.match(/^#([A-Za-z0-9_-]+)/);
    if (idMatch) {
        if (el.id !== idMatch[1]) return false;
        rest = rest.slice(idMatch[0].length);
    } else {
        const tagMatch = rest.match(/^[A-Za-z0-9-]+/);
        if (tagMatch) {
            if (el.tagName !== tagMatch[0].toLowerCase()) return false;
            rest = rest.slice(tagMatch[0].length);
        }
    }

    while (rest.length > 0) {
        if (rest.startsWith('.')) {
            const clsMatch = rest.match(/^\.([A-Za-z0-9_-]+)/);
            if (!clsMatch || !el.classList.contains(clsMatch[1])) return false;
            rest = rest.slice(clsMatch[0].length);
            continue;
        }
        if (rest.startsWith('#')) {
            const innerId = rest.match(/^#([A-Za-z0-9_-]+)/);
            if (!innerId || el.id !== innerId[1]) return false;
            rest = rest.slice(innerId[0].length);
            continue;
        }
        if (rest.startsWith(':not(')) {
            let depth = 1;
            let i = 5;
            while (i < rest.length && depth > 0) {
                if (rest[i] === '(') depth += 1;
                else if (rest[i] === ')') depth -= 1;
                i += 1;
            }
            const inner = rest.slice(5, i - 1);
            if (matchesSelector(el, inner)) return false;
            rest = rest.slice(i);
            continue;
        }
        if (rest.startsWith(':checked')) {
            if (!el.checked) return false;
            rest = rest.slice(':checked'.length);
            continue;
        }
        if (rest.startsWith(':disabled')) {
            if (!el.disabled) return false;
            rest = rest.slice(':disabled'.length);
            continue;
        }
        if (rest.startsWith('[')) {
            let end = -1;
            let quote = null;
            for (let i = 1; i < rest.length; i += 1) {
                const ch = rest[i];
                if (quote) {
                    if (ch === quote) quote = null;
                } else if (ch === '"' || ch === "'") {
                    quote = ch;
                } else if (ch === ']') {
                    end = i;
                    break;
                }
            }
            if (end < 0) return false;
            const expr = rest.slice(1, end);
            const eq = expr.indexOf('=');
            if (eq < 0) {
                if (!el.hasAttribute(expr.trim())) return false;
            } else {
                const attr = expr.slice(0, eq).trim();
                const val = expr.slice(eq + 1).trim().replace(/^['"]|['"]$/g, '');
                if (el.getAttribute(attr) !== val) return false;
            }
            rest = rest.slice(end + 1);
            continue;
        }
        return false;
    }
    return true;
}

function splitDescendantTokens(sel) {
    const tokens = [];
    let depth = 0;
    let quote = null;
    let cur = '';
    for (const ch of sel.trim()) {
        if (quote) {
            if (ch === quote) quote = null;
            cur += ch;
        } else if (ch === '"' || ch === "'") {
            quote = ch;
            cur += ch;
        } else if (ch === '[' || ch === '(') {
            depth += 1;
            cur += ch;
        } else if (ch === ']' || ch === ')') {
            depth = Math.max(0, depth - 1);
            cur += ch;
        } else if (/\s/.test(ch) && depth === 0) {
            if (cur) {
                tokens.push(cur);
                cur = '';
            }
        } else {
            cur += ch;
        }
    }
    if (cur) tokens.push(cur);
    return tokens;
}

function matchesSelector(el, selectorGroup) {
    return splitSelectors(selectorGroup).some(sel => {
        const clean = sel.replace(/^:scope\s*>\s*/, '');
        const directOnly = /^:scope\s*>/.test(sel);
        if (directOnly) {
            return matchesCompound(el, clean);
        }
        const tokens = splitDescendantTokens(clean);
        let cur = el;
        if (!matchesCompound(cur, tokens[tokens.length - 1])) return false;
        for (let i = tokens.length - 2; i >= 0; i -= 1) {
            let anc = cur.parentElement;
            while (anc && !matchesCompound(anc, tokens[i])) anc = anc.parentElement;
            if (!anc) return false;
            cur = anc;
        }
        return true;
    });
}

class DomElement {
    constructor(tagName, ownerDocument) {
        this.nodeType = 1;
        this.tagName = tagName.toLowerCase();
        this.ownerDocument = ownerDocument;
        this.parentNode = null;
        this.children = [];
        this.attributes = new Map();
        this._text = '';
        this._className = '';
        this.classList = new ClassList(this);
        this.dataset = new Proxy({}, {
            get: (_, prop) => {
                const k = 'data-' + String(prop).replace(/[A-Z]/g, m => '-' + m.toLowerCase());
                return this.attributes.get(k);
            },
            set: (_, prop, val) => {
                const k = 'data-' + String(prop).replace(/[A-Z]/g, m => '-' + m.toLowerCase());
                this.setAttribute(k, String(val));
                return true;
            },
        });
        this._value = '';
        this._disabled = false;
        this._hidden = false;
        this.checked = false;
        this.selected = false;
        this.open = false;
        this.tabIndex = 0;
        this.files = [];
        this._rect = { top: 140, bottom: 184, left: 40, right: 320, width: 280, height: 44 };
        this._listeners = new Map();
    }

    get parentElement() {
        return this.parentNode && this.parentNode.nodeType === 1 && this.parentNode.tagName !== 'document'
            ? this.parentNode
            : null;
    }

    get id() { return this.attributes.get('id') || ''; }
    set id(v) { this.setAttribute('id', v); }

    get type() { return this.attributes.get('type') || ''; }
    set type(v) { this.setAttribute('type', v); }

    get name() { return this.attributes.get('name') || ''; }
    set name(v) { this.setAttribute('name', v); }

    get className() { return this._className; }
    set className(v) {
        this._className = String(v || '');
        this.classList = new ClassList(this, this._className);
    }

    get disabled() { return this._disabled; }
    set disabled(v) {
        this._disabled = Boolean(v);
        if (this._disabled) this.attributes.set('disabled', '');
        else this.attributes.delete('disabled');
    }

    get hidden() { return this._hidden; }
    set hidden(v) {
        this._hidden = Boolean(v);
        if (this._hidden) this.attributes.set('hidden', '');
        else this.attributes.delete('hidden');
    }

    get options() {
        if (this.tagName !== 'select') return [];
        return this.children.filter(c => c.tagName === 'option');
    }

    get selectedOptions() {
        if (this.tagName !== 'select') return [];
        const opts = this.options;
        const explicit = opts.filter(o => o.selected);
        if (explicit.length) return explicit;
        const byVal = opts.find(o => o.value === this._value);
        if (byVal) return [byVal];
        return opts.length ? [opts[0]] : [];
    }

    get value() {
        if (this.tagName === 'select') {
            const sel = this.selectedOptions[0];
            return sel ? sel._value : this._value;
        }
        return this._value;
    }
    set value(v) {
        const s = String(v == null ? '' : v);
        this._value = s;
        if (this.tagName === 'select') {
            this.options.forEach(o => { o.selected = o._value === s; });
        }
    }

    get textContent() {
        return this._text + this.children.map(c => c.textContent).join('');
    }
    set textContent(v) {
        this.children = [];
        this._text = String(v == null ? '' : v);
    }

    setAttribute(name, val) {
        const s = String(val == null ? '' : val);
        this.attributes.set(name, s);
        if (name === 'class') this.className = s;
        else if (name === 'value') this._value = s;
        else if (name === 'disabled') this._disabled = true;
        else if (name === 'hidden') this._hidden = true;
    }

    getAttribute(name) {
        if (name === 'class') return this._className;
        return this.attributes.has(name) ? this.attributes.get(name) : null;
    }

    removeAttribute(name) {
        this.attributes.delete(name);
        if (name === 'disabled') this._disabled = false;
        if (name === 'hidden') this._hidden = false;
    }

    hasAttribute(name) {
        if (name === 'class') return Boolean(this._className);
        return this.attributes.has(name);
    }

    appendChild(child) {
        if (child.parentNode) {
            const idx = child.parentNode.children.indexOf(child);
            if (idx >= 0) child.parentNode.children.splice(idx, 1);
        }
        child.parentNode = this;
        this.children.push(child);
        return child;
    }

    insertBefore(child, ref) {
        if (child.parentNode) {
            const idx = child.parentNode.children.indexOf(child);
            if (idx >= 0) child.parentNode.children.splice(idx, 1);
        }
        child.parentNode = this;
        const pos = ref ? this.children.indexOf(ref) : this.children.length;
        this.children.splice(pos < 0 ? this.children.length : pos, 0, child);
        return child;
    }

    replaceChildren(...nodes) {
        this.children.forEach(c => { c.parentNode = null; });
        this.children = [];
        nodes.forEach(n => this.appendChild(n));
        if (this.tagName === 'select') {
            this._value = this.options[0] ? this.options[0]._value : '';
        }
    }

    add(option) {
        this.appendChild(option);
    }

    remove() {
        if (!this.parentNode) return;
        const idx = this.parentNode.children.indexOf(this);
        if (idx >= 0) this.parentNode.children.splice(idx, 1);
        this.parentNode = null;
    }

    matches(sel) { return matchesSelector(this, sel); }

    closest(sel) {
        let cur = this;
        while (cur && cur.nodeType === 1 && cur.tagName !== 'document') {
            if (cur.matches(sel)) return cur;
            cur = cur.parentNode;
        }
        return null;
    }

    contains(other) {
        let cur = other;
        while (cur) {
            if (cur === this) return true;
            cur = cur.parentNode;
        }
        return false;
    }

    querySelector(sel) { return this.querySelectorAll(sel)[0] || null; }

    querySelectorAll(sel) {
        if (/^:scope\s*>/.test(sel.trim())) {
            const rest = sel.trim().replace(/^:scope\s*>\s*/, '');
            return this.children.filter(c => matchesCompound(c, rest));
        }
        const out = [];
        const visit = node => {
            for (const c of node.children) {
                if (c.matches(sel)) out.push(c);
                visit(c);
            }
        };
        visit(this);
        return out;
    }

    focus() { this.ownerDocument.activeElement = this; }
    scrollIntoView() { this.scrolledIntoView = true; }
    getBoundingClientRect() { return this._rect; }

    addEventListener(type, cb) {
        if (!this._listeners.has(type)) this._listeners.set(type, []);
        this._listeners.get(type).push(cb);
    }

    dispatchEvent(ev) {
        ev.target = ev.target || this;
        let cur = this;
        while (cur) {
            const list = cur._listeners && cur._listeners.get(ev.type);
            if (list) {
                for (const fn of list) {
                    fn.call(cur, ev);
                    if (ev._stopped) return !ev.defaultPrevented;
                }
            }
            if (!ev.bubbles) break;
            cur = cur.parentNode;
        }
        return !ev.defaultPrevented;
    }
}

class SimEvent {
    constructor(type, { bubbles = false, key = '' } = {}) {
        this.type = type;
        this.bubbles = bubbles;
        this.key = key;
        this.defaultPrevented = false;
        this._stopped = false;
        this.target = null;
    }
    preventDefault() { this.defaultPrevented = true; }
    stopPropagation() { this._stopped = true; }
}

function buildLegacyFormEnv({ innerHeight = 900 } = {}) {
    const docRoot = new DomElement('document', null);
    const document = {
        activeElement: null,
        createElement(tag) { return new DomElement(tag, document); },
        createElementNS(_, tag) { return new DomElement(tag, document); },
        getElementById(id) { return docRoot.querySelector('#' + id); },
        querySelector(sel) { return docRoot.querySelector(sel); },
        querySelectorAll(sel) { return docRoot.querySelectorAll(sel); },
        addEventListener(type, cb) { docRoot.addEventListener(type, cb); },
        dispatchEvent(ev) { return docRoot.dispatchEvent(ev); },
    };
    docRoot.ownerDocument = document;

    const body = document.createElement('body');
    docRoot.appendChild(body);

    const form = document.createElement('form');
    form.id = 'legacy-import-form';
    form.setAttribute('data-native-select', '');
    form.dataset.collegesUrl = '/ajax/colleges/';
    form.dataset.departmentsUrl = '/ajax/departments/';
    body.appendChild(form);

    const makeOption = (label, value, selected = false) => {
        const opt = document.createElement('option');
        opt.value = value;
        opt.textContent = label;
        opt.selected = selected;
        return opt;
    };

    const makeSelectField = (parent, id, name, labelText, choices, initialValue = '') => {
        const field = document.createElement('div');
        field.className = 'legacy-field';
        const label = document.createElement('label');
        label.setAttribute('for', id);
        label.textContent = labelText;
        const select = document.createElement('select');
        select.id = id;
        select.name = name;
        select.className = 'legacy-input';
        choices.forEach(([val, text]) => select.appendChild(makeOption(text, val, val === initialValue)));
        select.value = initialValue;
        field.appendChild(label);
        field.appendChild(select);
        parent.appendChild(field);
        return { field, label, select };
    };

    // Card 1: Activity state radios + stage selects
    const stageCard = document.createElement('section');
    stageCard.className = 'legacy-card';
    form.appendChild(stageCard);

    const stateFieldset = document.createElement('fieldset');
    stateFieldset.id = 'id_activity_state';
    stageCard.appendChild(stateFieldset);
    const radios = {};
    for (const val of ['HISTORICAL', 'MOA_PENDING', 'ONGOING', 'COMPLETED']) {
        const r = document.createElement('input');
        r.type = 'radio';
        r.name = 'activity_state';
        r.value = val;
        r.checked = val === 'HISTORICAL';
        radios[val] = r;
        stateFieldset.appendChild(r);
    }

    const histWrap = document.createElement('div');
    histWrap.id = 'historical-status-field';
    histWrap.className = 'legacy-stage-detail';
    stageCard.appendChild(histWrap);
    makeSelectField(histWrap, 'id_proposal_status', 'proposal_status', 'Original proposal status', [
        ['DRAFTING', 'Drafting'],
        ['APPROVED', 'Approved / Claiming'],
        ['COMPLETED', 'Completed'],
    ], 'APPROVED');

    const moaWrap = document.createElement('div');
    moaWrap.id = 'moa-stage-field';
    moaWrap.className = 'legacy-stage-detail';
    stageCard.appendChild(moaWrap);
    makeSelectField(moaWrap, 'id_moa_stage', 'moa_stage', 'Current MOA stage', [
        ['NOT_STARTED', 'Not Started'],
        ['DRAFT', 'Drafting MOA'],
        ['LEGAL_REVIEW', 'Legal Review'],
    ], 'NOT_STARTED');

    const implWrap = document.createElement('div');
    implWrap.id = 'implementation-stage-field';
    implWrap.className = 'legacy-stage-detail';
    stageCard.appendChild(implWrap);
    makeSelectField(implWrap, 'id_implementation_stage', 'implementation_stage', 'Current implementation stage', [
        ['IMPLEMENTATION', 'Implementation of Extension Activity'],
        ['MONITORING', 'Monitoring and Evaluation'],
    ], 'IMPLEMENTATION');

    // Card 2: Details, organization cascade, and optional details
    const detailsCard = document.createElement('section');
    detailsCard.className = 'legacy-card';
    form.appendChild(detailsCard);

    const titleInput = document.createElement('input');
    titleInput.id = 'id_title';
    titleInput.type = 'text';
    detailsCard.appendChild(titleInput);

    makeSelectField(detailsCard, 'id_extension_type', 'extension_type', 'Extension type', [
        ['', 'Choose extension type'],
        ['COMMUNITY', 'Community-based'],
        ['REQUEST', 'Request-based'],
    ], '');
    makeSelectField(detailsCard, 'id_scope_type', 'scope_type', 'Scope', [
        ['', 'Choose scope'],
        ['PROJECT', 'Project'],
        ['PROGRAM', 'Program'],
    ], '');
    makeSelectField(detailsCard, 'id_campus', 'campus', 'Campus', [
        ['', 'Choose campus'],
        ['Santa Maria Campus', 'Santa Maria Campus'],
        ['Candon Campus', 'Candon Campus'],
    ], '');
    makeSelectField(detailsCard, 'id_college', 'college', 'College', [
        ['', 'Choose college'],
    ], '');
    makeSelectField(detailsCard, 'id_department', 'department', 'Department', [
        ['', 'Choose department'],
    ], '');

    const unitFeedback = document.createElement('p');
    unitFeedback.id = 'unit-feedback';
    detailsCard.appendChild(unitFeedback);
    const unitRetry = document.createElement('button');
    unitRetry.id = 'unit-retry';
    unitRetry.hidden = true;
    detailsCard.appendChild(unitRetry);

    const optionalDetails = document.createElement('details');
    optionalDetails.className = 'legacy-optional';
    optionalDetails.open = true;
    detailsCard.appendChild(optionalDetails);
    makeSelectField(optionalDetails, 'id_estimated_month', 'estimated_month', 'Estimated month', [
        ['', 'Choose month'],
        ['January', 'January'],
        ['February', 'February'],
    ], '');

    // Accounts + files + review stubs required by legacy-import.js
    const accountTools = document.createElement('div');
    accountTools.className = 'legacy-account-tools';
    accountTools.hidden = true;
    form.appendChild(accountTools);

    for (const [id, tag] of [
        ['account-search', 'input'],
        ['show-selected', 'button'],
        ['assignment-help', 'p'],
        ['selected-count', 'span'],
        ['account-empty', 'p'],
        ['assignment-error', 'p'],
        ['document-guidance', 'p'],
        ['live-review', 'div'],
        ['review-title', 'p'],
        ['review-campus', 'p'],
        ['review-reporting', 'p'],
        ['review-accounts', 'dd'],
        ['review-files', 'dd'],
        ['import-submit', 'button'],
    ]) {
        const el = document.createElement(tag);
        el.id = id;
        form.appendChild(el);
    }

    for (const id of ['review-proposal', 'review-moa', 'review-implementation']) {
        const li = document.createElement('li');
        const span = document.createElement('span');
        span.id = id;
        li.appendChild(span);
        form.appendChild(li);
    }

    for (const [wrapperId, inputId, tag] of [
        ['moa-file-field', 'id_moa_draft_file', 'input'],
        ['terminal-report-field', 'id_terminal_report_file', 'input'],
        ['photo-documentation-field', 'id_documentation_photos', 'input'],
    ]) {
        const w = document.createElement('div');
        w.id = wrapperId;
        const inp = document.createElement(tag);
        inp.id = inputId;
        inp.type = 'file';
        w.appendChild(inp);
        if (wrapperId === 'photo-documentation-field') {
            const cap = document.createElement('input');
            cap.id = 'id_documentation_caption';
            cap.type = 'text';
            w.appendChild(cap);
        }
        form.appendChild(w);
    }
    for (const fileId of ['id_legacy_proposal_file', 'id_attachments']) {
        const inp = document.createElement('input');
        inp.id = fileId;
        inp.type = 'file';
        form.appendChild(inp);
    }

    const outsideBtn = document.createElement('button');
    outsideBtn.type = 'button';
    body.appendChild(outsideBtn);

    const requests = [];
    const windowObj = new DomElement('window', document);
    windowObj.innerHeight = innerHeight;
    windowObj.Event = SimEvent;

    function OptionCtor(label, value) {
        return makeOption(label, value, false);
    }

    runInNewContext(script, {
        document,
        window: windowObj,
        Event: SimEvent,
        Option: OptionCtor,
        AbortController,
        URLSearchParams,
        fetch: (url, options) => new Promise((resolve, reject) => {
            requests.push({
                url,
                options,
                resolve: (data, ok = true) => resolve({ ok, json: async () => data }),
                reject,
            });
        }),
    });

    const click = el => el.dispatchEvent(new SimEvent('click', { bubbles: true }));
    const keydown = (el, key) => {
        const ev = new SimEvent('keydown', { bubbles: true, key });
        el.dispatchEvent(ev);
        return ev;
    };
    const dropdownFor = id => document.getElementById(id).closest('[data-li-dropdown]');

    return { document, window: windowObj, form, radios, optionalDetails, outsideBtn, requests, click, keydown, dropdownFor };
}

test('enhances all 9 legacy upload selects into single-click popover dropdowns without flicker', () => {
    const { form, click, dropdownFor } = buildLegacyFormEnv();
    const enhanced = form.querySelectorAll('[data-li-dropdown]');
    assert.equal(enhanced.length, 9, 'all 9 selects on Legacy Upload are enhanced');

    const extDd = dropdownFor('id_extension_type');
    const trigger = extDd.querySelector('[data-li-dropdown-trigger]');
    const labelSpan = extDd.querySelector('[data-li-dropdown-label]');
    const chevron = extDd.querySelector('[data-li-dropdown-chevron]');
    const menu = extDd.querySelector('[data-li-dropdown-menu]');

    assert.equal(labelSpan.textContent, 'Choose extension type');
    assert.equal(trigger.dataset.placeholder, 'true');
    assert.equal(menu.hidden, true);

    // Click label span -> opens
    click(labelSpan);
    assert.equal(menu.hidden, false);
    assert.equal(trigger.getAttribute('aria-expanded'), 'true');
    assert.equal(extDd.classList.contains('is-open'), true);

    // Click chevron while open -> closes cleanly without re-opening
    click(chevron);
    assert.equal(menu.hidden, true);
    assert.equal(trigger.getAttribute('aria-expanded'), 'false');
    assert.equal(extDd.classList.contains('is-open'), false);

    // Select Community-based -> updates underlying select, label, and placeholder state
    click(trigger);
    click(menu.querySelector('[data-li-dropdown-option="COMMUNITY"]'));
    assert.equal(form.querySelector('#id_extension_type').value, 'COMMUNITY');
    assert.equal(labelSpan.textContent, 'Community-based');
    assert.equal(trigger.dataset.placeholder, 'false');
    assert.equal(menu.hidden, true);
});

test('cascading Campus -> College -> Department AJAX updates custom popover menus and disabled states', async () => {
    const { document, requests, click, dropdownFor } = buildLegacyFormEnv();
    const campusDd = dropdownFor('id_campus');
    const collegeDd = dropdownFor('id_college');
    const deptDd = dropdownFor('id_department');

    const collegeTrigger = collegeDd.querySelector('[data-li-dropdown-trigger]');
    const deptTrigger = deptDd.querySelector('[data-li-dropdown-trigger]');

    // Initially disabled before a campus is chosen
    assert.equal(collegeTrigger.disabled, true);
    assert.equal(deptTrigger.disabled, true);
    click(collegeTrigger);
    assert.equal(collegeDd.querySelector('[data-li-dropdown-menu]').hidden, true);

    // Pick Santa Maria Campus from custom popover
    click(campusDd.querySelector('[data-li-dropdown-trigger]'));
    click(campusDd.querySelector('[data-li-dropdown-option="Santa Maria Campus"]'));
    assert.equal(document.getElementById('review-campus').textContent, 'Santa Maria Campus');
    assert.equal(requests.length, 1);

    requests[0].resolve({
        colleges: [{ value: 'College of Agriculture', label: 'College of Agriculture' }],
    });
    await flush();
    assert.equal(requests.length, 2);
    requests[1].resolve({
        departments: [{ value: 'Agronomy', label: 'Agronomy' }],
    });
    await flush();

    // College and Department custom triggers are now enabled and populated!
    assert.equal(collegeTrigger.disabled, false);
    assert.equal(deptTrigger.disabled, false);

    click(collegeTrigger);
    const collegeOpt = collegeDd.querySelector('[data-li-dropdown-option="College of Agriculture"]');
    assert.ok(collegeOpt, 'fetched college appears in custom popover menu');
    click(collegeOpt);
    assert.equal(document.getElementById('id_college').value, 'College of Agriculture');

    // Picking college fetches college-scoped departments and refreshes Department popover
    assert.equal(requests.length, 3);
    requests[2].resolve({
        departments: [{ value: 'BS Agriculture', label: 'BS Agriculture' }],
    });
    await flush();

    click(deptTrigger);
    const deptOpt = deptDd.querySelector('[data-li-dropdown-option="BS Agriculture"]');
    assert.ok(deptOpt, 'fetched department appears in custom popover menu');
    click(deptOpt);
    assert.equal(document.getElementById('id_department').value, 'BS Agriculture');
    assert.equal(deptDd.querySelector('[data-li-dropdown-label]').textContent, 'BS Agriculture');
});

test('stage switching, upward viewport placement, keyboard navigation, and details toggle work cleanly', () => {
    const { document, form, radios, optionalDetails, outsideBtn, click, keydown, dropdownFor } = buildLegacyFormEnv({ innerHeight: 500 });
    const propDd = dropdownFor('id_proposal_status');
    const moaDd = dropdownFor('id_moa_stage');
    const monthDd = dropdownFor('id_estimated_month');

    // Open proposal status, then switch stage to MOA_PENDING -> closes & disables proposal status, enables MOA stage
    click(propDd.querySelector('[data-li-dropdown-trigger]'));
    assert.equal(propDd.querySelector('[data-li-dropdown-menu]').hidden, false);

    radios.HISTORICAL.checked = false;
    radios.MOA_PENDING.checked = true;
    form.dispatchEvent(new SimEvent('change', { bubbles: true }));

    assert.equal(propDd.querySelector('[data-li-dropdown-menu]').hidden, true);
    assert.equal(propDd.querySelector('[data-li-dropdown-trigger]').disabled, true);
    assert.equal(moaDd.querySelector('[data-li-dropdown-trigger]').disabled, false);

    // Keyboard navigation on MOA stage + upward placement near bottom of viewport
    const moaTrigger = moaDd.querySelector('[data-li-dropdown-trigger]');
    const moaMenu = moaDd.querySelector('[data-li-dropdown-menu]');
    moaTrigger._rect = { top: 430, bottom: 474, left: 40, right: 320, width: 280, height: 44 };

    keydown(moaTrigger, 'ArrowDown');
    assert.equal(moaMenu.hidden, false);
    assert.equal(moaMenu.classList.contains('is-upward'), true);

    keydown(document.activeElement, 'ArrowDown'); // Not Started -> Drafting MOA
    keydown(document.activeElement, 'ArrowDown'); // Drafting MOA -> Legal Review
    keydown(document.activeElement, 'Enter');
    assert.equal(document.getElementById('id_moa_stage').value, 'LEGAL_REVIEW');
    assert.equal(document.getElementById('review-moa').textContent, 'Legal Review');
    assert.equal(moaMenu.hidden, true);
    assert.equal(document.activeElement, moaTrigger);

    // Closing optional <details> closes open Estimated month dropdown inside it
    click(monthDd.querySelector('[data-li-dropdown-trigger]'));
    assert.equal(monthDd.querySelector('[data-li-dropdown-menu]').hidden, false);
    optionalDetails.open = false;
    optionalDetails.dispatchEvent(new SimEvent('toggle'));
    assert.equal(monthDd.querySelector('[data-li-dropdown-menu]').hidden, true);

    // Outside click closes any open dropdown
    click(moaTrigger);
    assert.equal(moaMenu.hidden, false);
    click(outsideBtn);
    assert.equal(moaMenu.hidden, true);
});
