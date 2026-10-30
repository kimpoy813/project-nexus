const { test } = require('node:test');
const assert = require('node:assert/strict');
const { readFileSync } = require('node:fs');
const { runInNewContext } = require('node:vm');

const rawTemplate = readFileSync('accounts/templates/dashboard/admin/_builder_script.html', 'utf8');

function compileBuilderScript() {
    const fieldTypes = [
        ['TEXT', 'Short Text'],
        ['TEXTAREA', 'Long Text'],
        ['NUMBER', 'Number'],
        ['DATE', 'Date'],
        ['EMAIL', 'Email'],
        ['SELECT', 'Dropdown'],
        ['CHECKBOX', 'Checkbox'],
        ['FILE', 'File Upload'],
    ];
    const mapChoices = [
        ['full_name', 'Name'],
        ['designation', 'Position / Designation'],
        ['specialization', 'Specialization'],
    ];

    let rendered = rawTemplate
        .replace(/\{%\s*comment\s*%\}[\s\S]*?\{%\s*endcomment\s*%\}/g, '')
        .replace(
            /\{%\s*for value,\s*label in field_type_choices\s*%\}[\s\S]*?\{%\s*endfor\s*%\}/,
            fieldTypes.map(([v, l]) => `{ value: "${v}", label: "${l}" }`).join(',\n  ')
        )
        .replace(/\{%\s*if proponent_map_choices\s*%\},\{%\s*endif\s*%\}/, ',')
        .replace(
            /\{%\s*for value,\s*label in proponent_map_choices\s*%\}[\s\S]*?\{%\s*endfor\s*%\}/,
            mapChoices.map(([v, l]) => `{ value: "${v}", label: "${l}" }`).join(',\n  ')
        );

    return rendered.match(/<script>([\s\S]*?)<\/script>/)[1];
}

const compiledScript = compileBuilderScript();

class ClassList {
    constructor(owner, initial = '') {
        this.owner = owner;
        this.set = new Set(initial.split(/\s+/).filter(Boolean));
    }
    _sync() {
        this.owner._className = Array.from(this.set).join(' ');
    }
    add(...tokens) {
        tokens.filter(Boolean).forEach(t => this.set.add(t));
        this._sync();
    }
    remove(...tokens) {
        tokens.filter(Boolean).forEach(t => this.set.delete(t));
        this._sync();
    }
    contains(token) {
        return this.set.has(token);
    }
    toggle(token, force) {
        const shouldAdd = force === undefined ? !this.set.has(token) : Boolean(force);
        if (shouldAdd) this.set.add(token);
        else this.set.delete(token);
        this._sync();
        return shouldAdd;
    }
}

function splitTopLevelSelectors(selectorGroup) {
    const parts = [];
    let depth = 0;
    let current = '';
    for (const ch of selectorGroup) {
        if (ch === '[') depth += 1;
        else if (ch === ']') depth = Math.max(0, depth - 1);
        if (ch === ',' && depth === 0) {
            if (current.trim()) parts.push(current.trim());
            current = '';
        } else {
            current += ch;
        }
    }
    if (current.trim()) parts.push(current.trim());
    return parts;
}

function matchesSingleCompound(el, compound) {
    if (!el || el.nodeType !== 1) return false;
    let rest = compound.trim();

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
            const clsMatch = rest.match(/^\.([A-Za-z0-9_:/\[\].%-]+)/);
            if (!clsMatch) return false;
            if (!el.classList.contains(clsMatch[1])) return false;
            rest = rest.slice(clsMatch[0].length);
            continue;
        }
        if (rest.startsWith('#')) {
            const innerId = rest.match(/^#([A-Za-z0-9_-]+)/);
            if (!innerId || el.id !== innerId[1]) return false;
            rest = rest.slice(innerId[0].length);
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
            const eqIdx = expr.indexOf('=');
            if (eqIdx < 0) {
                if (!el.hasAttribute(expr.trim())) return false;
            } else {
                const attrName = expr.slice(0, eqIdx).trim();
                const rawVal = expr.slice(eqIdx + 1).trim().replace(/^['"]|['"]$/g, '');
                if (el.getAttribute(attrName) !== rawVal) return false;
            }
            rest = rest.slice(end + 1);
            continue;
        }
        return false;
    }
    return true;
}

function matchesSelector(el, selectorGroup) {
    return splitTopLevelSelectors(selectorGroup).some(sel => {
        const chain = sel.trim().split(/\s+/);
        let cursor = el;
        if (!matchesSingleCompound(cursor, chain[chain.length - 1])) return false;
        for (let i = chain.length - 2; i >= 0; i -= 1) {
            let ancestor = cursor.parentElement;
            while (ancestor && !matchesSingleCompound(ancestor, chain[i])) {
                ancestor = ancestor.parentElement;
            }
            if (!ancestor) return false;
            cursor = ancestor;
        }
        return true;
    });
}

function decodeEntities(str) {
    return String(str)
        .replace(/&quot;/g, '"')
        .replace(/&#39;/g, "'")
        .replace(/&lt;/g, '<')
        .replace(/&gt;/g, '>')
        .replace(/&amp;/g, '&');
}

function parseHTMLFragment(html, ownerDocument) {
    const voidTags = new Set(['input', 'br', 'hr', 'img', 'meta', 'link', 'path', 'use']);
    const root = new MiniElement('fragment', ownerDocument);
    const stack = [root];
    const tokenRe = /<!--[\s\S]*?-->|<\/([A-Za-z0-9:-]+)\s*>|<([A-Za-z0-9:-]+)([\s\S]*?)(\/?)>|([^<]+)/g;
    let match;
    while ((match = tokenRe.exec(html)) !== null) {
        if (match[1]) {
            const closeTag = match[1].toLowerCase();
            while (stack.length > 1 && stack[stack.length - 1].tagName !== closeTag) {
                stack.pop();
            }
            if (stack.length > 1) stack.pop();
        } else if (match[2]) {
            const tag = match[2].toLowerCase();
            const attrText = match[3] || '';
            const selfClosing = Boolean(match[4]) || voidTags.has(tag);
            const el = ownerDocument.createElement(tag);
            const attrRe = /([A-Za-z0-9_:@-]+)(?:\s*=\s*(?:"([^"]*)"|'([^']*)'|([^\s"'=<>`]+)))?/g;
            let am;
            while ((am = attrRe.exec(attrText)) !== null) {
                const name = am[1];
                const val = am[2] !== undefined ? am[2] : (am[3] !== undefined ? am[3] : (am[4] !== undefined ? am[4] : ''));
                el.setAttribute(name, decodeEntities(val));
            }
            stack[stack.length - 1].appendChild(el);
            if (!selfClosing) stack.push(el);
        } else if (match[5]) {
            const text = decodeEntities(match[5]);
            if (text.trim()) {
                stack[stack.length - 1]._textNodes.push(text);
            }
        }
    }
    return root.children.slice();
}

class MiniElement {
    constructor(tagName, ownerDocument) {
        this.nodeType = 1;
        this.tagName = tagName.toLowerCase();
        this.ownerDocument = ownerDocument;
        this.parentNode = null;
        this.children = [];
        this.attributes = new Map();
        this._textNodes = [];
        this._className = '';
        this.classList = new ClassList(this);
        this.dataset = new Proxy({}, {
            get: (_, prop) => {
                const kebab = 'data-' + String(prop).replace(/[A-Z]/g, m => '-' + m.toLowerCase());
                return this.attributes.get(kebab);
            },
            set: (_, prop, val) => {
                const kebab = 'data-' + String(prop).replace(/[A-Z]/g, m => '-' + m.toLowerCase());
                this.setAttribute(kebab, String(val));
                return true;
            },
        });
        this._value = '';
        this._hidden = false;
        this._rect = { top: 120, bottom: 164, left: 40, right: 260, width: 220, height: 44 };
        this._listeners = new Map();
    }

    get parentElement() {
        return this.parentNode && this.parentNode.nodeType === 1 && this.parentNode.tagName !== 'document'
            ? this.parentNode
            : null;
    }

    get id() { return this.attributes.get('id') || ''; }
    set id(v) { this.setAttribute('id', v); }

    get className() { return this._className; }
    set className(v) {
        this._className = String(v || '');
        this.classList = new ClassList(this, this._className);
    }

    get value() { return this._value; }
    set value(v) { this._value = String(v == null ? '' : v); }

    get hidden() { return this._hidden; }
    set hidden(v) {
        this._hidden = Boolean(v);
        if (this._hidden) this.attributes.set('hidden', '');
        else this.attributes.delete('hidden');
    }

    get textContent() {
        const own = this._textNodes.join('');
        const sub = this.children.map(c => c.textContent).join('');
        return own + sub;
    }
    set textContent(v) {
        this.children = [];
        this._textNodes = [String(v == null ? '' : v)];
    }

    set innerHTML(html) {
        this.children = [];
        this._textNodes = [];
        for (const child of parseHTMLFragment(html, this.ownerDocument)) {
            this.appendChild(child);
        }
    }

    get previousElementSibling() {
        if (!this.parentNode) return null;
        const idx = this.parentNode.children.indexOf(this);
        return idx > 0 ? this.parentNode.children[idx - 1] : null;
    }

    get nextElementSibling() {
        if (!this.parentNode) return null;
        const idx = this.parentNode.children.indexOf(this);
        return idx >= 0 && idx < this.parentNode.children.length - 1
            ? this.parentNode.children[idx + 1]
            : null;
    }

    setAttribute(name, val) {
        const s = String(val == null ? '' : val);
        this.attributes.set(name, s);
        if (name === 'class') this.className = s;
        if (name === 'value') this._value = s;
        if (name === 'hidden') this._hidden = true;
    }

    getAttribute(name) {
        if (name === 'class') return this._className;
        return this.attributes.has(name) ? this.attributes.get(name) : null;
    }

    hasAttribute(name) {
        if (name === 'class') return Boolean(this._className);
        return this.attributes.has(name);
    }

    appendChild(child) {
        if (child.parentNode) {
            const prevIdx = child.parentNode.children.indexOf(child);
            if (prevIdx >= 0) child.parentNode.children.splice(prevIdx, 1);
        }
        child.parentNode = this;
        this.children.push(child);
        return child;
    }

    insertBefore(child, reference) {
        if (child.parentNode) {
            const prevIdx = child.parentNode.children.indexOf(child);
            if (prevIdx >= 0) child.parentNode.children.splice(prevIdx, 1);
        }
        child.parentNode = this;
        const idx = reference ? this.children.indexOf(reference) : this.children.length;
        this.children.splice(idx < 0 ? this.children.length : idx, 0, child);
        return child;
    }

    remove() {
        if (!this.parentNode) return;
        const idx = this.parentNode.children.indexOf(this);
        if (idx >= 0) this.parentNode.children.splice(idx, 1);
        this.parentNode = null;
    }

    matches(selector) {
        return matchesSelector(this, selector);
    }

    closest(selector) {
        let cur = this;
        while (cur && cur.nodeType === 1 && cur.tagName !== 'document') {
            if (cur.matches(selector)) return cur;
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

    querySelector(selector) {
        return this.querySelectorAll(selector)[0] || null;
    }

    querySelectorAll(selector) {
        const out = [];
        const visit = node => {
            for (const child of node.children) {
                if (child.matches(selector)) out.push(child);
                visit(child);
            }
        };
        visit(this);
        return out;
    }

    focus() {
        this.ownerDocument.activeElement = this;
    }

    getBoundingClientRect() {
        return this._rect;
    }

    addEventListener(type, cb) {
        if (!this._listeners.has(type)) this._listeners.set(type, []);
        this._listeners.get(type).push(cb);
    }

    dispatchEvent(event) {
        event.target = event.target || this;
        let cur = this;
        while (cur) {
            const cbs = cur._listeners && cur._listeners.get(event.type);
            if (cbs) {
                for (const cb of cbs) {
                    cb.call(cur, event);
                    if (event._stopped) return !event.defaultPrevented;
                }
            }
            if (!event.bubbles) break;
            cur = cur.parentNode;
        }
        return !event.defaultPrevented;
    }
}

class CustomEventObj {
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

function setupWizardEditor({ proponentStep = false, innerHeight = 900 } = {}) {
    const docRoot = new MiniElement('document', null);
    const document = {
        readyState: 'complete',
        activeElement: null,
        body: null,
        createElement(tag) { return new MiniElement(tag, document); },
        getElementById(id) { return docRoot.querySelector('#' + id); },
        querySelector(sel) { return docRoot.querySelector(sel); },
        querySelectorAll(sel) { return docRoot.querySelectorAll(sel); },
        addEventListener(type, cb) { docRoot.addEventListener(type, cb); },
        dispatchEvent(ev) { return docRoot.dispatchEvent(ev); },
    };
    docRoot.ownerDocument = document;
    const body = document.createElement('body');
    docRoot.appendChild(body);
    document.body = body;

    const fieldRows = document.createElement('div');
    fieldRows.setAttribute('id', 'fieldRows');
    fieldRows.setAttribute('data-proponent-step', proponentStep ? 'true' : 'false');
    body.appendChild(fieldRows);

    const outsideButton = document.createElement('button');
    outsideButton.setAttribute('type', 'button');
    body.appendChild(outsideButton);

    const window = {
        innerHeight,
        Event: CustomEventObj,
        document,
    };

    const sandbox = {
        window,
        document,
        Event: CustomEventObj,
        Array,
        Boolean,
        String,
        Math,
    };
    runInNewContext(compiledScript, sandbox);

    const click = el => el.dispatchEvent(new CustomEventObj('click', { bubbles: true }));
    const keydown = (el, key) => {
        const ev = new CustomEventObj('keydown', { bubbles: true, key });
        el.dispatchEvent(ev);
        return ev;
    };

    return { document, window, sandbox, fieldRows, outsideButton, click, keydown };
}

test('clicking anywhere on trigger, label, or chevron opens and closes cleanly without flicker', () => {
    const { sandbox, click } = setupWizardEditor();
    const row = sandbox.addFieldRow();
    const typeDropdown = row.querySelectorAll('[data-nx-builder-dropdown]')[0];
    const trigger = typeDropdown.querySelector('[data-nx-dropdown-trigger]');
    const labelSpan = typeDropdown.querySelector('[data-nx-dropdown-label]');
    const chevronSvg = typeDropdown.querySelector('[data-nx-dropdown-chevron]');
    const menu = typeDropdown.querySelector('[data-nx-dropdown-menu]');

    assert.equal(labelSpan.textContent.trim(), 'Short Text');
    assert.equal(menu.hidden, true);
    assert.equal(trigger.getAttribute('aria-expanded'), 'false');

    // Click inner label span -> opens
    click(labelSpan);
    assert.equal(menu.hidden, false);
    assert.equal(menu.classList.contains('hidden'), false);
    assert.equal(trigger.getAttribute('aria-expanded'), 'true');
    assert.equal(chevronSvg.classList.contains('rotate-180'), true);
    assert.equal(row.classList.contains('z-30'), true);

    // Click chevron SVG while open -> closes cleanly (no light-dismiss re-open!)
    click(chevronSvg);
    assert.equal(menu.hidden, true);
    assert.equal(menu.classList.contains('hidden'), true);
    assert.equal(trigger.getAttribute('aria-expanded'), 'false');
    assert.equal(chevronSvg.classList.contains('rotate-180'), false);
    assert.equal(row.classList.contains('z-30'), false);
});

test('selecting Dropdown toggles choices-cell and updates hidden field_type[] value', () => {
    const { sandbox, click } = setupWizardEditor();
    const row = sandbox.addFieldRow();
    const typeDropdown = row.querySelectorAll('[data-nx-builder-dropdown]')[0];
    const hiddenInput = row.querySelector('input[name="field_type[]"]');
    const choicesCell = row.querySelector('.choices-cell');
    const trigger = typeDropdown.querySelector('[data-nx-dropdown-trigger]');
    const labelSpan = typeDropdown.querySelector('[data-nx-dropdown-label]');

    let changeCount = 0;
    hiddenInput.addEventListener('change', () => { changeCount += 1; });

    assert.equal(hiddenInput.value, 'TEXT');
    assert.equal(choicesCell.classList.contains('hidden'), true);

    click(trigger);
    const selectOpt = typeDropdown.querySelector('[data-nx-dropdown-option="SELECT"]');
    click(selectOpt);

    assert.equal(hiddenInput.value, 'SELECT');
    assert.equal(labelSpan.textContent.trim(), 'Dropdown');
    assert.equal(selectOpt.getAttribute('aria-selected'), 'true');
    assert.equal(choicesCell.classList.contains('hidden'), false, 'choices box appears for Dropdown fields');
    assert.equal(typeDropdown.querySelector('[data-nx-dropdown-menu]').hidden, true);
    assert.equal(changeCount, 1);

    // Switch back to File Upload -> choices-cell hides again
    click(trigger);
    click(typeDropdown.querySelector('[data-nx-dropdown-option="FILE"]'));
    assert.equal(hiddenInput.value, 'FILE');
    assert.equal(labelSpan.textContent.trim(), 'File Upload');
    assert.equal(choicesCell.classList.contains('hidden'), true);
});

test('opening another dropdown closes the first, and Step 3 proponent mapping works cleanly', () => {
    const { sandbox, outsideButton, click } = setupWizardEditor({ proponentStep: true });
    const row1 = sandbox.addFieldRow();
    const row2 = sandbox.addFieldRow();

    const mapsCell1 = row1.querySelector('.maps-to-cell');
    assert.equal(mapsCell1.classList.contains('hidden'), false, 'Step 3 reveals proponent mapping dropdown');

    const [typeDd1, mapsDd1] = row1.querySelectorAll('[data-nx-builder-dropdown]');
    const [typeDd2] = row2.querySelectorAll('[data-nx-builder-dropdown]');

    click(typeDd1.querySelector('[data-nx-dropdown-trigger]'));
    assert.equal(typeDd1.querySelector('[data-nx-dropdown-menu]').hidden, false);

    // Opening mapsDd1 closes typeDd1
    click(mapsDd1.querySelector('[data-nx-dropdown-trigger]'));
    assert.equal(typeDd1.querySelector('[data-nx-dropdown-menu]').hidden, true);
    assert.equal(mapsDd1.querySelector('[data-nx-dropdown-menu]').hidden, false);

    // Opening row2 dropdown closes row1 dropdown and moves z-30 elevation to row2
    click(typeDd2.querySelector('[data-nx-dropdown-trigger]'));
    assert.equal(mapsDd1.querySelector('[data-nx-dropdown-menu]').hidden, true);
    assert.equal(row1.classList.contains('z-30'), false);
    assert.equal(row2.classList.contains('z-30'), true);

    // Outside click closes all
    click(outsideButton);
    assert.equal(typeDd2.querySelector('[data-nx-dropdown-menu]').hidden, true);
    assert.equal(row2.classList.contains('z-30'), false);

    // Select Position / Designation in Step 3 maps_to
    click(mapsDd1.querySelector('[data-nx-dropdown-trigger]'));
    click(mapsDd1.querySelector('[data-nx-dropdown-option="designation"]'));
    assert.equal(row1.querySelector('input[name="field_maps_to[]"]').value, 'designation');
    assert.equal(mapsDd1.querySelector('[data-nx-dropdown-label]').textContent.trim(), 'Position / Designation');
});

test('auto-places upward near bottom of viewport, supports keyboard navigation, and handles row reorder', () => {
    const { document, sandbox, click, keydown } = setupWizardEditor({ innerHeight: 500 });
    const row1 = sandbox.addFieldRow();
    const row2 = sandbox.addFieldRow();
    const dd1 = row1.querySelectorAll('[data-nx-builder-dropdown]')[0];
    const trigger1 = dd1.querySelector('[data-nx-dropdown-trigger]');
    const menu1 = dd1.querySelector('[data-nx-dropdown-menu]');

    // Near bottom of 500px viewport -> opens upward
    trigger1._rect = { top: 430, bottom: 474, left: 40, right: 260, width: 220, height: 44 };
    keydown(trigger1, 'ArrowDown');
    assert.equal(menu1.hidden, false);
    assert.equal(menu1.classList.contains('bottom-full'), true);
    assert.equal(menu1.classList.contains('top-full'), false);

    // Navigate down twice (Short Text -> Long Text -> Number) and press Enter
    keydown(document.activeElement, 'ArrowDown');
    keydown(document.activeElement, 'ArrowDown');
    keydown(document.activeElement, 'Enter');
    assert.equal(row1.querySelector('input[name="field_type[]"]').value, 'NUMBER');
    assert.equal(dd1.querySelector('[data-nx-dropdown-label]').textContent.trim(), 'Number');
    assert.equal(menu1.hidden, true);
    assert.equal(document.activeElement, trigger1);

    // Escape closes and restores focus
    trigger1._rect = { top: 80, bottom: 124, left: 40, right: 260, width: 220, height: 44 };
    click(trigger1);
    assert.equal(menu1.classList.contains('top-full'), true);
    keydown(trigger1, 'Escape');
    assert.equal(menu1.hidden, true);

    // Reordering rows closes open menus and preserves each row's selected field_type[]
    click(trigger1);
    click(row2.querySelector('[data-field-move="up"]'));
    assert.equal(menu1.hidden, true);
    const orderedTypes = Array.from(document.querySelectorAll('input[name="field_type[]"]')).map(el => el.value);
    assert.deepEqual(orderedTypes, ['TEXT', 'NUMBER']);
});
