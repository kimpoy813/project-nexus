const { test } = require("node:test");
const assert = require("node:assert/strict");
const { readFileSync } = require("node:fs");
const { runInNewContext } = require("node:vm");

const script = readFileSync("static/js/gallery-directory.js", "utf8");

function makeFigure(key) {
    return {
        hidden: false,
        style: { order: "" },
        getAttribute(name) {
            return name === "data-gallery-key" ? key : null;
        },
    };
}

function makeHarness(seed, figures) {
    const sandbox = {
        document: {
            getElementById(id) {
                return id === "gallery-seed-1" ? { textContent: JSON.stringify(seed) } : null;
            },
        },
    };
    runInNewContext(script, sandbox);
    const controller = sandbox.nexusGalleryDirectory("gallery-seed-1");
    controller.$el = {
        querySelector(sel) {
            if (sel === "[data-gallery-grid]" && figures) {
                return {
                    querySelectorAll(innerSel) {
                        return innerSel === "[data-gallery-key]" ? figures : [];
                    },
                };
            }
            return null;
        },
    };
    controller.apply();
    return controller;
}

const BASE_OVERVIEW = {
    years: [
        { value: "2024", label: "2024", short_label: "24", count: 0, percent: 0, bar_percent: 0 },
        { value: "2025", label: "2025", short_label: "25", count: 0, percent: 0, bar_percent: 0 },
    ],
    campuses: [
        { key: "main", value: "Main Campus", label: "Main Campus", count: 0, percent: 0 },
        { key: "stamaria", value: "Sta. Maria Campus", label: "Sta. Maria Campus", count: 0, percent: 0 },
    ],
    sources: [
        { value: "TERMINAL_REPORT", label: "Terminal report", short_label: "Terminal report", color: "#103b07", count: 0, percent: 0, dash: 0, gap: 100, dashoffset: 25 },
        { value: "LEGACY", label: "Legacy upload", short_label: "Legacy upload", color: "#5a1113", count: 0, percent: 0, dash: 0, gap: 100, dashoffset: 25 },
    ],
};

test("zero-photo state keeps Summary KPIs, Visual Overview charts, and Filters intact", () => {
    const ctrl = makeHarness({
        stats: {
            photo_count: 0,
            activity_count: 0,
            campus_count: 0,
            total_campuses: 7,
            terminal_report_count: 0,
            legacy_count: 0,
        },
        overview: BASE_OVERVIEW,
        photos: [],
    });

    assert.equal(ctrl.shown, 0);
    assert.equal(ctrl.shownActivities, 0);
    assert.equal(ctrl.shownCampuses, 0);
    assert.equal(ctrl.shownTerminal, 0);
    assert.equal(ctrl.shownLegacy, 0);
    assert.equal(ctrl.hasActiveFilters(), false);
    assert.equal(ctrl.campusStat("main").count, 0);
    assert.equal(ctrl.yearStat("2025").count, 0);
    assert.equal(ctrl.sourceStat("TERMINAL_REPORT").count, 0);
});

test("filtering, quoted-phrase search, and non-destructive CSS order sorting recalculate KPIs and charts", () => {
    const figures = [makeFigure("photo-1"), makeFigure("photo-2"), makeFigure("photo-3")];
    const ctrl = makeHarness(
        {
            stats: {
                photo_count: 3,
                activity_count: 2,
                campus_count: 2,
                total_campuses: 7,
                terminal_report_count: 2,
                legacy_count: 1,
            },
            overview: BASE_OVERVIEW,
            photos: [
                {
                    key: "photo-1",
                    order_index: 0,
                    proposal_id: 10,
                    title: "Seedling nursery workshop",
                    caption: "Seedling nursery workshop",
                    subtitle: "Agroforestry Program",
                    campus: "Sta. Maria Campus",
                    campus_key: "stamaria",
                    year: "2025",
                    taken_on: "2025-05-10",
                    source: "TERMINAL_REPORT",
                    source_label: "Terminal report",
                },
                {
                    key: "photo-2",
                    order_index: 1,
                    proposal_id: 10,
                    title: "Field planting day",
                    caption: "Field planting day",
                    subtitle: "Agroforestry Program",
                    campus: "Sta. Maria Campus",
                    campus_key: "stamaria",
                    year: "2025",
                    taken_on: "2025-05-11",
                    source: "TERMINAL_REPORT",
                    source_label: "Terminal report",
                },
                {
                    key: "photo-3",
                    order_index: 2,
                    proposal_id: 20,
                    title: "Coastal clean-up drive",
                    caption: "Coastal clean-up drive",
                    subtitle: "Marine Conservation",
                    campus: "Main Campus",
                    campus_key: "main",
                    year: "2024",
                    taken_on: "2024-08-15",
                    source: "LEGACY",
                    source_label: "Legacy upload",
                },
            ],
        },
        figures
    );

    assert.equal(ctrl.shown, 3);
    assert.equal(ctrl.shownActivities, 2);
    assert.equal(ctrl.shownCampuses, 2);

    // Filter by campus via chart toggle
    ctrl.toggleCampus("stamaria");
    assert.equal(ctrl.shown, 2);
    assert.equal(ctrl.shownActivities, 1);
    assert.equal(ctrl.shownTerminal, 2);
    assert.equal(ctrl.shownLegacy, 0);
    assert.equal(figures[0].hidden, false);
    assert.equal(figures[1].hidden, false);
    assert.equal(figures[2].hidden, true);

    // Quoted exact phrase search narrows further
    ctrl.q = '"nursery workshop"';
    ctrl.apply();
    assert.equal(ctrl.shown, 1);
    assert.deepEqual(Array.from(ctrl.filteredKeys), ["photo-1"]);
    assert.equal(figures[0].hidden, false);
    assert.equal(figures[1].hidden, true);

    // Reset restores all items, then sort oldest-first updates CSS order
    ctrl.reset();
    assert.equal(ctrl.shown, 3);
    ctrl.sortBy = "oldest";
    ctrl.apply();
    assert.deepEqual(Array.from(ctrl.filteredKeys), ["photo-3", "photo-1", "photo-2"]);
    assert.equal(figures[2].style.order, "1");
    assert.equal(figures[0].style.order, "2");
    assert.equal(figures[1].style.order, "3");
});
