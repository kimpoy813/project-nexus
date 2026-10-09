/*
 * Nested step editor for Extension Processes.
 *
 * One list, unlimited nesting: drag a row by its handle to move it, and drag
 * it sideways to nest it under the step above. Indent/outdent buttons and
 * Tab / Shift+Tab in a description field do the same thing without a mouse.
 *
 * The structure is submitted as four parallel form fields -- `step_ref[]`,
 * `step_id[]`, `step_description[]` and `step_parent[]`. A row's parent is a
 * *reference*, not an id, so a step that has never been saved can still be the
 * parent of one that has not been saved either. `accounts/views/process_steps.py`
 * turns that outline into ProcessStep rows.
 *
 * The planning helpers below are pure and covered by
 * tests/process-steps.test.cjs; everything touching the DOM is a thin wrapper.
 */
(function (global) {
    'use strict';

    // Horizontal distance equal to one nesting level. The stylesheet indents
    // nested lists by the same amount, so pointer maths and pixels agree.
    var INDENT_PX = 28;
    var SORTABLE_SRC = 'https://cdn.jsdelivr.net/npm/sortablejs@1.15.2/Sortable.min.js';

    /* ---------------------------------------------------------------- *
     * Pure helpers                                                     *
     * ---------------------------------------------------------------- */

    function indexOfRef(rows, ref) {
        for (var i = 0; i < rows.length; i++) {
            if (rows[i].ref === ref) return i;
        }
        return -1;
    }

    // Rows are in document order, so a row's whole subtree follows it as the
    // contiguous run of deeper rows.
    function isDescendantOf(rows, index, ancestorIndex) {
        return index > ancestorIndex && rows[index].depth > rows[ancestorIndex].depth;
    }

    function withoutSubtree(rows, ref) {
        var index = indexOfRef(rows, ref);
        if (index < 0) return rows.slice();
        var kept = rows.slice(0, index);
        for (var i = index + 1; i < rows.length; i++) {
            if (isDescendantOf(rows, i, index)) continue;
            kept.push(rows[i]);
        }
        return kept;
    }

    /*
     * Where should a dropped row land?
     *
     * `others` is every row except the one being moved and everything under
     * it, in document order; `insertIndex` is how many of them precede the
     * drop point. Nesting can only ever be one level deeper than the row
     * above, which keeps the outline free of gaps.
     */
    function planDrop(others, insertIndex, dropX, rootLeft, indent) {
        if (typeof dropX !== 'number' || !isFinite(dropX)) return null;
        indent = indent || INDENT_PX;

        if (insertIndex < 0) insertIndex = 0;
        if (insertIndex > others.length) insertIndex = others.length;

        var depth = Math.round((dropX - rootLeft) / indent);
        if (!isFinite(depth) || depth < 0) depth = 0;

        var previous = insertIndex > 0 ? others[insertIndex - 1] : null;
        var maxDepth = previous ? previous.depth + 1 : 0;
        if (depth > maxDepth) depth = maxDepth;

        var parentRef = null;
        if (depth > 0) {
            for (var i = insertIndex - 1; i >= 0; i--) {
                if (others[i].depth === depth - 1) {
                    parentRef = others[i].ref;
                    break;
                }
            }
            if (parentRef === null) depth = 0;
        }

        var beforeRef = null;
        for (var j = insertIndex; j < others.length; j++) {
            if (others[j].depth === depth && (others[j].parentRef || null) === parentRef) {
                beforeRef = others[j].ref;
                break;
            }
        }

        return { depth: depth, parentRef: parentRef, beforeRef: beforeRef };
    }

    // Nest under the row immediately above; appended as its last child.
    function planIndent(rows, ref) {
        var index = indexOfRef(rows, ref);
        if (index <= 0) return null;
        var previous = rows[index - 1];
        return { depth: previous.depth + 1, parentRef: previous.ref, beforeRef: null };
    }

    // Become the next sibling of the current parent.
    function planOutdent(rows, ref) {
        var index = indexOfRef(rows, ref);
        if (index < 0) return null;
        var row = rows[index];
        if (!row.parentRef) return null;

        var parentIndex = indexOfRef(rows, row.parentRef);
        if (parentIndex < 0) {
            // A dangling parent link: bring the row back to the top level.
            return { depth: 0, parentRef: null, beforeRef: null };
        }
        var parent = rows[parentIndex];
        var newParentRef = parent.parentRef || null;
        var newDepth = parent.depth;

        var end = parentIndex;
        for (var i = parentIndex + 1; i < rows.length; i++) {
            if (rows[i].depth <= parent.depth) break;
            end = i;
        }

        var beforeRef = null;
        for (var j = end + 1; j < rows.length; j++) {
            if (isDescendantOf(rows, j, index)) continue;
            if (rows[j].depth === newDepth && (rows[j].parentRef || null) === newParentRef) {
                beforeRef = rows[j].ref;
                break;
            }
        }

        return { depth: newDepth, parentRef: newParentRef, beforeRef: beforeRef };
    }

    var api = {
        INDENT_PX: INDENT_PX,
        indexOfRef: indexOfRef,
        withoutSubtree: withoutSubtree,
        planDrop: planDrop,
        planIndent: planIndent,
        planOutdent: planOutdent,
        init: function (root) { return initEditor(root); },
        initAll: initAll
    };

    if (typeof module !== 'undefined' && module.exports) module.exports = api;
    global.NexusProcessSteps = api;

    /* ---------------------------------------------------------------- *
     * Everything below needs a browser.                                *
     * ---------------------------------------------------------------- */
    if (!global.document) return;

    var document = global.document;
    var groupCounter = 0;
    var sortablePromise = null;

    var ROW_TEMPLATE = [
        '<div class="nx-step-row__body">',
        '  <button type="button" class="js-step-handle nx-step-handle" title="Drag to move. Drag sideways to nest." aria-label="Drag to reorder this step">',
        '    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor" aria-hidden="true">',
        '      <path d="M7 5a1 1 0 110-2 1 1 0 010 2zm6-1a1 1 0 100 2 1 1 0 000-2zM7 11a1 1 0 110-2 1 1 0 010 2zm6-1a1 1 0 100 2 1 1 0 000-2zM7 17a1 1 0 110-2 1 1 0 010 2zm6-1a1 1 0 100 2 1 1 0 000-2z"/>',
        '    </svg>',
        '  </button>',
        '  <input type="hidden" data-step-ref-input name="step_ref[]" value="">',
        '  <input type="hidden" data-step-id-input name="step_id[]" value="">',
        '  <input type="hidden" data-step-parent-input name="step_parent[]" value="">',
        '  <input type="text" data-step-description name="step_description[]" value="" class="nx-step-input" placeholder="Describe this step">',
        '  <span class="nx-step-actions">',
        '    <button type="button" class="nx-step-btn" data-step-action="add-sub" title="Add a sub-step under this one">+ Sub</button>',
        '    <button type="button" class="nx-step-btn" data-step-action="outdent" title="Move out one level (Shift+Tab)">\u21e4</button>',
        '    <button type="button" class="nx-step-btn" data-step-action="indent" title="Nest under the step above (Tab)">\u21e5</button>',
        '    <button type="button" class="nx-step-btn nx-step-btn--danger" data-step-action="remove" title="Delete this step and its sub-steps">\u00d7</button>',
        '  </span>',
        '</div>'
    ].join('');

    function readCookie(name) {
        var cookies = document.cookie ? document.cookie.split(';') : [];
        for (var i = 0; i < cookies.length; i++) {
            var crumb = cookies[i].trim();
            if (crumb.indexOf(name + '=') === 0) {
                return decodeURIComponent(crumb.substring(name.length + 1));
            }
        }
        return null;
    }

    function withSortable(callback) {
        if (global.Sortable) {
            callback();
            return;
        }
        if (!sortablePromise) {
            sortablePromise = new Promise(function (resolve, reject) {
                var script = document.createElement('script');
                script.src = SORTABLE_SRC;
                script.onload = resolve;
                script.onerror = function () { reject(new Error('Sortable failed to load')); };
                document.head.appendChild(script);
            });
        }
        sortablePromise.then(function () { callback(); }, function () { /* drag disabled */ });
    }

    /* ---------------------------- DOM reads ---------------------------- */

    function depthOf(rowEl, root) {
        var depth = 0;
        var node = rowEl.parentElement;
        while (node && node !== root) {
            if (node.getAttribute && node.getAttribute('data-step-list') !== null) depth++;
            node = node.parentElement;
        }
        return depth;
    }

    function readRows(root, excludeRef) {
        var els = root.querySelectorAll('li[data-step-row]');
        var rows = [];
        for (var i = 0; i < els.length; i++) {
            rows.push({
                ref: els[i].getAttribute('data-step-ref'),
                depth: depthOf(els[i], root),
                parentRef: els[i].getAttribute('data-step-parent') || null,
                id: els[i].getAttribute('data-step-id') || '',
                el: els[i]
            });
        }
        return excludeRef ? withoutSubtree(rows, excludeRef) : rows;
    }

    function rowByRef(root, ref) {
        if (!ref) return null;
        return root.querySelector('li[data-step-row][data-step-ref="' + ref + '"]');
    }

    /* ---------------------------- DOM writes --------------------------- */

    function childList(root, rowEl) {
        var children = rowEl.children;
        for (var i = 0; i < children.length; i++) {
            if (children[i].tagName === 'UL' && children[i].getAttribute('data-step-list') !== null) {
                return children[i];
            }
        }
        var ul = document.createElement('ul');
        ul.setAttribute('data-step-list', '');
        ul.className = 'nx-step-list nx-step-list--children';
        ul.hidden = false;
        rowEl.appendChild(ul);
        withSortable(function () { makeSortable(ul, root); });
        return ul;
    }

    function applyPlan(root, plan, rowEl) {
        var container = root;
        if (plan.parentRef) {
            var parentEl = rowByRef(root, plan.parentRef);
            // The new parent may be an ancestor of the row (that is what
            // outdenting is), but it can never be the row itself or anything
            // nested inside it.
            if (!parentEl || parentEl === rowEl || rowEl.contains(parentEl)) return false;
            container = childList(root, parentEl);
        }
        var before = plan.beforeRef ? rowByRef(root, plan.beforeRef) : null;
        if (before && before.parentElement !== container) before = null;
        try {
            container.insertBefore(rowEl, before);
        } catch (error) {
            return false;
        }
        syncParents(root);
        return true;
    }

    // The parent reference is the source of truth on submit, so it is
    // recomputed from the DOM after every structural change.
    function syncParents(root) {
        var lists = [root];
        var nested = root.querySelectorAll('ul[data-step-list]');
        for (var i = 0; i < nested.length; i++) lists.push(nested[i]);

        lists.forEach(function (ul) {
            var parentRef = ul === root ? '' : (ul.parentElement.getAttribute('data-step-ref') || '');
            var children = ul.children;
            // An empty child list has no rows to show, and collapsing it keeps
            // the dashed guide line from dangling under a childless step.
            if (ul !== root) ul.hidden = children.length === 0;
            for (var j = 0; j < children.length; j++) {
                var li = children[j];
                if (li.getAttribute('data-step-row') === null) continue;
                li.setAttribute('data-step-parent', parentRef);
                var input = li.querySelector('input[data-step-parent-input]');
                if (input) input.value = parentRef;
            }
        });
    }

    function buildRow(root, options) {
        var li = document.createElement('li');
        li.className = 'nx-step-row';
        li.setAttribute('data-step-row', '');
        li.setAttribute('data-step-ref', options.ref);
        li.setAttribute('data-step-id', options.id || '');
        li.setAttribute('data-step-parent', options.parentRef || '');
        li.innerHTML = ROW_TEMPLATE;
        li.querySelector('input[data-step-ref-input]').value = options.ref;
        li.querySelector('input[data-step-id-input]').value = options.id || '';
        li.querySelector('input[data-step-parent-input]').value = options.parentRef || '';
        var description = li.querySelector('input[data-step-description]');
        description.value = options.description || '';
        if (options.placeholder) description.placeholder = options.placeholder;
        if (options.inputClass) description.className = options.inputClass;
        return li;
    }

    function nextRef(root) {
        var seq = parseInt(root.getAttribute('data-step-seq') || '0', 10) + 1;
        root.setAttribute('data-step-seq', String(seq));
        return 'n' + seq;
    }

    function addRow(root, options) {
        var row = buildRow(root, {
            ref: nextRef(root),
            id: '',
            description: '',
            parentRef: options.parentRef || '',
            placeholder: options.placeholder || '',
            inputClass: root.getAttribute('data-input-class') || ''
        });
        var container = options.parentRef ? childList(root, rowByRef(root, options.parentRef)) : root;
        container.appendChild(row);
        syncParents(root);
        var input = row.querySelector('input[data-step-description]');
        if (input) input.focus();
        return row;
    }

    /* ----------------------------- Saving ------------------------------ */

    function statusEl(root) {
        var id = root.getAttribute('data-status-id');
        return id ? document.getElementById(id) : null;
    }

    function setStatus(root, message, kind) {
        var status = statusEl(root);
        if (!status) return;
        status.textContent = message;
        status.className = 'nx-step-status' + (kind ? ' nx-step-status--' + kind : '');
    }

    function toast(type, message) {
        var toaster = global.goeyToast;
        if (toaster && typeof toaster[type] === 'function') toaster[type](message);
    }

    function persist(root) {
        var url = root.getAttribute('data-persist-url');
        if (!url) return Promise.resolve(null);

        var rows = readRows(root, null);
        var steps = [];
        rows.forEach(function (row) {
            if (!row.id) return; // not saved yet; the form submit handles it
            var parent = row.parentRef ? rowByRef(root, row.parentRef) : null;
            steps.push({ id: row.id, parent: parent ? (parent.getAttribute('data-step-id') || '') : '' });
        });

        setStatus(root, 'Saving step order\u2026');
        // Wrapped so a browser without fetch (or a blocked request) rejects
        // into the handler below instead of throwing out of the drag handler.
        return Promise.resolve()
            .then(function () {
                return fetch(url, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-CSRFToken': readCookie('csrftoken') || ''
                    },
                    body: JSON.stringify({ steps: steps })
                });
            })
            .then(function (response) {
                if (!response.ok) throw new Error('Request failed');
                return response.json();
            })
            .then(function (data) {
                if (!data || !data.ok) throw new Error('Request failed');
                setStatus(root, 'Step order saved.', 'ok');
                toast('success', 'Step order saved.');
            })
            .catch(function () {
                setStatus(root, 'Step order saved when you save the form.', 'err');
                toast('error', 'Could not save the order yet. Save the form to keep it.');
            });
    }

    function commit(root, plan, rowEl) {
        if (!plan) return false;
        if (!applyPlan(root, plan, rowEl)) return false;
        persist(root);
        return true;
    }

    /* ----------------------------- Dragging ---------------------------- */

    function makeSortable(ul, root) {
        if (ul.getAttribute('data-step-sortable') === '1') return;
        ul.setAttribute('data-step-sortable', '1');
        var group = root.getAttribute('data-step-group');
        var lastX = null;

        new global.Sortable(ul, {
            group: group,
            handle: '.js-step-handle',
            animation: 150,
            fallbackOnBody: true,
            swapThreshold: 0.7,
            emptyInsertThreshold: 12,
            onStart: function () { lastX = null; },
            onMove: function (evt) {
                if (evt.originalEvent && typeof evt.originalEvent.clientX === 'number') {
                    lastX = evt.originalEvent.clientX;
                }
            },
            onEnd: function (evt) { finishDrag(root, evt.item, lastX); }
        });
    }

    function finishDrag(root, node, dropX) {
        var ref = node.getAttribute('data-step-ref');
        var all = readRows(root, null);
        var others = withoutSubtree(all, ref);
        var position = indexOfRef(all, ref);

        // Where Sortable left the row decides its vertical position; the
        // pointer's horizontal position decides how deeply it is nested.
        var insertIndex = others.length;
        for (var i = position + 1; i < all.length; i++) {
            if (isDescendantOf(all, i, position)) continue;
            var mapped = indexOfRef(others, all[i].ref);
            if (mapped >= 0) insertIndex = mapped;
            break;
        }

        var plan = planDrop(others, insertIndex, dropX, root.getBoundingClientRect().left, INDENT_PX);
        if (!plan) {
            syncParents(root);
            return;
        }
        commit(root, plan, node);
    }

    /* ------------------------------ Wiring ----------------------------- */

    function removeRow(root, rowEl) {
        var rows = readRows(root, null);
        var index = indexOfRef(rows, rowEl.getAttribute('data-step-ref'));
        var childCount = 0;
        for (var i = index + 1; i < rows.length; i++) {
            if (isDescendantOf(rows, i, index)) childCount++;
            else break;
        }
        if (childCount && !global.confirm('Delete this step and its ' + childCount + ' sub-step' + (childCount === 1 ? '' : 's') + '?')) {
            return;
        }
        rowEl.parentNode.removeChild(rowEl);
        syncParents(root);
        persist(root);
    }

    function onAction(root, button) {
        var action = button.getAttribute('data-step-action');
        var rowEl = button.closest ? button.closest('li[data-step-row]') : null;
        var ref = rowEl ? rowEl.getAttribute('data-step-ref') : null;
        var rows = readRows(root, null);

        if (action === 'add') {
            addRow(root, {});
            return;
        }
        if (action === 'add-sub' && ref) {
            addRow(root, { parentRef: ref, placeholder: 'Sub-step\u2026' });
            persist(root);
            return;
        }
        if (!rowEl) return;

        if (action === 'indent' || action === 'outdent') {
            var plan = action === 'indent' ? planIndent(rows, ref) : planOutdent(rows, ref);
            commit(root, plan, rowEl);
            return;
        }
        if (action === 'remove') {
            removeRow(root, rowEl);
        }
    }

    // Tab / Shift+Tab inside a description field nests or promotes the row.
    function onKeydown(root, event) {
        if (event.key !== 'Tab') return;
        var input = event.target;
        if (!input || input.getAttribute('data-step-description') === null) return;
        var rowEl = input.closest('li[data-step-row]');
        if (!rowEl) return;
        var rows = readRows(root, null);
        var ref = rowEl.getAttribute('data-step-ref');
        var plan = event.shiftKey ? planOutdent(rows, ref) : planIndent(rows, ref);
        if (commit(root, plan, rowEl)) {
            event.preventDefault();
            input.focus();
        }
    }

    function initEditor(root) {
        if (!root || root.getAttribute('data-step-init') === '1') return;
        root.setAttribute('data-step-init', '1');
        if (!root.getAttribute('data-step-group')) {
            groupCounter += 1;
            root.setAttribute('data-step-group', 'nx-process-steps-' + groupCounter);
        }

        var wrapper = root.closest('[data-step-editor]') || root.parentElement || root;
        if (wrapper.getAttribute('data-step-bound') !== '1') {
            wrapper.setAttribute('data-step-bound', '1');
            wrapper.addEventListener('click', function (event) {
                var button = event.target.closest('[data-step-action]');
                if (button && wrapper.contains(button)) onAction(root, button);
            });
            wrapper.addEventListener('keydown', function (event) { onKeydown(root, event); });
        }

        syncParents(root);
        withSortable(function () {
            makeSortable(root, root);
            var nested = root.querySelectorAll('ul[data-step-list]');
            for (var i = 0; i < nested.length; i++) makeSortable(nested[i], root);
        });
    }

    function initAll() {
        if (typeof document.querySelectorAll !== 'function') return;
        var roots = document.querySelectorAll('ul[data-step-root]');
        for (var i = 0; i < roots.length; i++) initEditor(roots[i]);
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initAll);
    } else {
        initAll();
    }
})(typeof globalThis !== 'undefined' ? globalThis : this);
