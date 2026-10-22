const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const themeSource = fs.readFileSync(
    path.join(__dirname, '..', 'static', 'js', 'nexus-theme.js'),
    'utf8',
);

const facultyTemplate = fs.readFileSync(
    path.join(__dirname, '..', 'accounts', 'templates', 'dashboard', 'faculty_dashboard.html'),
    'utf8',
);

/* Extract the production gauge functions directly from faculty_dashboard.html so
   tests exercise the exact sweep math (`0% -> 100% -> hold -> target%`). */
function extractGaugeFunctions() {
    const start = facultyTemplate.indexOf('function easeOutCubic(');
    const end = facultyTemplate.indexOf('document.addEventListener("DOMContentLoaded"');
    assert.ok(start !== -1 && end > start, 'faculty_dashboard.html contains gauge helpers');
    return facultyTemplate.slice(start, end);
}

const gaugeHelpersSource = extractGaugeFunctions();

function makeClassList(initial = []) {
    const set = new Set(initial);
    return {
        add(...names) { names.forEach((n) => set.add(n)); },
        remove(...names) { names.forEach((n) => set.delete(n)); },
        toggle(name, force) {
            if (force === undefined) {
                if (set.has(name)) { set.delete(name); return false; }
                set.add(name); return true;
            }
            if (force) set.add(name); else set.delete(name);
            return Boolean(force);
        },
        contains(name) { return set.has(name); },
    };
}

function createCanvas({ hidden = false, rect = { top: 40, bottom: 142, left: 20, right: 122, width: 102, height: 102 } } = {}) {
    const listeners = {};
    const strokes = [];
    let transform = null;
    const ctx = {
        strokeStyle: '',
        lineWidth: 1,
        lineCap: 'butt',
        clearRect() {},
        beginPath() {},
        arc(cx, cy, r, start, end) {
            ctx._lastArc = { cx, cy, r, start, end };
        },
        stroke() {
            strokes.push({ strokeStyle: ctx.strokeStyle, lineWidth: ctx.lineWidth, arc: ctx._lastArc });
        },
        setTransform(...args) {
            transform = args;
        },
    };

    const panel = {
        nodeType: 1,
        hidden: Boolean(hidden),
        classList: makeClassList(hidden === 'class' ? ['hidden'] : []),
        parentElement: null,
        contains(node) { return node === canvas; },
    };
    if (hidden === 'class') panel.hidden = false;

    const canvas = {
        nodeType: 1,
        isConnected: true,
        width: 0,
        height: 0,
        dataset: {},
        style: {},
        parentElement: panel,
        classList: makeClassList(),
        getContext() { return ctx; },
        getBoundingClientRect() { return rect; },
        closest(selector) {
            if (selector.includes('[hidden]') && panel.hidden) return panel;
            if (selector.includes('.hidden') && panel.classList.contains('hidden')) return panel;
            return null;
        },
        addEventListener(type, fn) {
            (listeners[type] ||= []).push(fn);
        },
        click() {
            (listeners.click || []).forEach((fn) => fn({ type: 'click' }));
        },
        _strokes: strokes,
        get _transform() { return transform; },
        _panel: panel,
    };

    return canvas;
}

function createHarness({ dpr = 1, hasSkeleton = false } = {}) {
    let now = 0;
    let nextTimerId = 1;
    let nextRafId = 1;
    const timers = new Map();
    const rafs = new Map();
    const windowListeners = {};
    const docListeners = {};
    const observed = new Set();
    let ioCallback = null;

    const skeleton = hasSkeleton
        ? { id: 'nx-page-skeleton', hidden: false, classList: makeClassList() }
        : null;

    class MockIntersectionObserver {
        constructor(cb) {
            ioCallback = cb;
        }
        observe(target) {
            observed.add(target);
        }
        unobserve(target) {
            observed.delete(target);
        }
    }

    const document = {
        readyState: 'complete',
        documentElement: { clientHeight: 800, clientWidth: 1280 },
        getElementById(id) {
            if (id === 'nx-page-skeleton') return skeleton;
            return null;
        },
        querySelectorAll() { return []; },
        addEventListener(type, fn) {
            (docListeners[type] ||= []).push(fn);
        },
    };

    const window = {
        document,
        devicePixelRatio: dpr,
        innerHeight: 800,
        innerWidth: 1280,
        IntersectionObserver: MockIntersectionObserver,
        performance: { now: () => now },
        getComputedStyle(el) {
            const hidden = el.hidden || (el.classList && el.classList.contains('hidden'));
            return { display: hidden ? 'none' : 'block', visibility: 'visible' };
        },
        setTimeout(fn, delay = 0) {
            const id = nextTimerId++;
            timers.set(id, { due: now + Math.max(0, Number(delay) || 0), fn });
            return id;
        },
        clearTimeout(id) {
            timers.delete(id);
        },
        requestAnimationFrame(fn) {
            const id = nextRafId++;
            rafs.set(id, fn);
            return id;
        },
        cancelAnimationFrame(id) {
            rafs.delete(id);
        },
        addEventListener(type, fn) {
            (windowListeners[type] ||= []).push(fn);
        },
    };

    const sandbox = {
        window,
        document,
        performance: window.performance,
        requestAnimationFrame: window.requestAnimationFrame,
        cancelAnimationFrame: window.cancelAnimationFrame,
        Math,
        Number,
        Boolean,
        String,
        Object,
        Array,
        JSON,
    };
    window.nexusPhaseShares = null;

    vm.runInNewContext(themeSource, sandbox, { filename: 'nexus-theme.js' });
    sandbox.nexusPhaseShares = window.nexusPhaseShares;
    vm.runInNewContext(gaugeHelpersSource, sandbox, { filename: 'faculty-gauge.js' });

    function stepTo(targetMs) {
        while (true) {
            let earliest = null;
            for (const [id, timer] of timers.entries()) {
                if (timer.due <= targetMs && (!earliest || timer.due < earliest.timer.due)) {
                    earliest = { id, timer };
                }
            }
            if (!earliest) break;
            now = earliest.timer.due;
            timers.delete(earliest.id);
            earliest.timer.fn();
        }
        now = targetMs;
        const batch = Array.from(rafs.entries());
        rafs.clear();
        for (const [, fn] of batch) {
            fn(now);
        }
    }

    function intersect(target, isIntersecting = true) {
        if (ioCallback) {
            ioCallback([{ target, isIntersecting, intersectionRatio: isIntersecting ? 0.5 : 0 }]);
        }
    }

    function firePageShow(persisted) {
        (windowListeners.pageshow || []).forEach((fn) => fn({ persisted }));
    }

    return {
        window,
        sandbox,
        skeleton,
        observed,
        rafs,
        stepTo,
        intersect,
        firePageShow,
    };
}

test('waits for #nx-page-skeleton fade-out before starting initial gauge sweep', () => {
    const h = createHarness({ hasSkeleton: true, dpr: 2 });
    const canvas = createCanvas();
    const textEl = { textContent: '0%' };

    h.window.nexusGauge.register(
        canvas,
        textEl,
        62,
        h.sandbox.animateDoughnutGauge,
        h.sandbox.createDoughnutGauge,
    );

    // Crisp HiDPI backing store is configured while keeping 102px logical geometry.
    assert.equal(canvas.width, 204);
    assert.equal(canvas.height, 204);
    assert.equal(canvas.style.width, '102px');
    assert.deepEqual(canvas._transform, [2, 0, 0, 2, 0, 0]);

    // While skeleton overlay is still fading (<190ms), the sweep has NOT started yet.
    h.stepTo(100);
    assert.equal(textEl.textContent, '0%');
    assert.equal(h.rafs.size, 0);

    // Once skeleton clears (>=190ms), sweep rises smoothly 0% -> 100% -> holds -> settles at 62%.
    h.stepTo(200);
    assert.equal(h.rafs.size, 1);

    h.stepTo(900); // mid-rise
    const midRise = parseInt(textEl.textContent, 10);
    assert.ok(midRise > 50 && midRise < 100, `expected mid-rise between 50 and 100, got ${midRise}`);

    h.stepTo(1750); // hold at 100%
    assert.equal(textEl.textContent, '100%');

    h.stepTo(3400); // settled at target 62%
    assert.equal(textEl.textContent, '62%');
    assert.equal(canvas._nxGaugeRaf, null);
});

test('defers hidden panel gauges and animates immediately when switched to Cards view or tab', () => {
    const h = createHarness({ hasSkeleton: false });
    const canvas = createCanvas({ hidden: true });
    const textEl = { textContent: '0%' };

    h.window.nexusGauge.register(
        canvas,
        textEl,
        45,
        h.sandbox.animateDoughnutGauge,
        h.sandbox.createDoughnutGauge,
    );

    // Simulate user staying on Table view for 5 full seconds: gauge never wastes its sweep hidden.
    h.stepTo(10);
    h.stepTo(5000);
    assert.equal(textEl.textContent, '0%');
    assert.equal(h.rafs.size, 0);

    // User clicks Cards view toggle -> unhide panel and notify controller interactively.
    canvas._panel.hidden = false;
    h.window.nexusGauge.onPanelToggle(canvas._panel, true, true);
    assert.equal(h.rafs.size, 1);

    h.stepTo(6500); // 1500ms into sweep -> holding at 100%
    assert.equal(textEl.textContent, '100%');

    h.stepTo(8200); // settled at 45%
    assert.equal(textEl.textContent, '45%');

    // Switching back to Table resets cleanly so switching to Cards again replays freshly.
    canvas._panel.hidden = true;
    h.window.nexusGauge.onPanelToggle(canvas._panel, false, true);
    assert.equal(textEl.textContent, '0%');
});

test('defers off-screen below-the-fold gauges until scrolled into view', () => {
    const h = createHarness({ hasSkeleton: false });
    const offscreen = createCanvas({
        rect: { top: 1400, bottom: 1502, left: 20, right: 122, width: 102, height: 102 },
    });
    const textEl = { textContent: '0%' };

    h.window.nexusGauge.register(
        offscreen,
        textEl,
        78,
        h.sandbox.animateDoughnutGauge,
        h.sandbox.createDoughnutGauge,
    );

    h.stepTo(10);
    assert.ok(h.observed.has(offscreen), 'below-the-fold canvas is watched by IntersectionObserver');
    assert.equal(h.rafs.size, 0);
    assert.equal(textEl.textContent, '0%');

    // User scrolls down to reveal card: sweep triggers immediately and unobserves cleanly.
    h.intersect(offscreen, true);
    assert.ok(!h.observed.has(offscreen));
    assert.equal(h.rafs.size, 1);

    h.stepTo(3200);
    assert.equal(textEl.textContent, '78%');
});

test('clicking a gauge or restoring from bfcache replays cleanly without overlapping RAF loops', () => {
    const h = createHarness({ hasSkeleton: false });
    const canvas = createCanvas();
    const textEl = { textContent: '0%' };

    h.window.nexusGauge.register(
        canvas,
        textEl,
        35,
        h.sandbox.animateDoughnutGauge,
        h.sandbox.createDoughnutGauge,
    );

    h.stepTo(10);
    h.stepTo(3200);
    assert.equal(textEl.textContent, '35%');

    // Clicking the gauge replays from 0% cleanly without leaving duplicate RAF callbacks queued.
    canvas.click();
    assert.equal(textEl.textContent, '0%');
    assert.equal(h.rafs.size, 1);

    // Mid-flight bfcache pageshow also cancels the prior RAF loop and starts a single clean loop.
    h.stepTo(3800);
    h.firePageShow(true);
    assert.equal(textEl.textContent, '0%');
    assert.equal(h.rafs.size, 1);

    h.stepTo(7000);
    assert.equal(textEl.textContent, '35%');
});
