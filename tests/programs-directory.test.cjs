const { test } = require("node:test");
const assert = require("node:assert/strict");
const { readFileSync } = require("node:fs");
const { runInNewContext } = require("node:vm");

const script = readFileSync("static/js/programs-directory.js", "utf8");

function makeHarness(seed, cards) {
    const sandbox = {
        document: {
            getElementById(id) {
                return id === "seed-1" ? { textContent: JSON.stringify(seed) } : null;
            },
        },
    };
    runInNewContext(script, sandbox);
    const controller = sandbox.nexusProgramsDirectory("seed-1");
    controller.$el = {
        querySelectorAll() {
            return cards;
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
    extension_types: [
        { value: "COMMUNITY_BASED", label: "Community-based", short_label: "Community-based", color: "#ca8a04", count: 0, percent: 0, dash: 0, gap: 100, dashoffset: 25 },
        { value: "REQUEST_BASED", label: "Request-based", short_label: "Request-based", color: "#5a1113", count: 0, percent: 0, dash: 0, gap: 100, dashoffset: 25 },
        { value: "RESEARCH_BASED", label: "Research-based", short_label: "Research-based", color: "#103b07", count: 0, percent: 0, dash: 0, gap: 100, dashoffset: 25 },
    ],
    research_bases: [
        { value: "FACULTY", label: "Based on Faculty Research", short_label: "Faculty Research", color: "#103b07", count: 0, percent: 0, dash: 0, gap: 100, dashoffset: 25 },
        { value: "STUDENT", label: "Based on Student Research", short_label: "Student Research", color: "#2f6f3e", count: 0, percent: 0, dash: 0, gap: 100, dashoffset: 25 },
        { value: "OTHERS", label: "Others", short_label: "Others", color: "#94a3b8", count: 0, percent: 0, dash: 0, gap: 100, dashoffset: 25 },
    ],
    proponents: [
        { value: "FACULTY", label: "Faculty", short_label: "Faculty", color: "#103b07", count: 0, percent: 0, dash: 0, gap: 100, dashoffset: 25 },
        { value: "JOINT", label: "Joint", short_label: "Joint", color: "#5a1113", count: 0, percent: 0, dash: 0, gap: 100, dashoffset: 25 },
        { value: "STUDENT", label: "Student", short_label: "Student", color: "#ca8a04", count: 0, percent: 0, dash: 0, gap: 100, dashoffset: 25 },
    ],
};

test("zero-data state keeps all 6 KPIs and 5 overview charts intact at zero", () => {
    const ctrl = makeHarness(
        {
            stats: {
                program_count: 0,
                campus_count: 0,
                total_campuses: 7,
                beneficiaries: 0,
                students: 0,
                faculty: 0,
                research_staff: 0,
            },
            overview: BASE_OVERVIEW,
        },
        []
    );

    assert.equal(ctrl.shown, 0);
    assert.equal(ctrl.shownCampuses, 0);
    assert.equal(ctrl.totalCampuses, 7);
    assert.equal(ctrl.yearStat("2025").count, 0);
    assert.equal(ctrl.campusStat("main").percent, 0);
    assert.equal(ctrl.donutStat("extensionTypes", "COMMUNITY_BASED").dash, 0);
    assert.equal(ctrl.donutStat("extensionTypes", "COMMUNITY_BASED").gap, 100);

    ctrl.toggleFilter("campus", "Main Campus");
    assert.equal(ctrl.hasActiveFilters(), true);
    assert.equal(ctrl.shown, 0);
    ctrl.reset();
    assert.equal(ctrl.hasActiveFilters(), false);
});

test("clicking charts recalculates KPI totals, bars, and donut arcs dynamically", () => {
    const cards = [
        {
            style: {},
            dataset: {
                campus: "Main Campus",
                campusKey: "main",
                year: "2025",
                type: "COMMUNITY_BASED",
                basis: "OTHERS",
                led: "FACULTY",
                beneficiaries: "80",
                students: "12",
                faculty: "4",
                researchStaff: "1",
                search: "reading literacy main campus",
            },
        },
        {
            style: {},
            dataset: {
                campus: "Sta. Maria Campus",
                campusKey: "stamaria",
                year: "2024",
                type: "RESEARCH_BASED",
                basis: "FACULTY",
                led: "JOINT",
                beneficiaries: "120",
                students: "20",
                faculty: "6",
                researchStaff: "3",
                search: "coastal farming sta. maria campus",
            },
        },
    ];

    const ctrl = makeHarness(
        {
            stats: {
                program_count: 2,
                campus_count: 2,
                total_campuses: 7,
                beneficiaries: 200,
                students: 32,
                faculty: 10,
                research_staff: 4,
            },
            overview: BASE_OVERVIEW,
        },
        cards
    );

    assert.equal(ctrl.shown, 2);
    assert.equal(ctrl.shownCampuses, 2);
    assert.equal(ctrl.shownBeneficiaries, 200);
    assert.equal(ctrl.donutStat("extensionTypes", "COMMUNITY_BASED").dash, 50);
    assert.equal(ctrl.donutStat("extensionTypes", "RESEARCH_BASED").dash, 50);
    assert.equal(ctrl.donutStat("extensionTypes", "RESEARCH_BASED").dashoffset, -25);

    // Filter by Sta. Maria Campus via chart click (matches normalized campus key).
    ctrl.toggleFilter("campus", "Sta Maria Campus");
    assert.equal(ctrl.shown, 1);
    assert.equal(ctrl.shownCampuses, 1);
    assert.equal(ctrl.shownBeneficiaries, 120);
    assert.equal(ctrl.shownStudents, 20);
    assert.equal(ctrl.shownFaculty, 6);
    assert.equal(ctrl.shownResearchStaff, 3);
    assert.equal(ctrl.campusStat("stamaria").percent, 100);
    assert.equal(ctrl.campusStat("main").percent, 0);
    assert.equal(ctrl.yearStat("2024").bar_percent, 100);
    assert.equal(ctrl.donutStat("extensionTypes", "RESEARCH_BASED").dash, 100);
    assert.equal(cards[0].style.display, "none");
    assert.equal(cards[1].style.display, "");
});
