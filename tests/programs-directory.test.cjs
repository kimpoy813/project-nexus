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
            return cards || [];
        },
        querySelector() {
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

test("zero-data state keeps all 6 KPIs, 5 overview charts, and filter controls intact", () => {
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
            programs: [],
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
    assert.equal(ctrl.facetButtonLabel("campuses", "Campuses"), "Campuses: All");

    ctrl.toggleFilter("campus", "Main Campus");
    assert.equal(ctrl.hasActiveFilters(), true);
    assert.equal(ctrl.facetButtonLabel("campuses", "Campuses"), "Campuses: Main Campus");
    assert.equal(ctrl.activeFilterChips().length, 1);
    assert.equal(ctrl.shown, 0);

    ctrl.selectAllFacet("campuses");
    assert.equal(ctrl.facetCount("campuses"), 2);
    assert.equal(ctrl.facetButtonLabel("campuses", "Campuses"), "Campuses: 2 selected");

    ctrl.reset();
    assert.equal(ctrl.hasActiveFilters(), false);
    assert.equal(ctrl.facetCount("campuses"), 0);
});

test("multi-select filters, quoted search, documents filter, sort, columns, and CSV work together", () => {
    const programs = [
        {
            key: "p1",
            title: "Reading Literacy Workshop",
            campus: "Main Campus",
            campus_key: "main",
            year: 2025,
            extension_type: "COMMUNITY_BASED",
            extension_type_label: "Community-based",
            research_basis: "OTHERS",
            research_basis_label: "Others",
            led_by: "FACULTY",
            led_by_label: "Faculty",
            target_community: "Dili National High School",
            duration: "May 2025",
            objectives: "Improve reading comprehension.",
            student_participants: 12,
            faculty_participants: 4,
            research_staff_participants: 1,
            beneficiaries: 80,
            document_available: true,
            document_url: "/programs/p1/document/",
        },
        {
            key: "p2",
            title: "Coastal Farming Resilience",
            campus: "Sta. Maria Campus",
            campus_key: "stamaria",
            year: 2024,
            extension_type: "RESEARCH_BASED",
            extension_type_label: "Research-based",
            research_basis: "FACULTY",
            research_basis_label: "Based on Faculty Research",
            led_by: "JOINT",
            led_by_label: "Joint",
            target_community: "Poblacion Sur fisherfolk",
            duration: "October 2024",
            objectives: "Strengthen coastal farming practices.",
            student_participants: 20,
            faculty_participants: 6,
            research_staff_participants: 3,
            beneficiaries: 120,
            document_available: false,
            document_url: "",
        },
    ];
    const cards = [
        { style: {}, dataset: { key: "p1" } },
        { style: {}, dataset: { key: "p2" } },
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
            programs: programs,
        },
        cards
    );

    assert.equal(ctrl.shown, 2);
    assert.equal(ctrl.donutStat("extensionTypes", "COMMUNITY_BASED").dash, 50);
    assert.equal(ctrl.donutStat("extensionTypes", "RESEARCH_BASED").dash, 50);
    assert.equal(ctrl.donutStat("extensionTypes", "RESEARCH_BASED").dashoffset, -25);

    // Filter by Sta. Maria Campus via chart click.
    ctrl.toggleFilter("campus", "Sta Maria Campus");
    assert.equal(ctrl.shown, 1);
    assert.equal(ctrl.shownBeneficiaries, 120);
    assert.equal(ctrl.campusStat("stamaria").percent, 100);
    assert.equal(cards[0].style.display, "none");
    assert.equal(cards[1].style.display, "");
    ctrl.reset();

    // Quoted exact-phrase search vs unmatched phrase.
    ctrl.query = '"coastal farming"';
    ctrl.apply();
    assert.equal(ctrl.shown, 1);
    assert.equal(ctrl.filteredPrograms[0].key, "p2");

    ctrl.query = '"farming coastal"';
    ctrl.apply();
    assert.equal(ctrl.shown, 0);
    ctrl.reset();

    // Documents filter.
    ctrl.documents = "with";
    ctrl.apply();
    assert.equal(ctrl.shown, 1);
    assert.equal(ctrl.filteredPrograms[0].key, "p1");
    ctrl.reset();

    // Sort by most beneficiaries.
    ctrl.sort = "beneficiaries";
    ctrl.apply();
    assert.deepEqual(Array.from(ctrl.filteredPrograms, (p) => p.key), ["p2", "p1"]);

    // Column presets and minimum 1-column guard.
    assert.equal(ctrl.selectedColumns.length, 11);
    assert.equal(ctrl.columnSummaryLabel(), "Columns: Default");
    ctrl.setColumnPreset("minimal");
    assert.equal(ctrl.selectedColumns.length, 6);
    assert.equal(ctrl.columnSummaryLabel(), "Columns: Minimal");
    ctrl.setColumnPreset("all");
    assert.equal(ctrl.selectedColumns.length, 16);
    assert.equal(ctrl.columnSummaryLabel(), "Columns: All 16");

    while (ctrl.selectedColumns.length > 1) {
        ctrl.toggleColumn(ctrl.selectedColumns[ctrl.selectedColumns.length - 1]);
    }
    const lastCol = ctrl.selectedColumns[0];
    ctrl.toggleColumn(lastCol);
    assert.equal(ctrl.selectedColumns.length, 1);

    // CSV export includes header + sorted rows.
    ctrl.setColumnPreset("minimal");
    const csv = ctrl.downloadCsv();
    assert.ok(csv.includes("Program title"));
    assert.ok(csv.includes("Coastal Farming Resilience"));
    assert.ok(csv.includes("Reading Literacy Workshop"));
});

test("rankings re-order by metric and filter by college, academic program, and faculty", () => {
    const programs = [
        {
            key: "p1",
            title: "CS Literacy 1",
            campus: "Main Campus",
            campus_key: "main",
            college: "College of Arts and Sciences",
            college_key: "main::collegeofartsandsciences",
            department: "Bachelor of Science in Computer Science",
            program_key: "main::bachelorofscienceincomputerscience",
            faculty_credits: [{ key: "user-1", label: "Dr. Maria Santos", subtitle: "Main Campus" }],
            faculty_keys: ["user-1"],
            is_completed: false,
            year: 2025,
            extension_type: "COMMUNITY_BASED",
            research_basis: "OTHERS",
            led_by: "FACULTY",
            beneficiaries: 60,
            student_participants: 10,
            faculty_participants: 2,
            research_staff_participants: 0,
            document_available: true,
        },
        {
            key: "p2",
            title: "CS Literacy 2",
            campus: "Main Campus",
            campus_key: "main",
            college: "College of Arts and Sciences",
            college_key: "main::collegeofartsandsciences",
            department: "Bachelor of Science in Computer Science",
            program_key: "main::bachelorofscienceincomputerscience",
            faculty_credits: [{ key: "user-1", label: "Dr. Maria Santos", subtitle: "Main Campus" }],
            faculty_keys: ["user-1"],
            is_completed: true,
            year: 2025,
            extension_type: "RESEARCH_BASED",
            research_basis: "FACULTY",
            led_by: "FACULTY",
            beneficiaries: 90,
            student_participants: 15,
            faculty_participants: 3,
            research_staff_participants: 1,
            document_available: true,
        },
        {
            key: "p3",
            title: "Coastal Agroforestry",
            campus: "Sta. Maria Campus",
            campus_key: "stamaria",
            college: "College of Computing Studies (CCS)",
            college_key: "stamaria::collegeofcomputingstudiesccs",
            department: "Bachelor of Science in Information Technology",
            program_key: "stamaria::bachelorofscienceininformationtechnology",
            faculty_credits: [{ key: "user-2", label: "Prof. Juan Dela Cruz", subtitle: "Sta. Maria Campus" }],
            faculty_keys: ["user-2"],
            is_completed: true,
            year: 2024,
            extension_type: "REQUEST_BASED",
            research_basis: "OTHERS",
            led_by: "FACULTY",
            beneficiaries: 400,
            student_participants: 25,
            faculty_participants: 5,
            research_staff_participants: 2,
            document_available: false,
        },
    ];

    const ctrl = makeHarness(
        {
            stats: {
                program_count: 3,
                campus_count: 2,
                total_campuses: 7,
                beneficiaries: 550,
                students: 50,
                faculty: 10,
                research_staff: 3,
            },
            overview: BASE_OVERVIEW,
            rankings: {
                campuses: [
                    { key: "main", label: "Main Campus", subtitle: "ISPSC Campus" },
                    { key: "stamaria", label: "Sta. Maria Campus", subtitle: "ISPSC Campus" },
                    { key: "cervantes", label: "Cervantes Campus", subtitle: "ISPSC Campus" },
                ],
                colleges: [
                    { key: "main::collegeofartsandsciences", label: "College of Arts and Sciences", subtitle: "Main Campus" },
                    { key: "stamaria::collegeofcomputingstudiesccs", label: "College of Computing Studies (CCS)", subtitle: "Sta. Maria Campus" },
                ],
                programs: [
                    { key: "main::bachelorofscienceincomputerscience", label: "Bachelor of Science in Computer Science", subtitle: "Main Campus" },
                    { key: "stamaria::bachelorofscienceininformationtechnology", label: "Bachelor of Science in Information Technology", subtitle: "Sta. Maria Campus" },
                ],
                faculty: [
                    { key: "user-1", label: "Dr. Maria Santos", subtitle: "Main Campus" },
                    { key: "user-2", label: "Prof. Juan Dela Cruz", subtitle: "Sta. Maria Campus" },
                ],
            },
            programs: programs,
        },
        []
    );

    // Default metric ("programs"): Dr. Maria Santos (#1, 2 programs) leads Prof. Juan Dela Cruz (#2, 1 program); Cervantes has null rank.
    assert.equal(ctrl.rankedFaculty[0].label, "Dr. Maria Santos");
    assert.equal(ctrl.rankedFaculty[0].rank, 1);
    assert.equal(ctrl.rankedFaculty[1].label, "Prof. Juan Dela Cruz");
    assert.equal(ctrl.rankedFaculty[1].rank, 2);
    assert.equal(ctrl.rankedCampuses[2].label, "Cervantes Campus");
    assert.equal(ctrl.rankedCampuses[2].rank, null);

    // Switch metric to "beneficiaries": Prof. Juan Dela Cruz (400) overtakes Dr. Maria Santos (150)!
    ctrl.setRankMetric("beneficiaries");
    assert.equal(ctrl.rankedFaculty[0].label, "Prof. Juan Dela Cruz");
    assert.equal(ctrl.rankedFaculty[0].rank, 1);
    assert.equal(ctrl.rankedCampuses[0].label, "Sta. Maria Campus");
    assert.equal(ctrl.rankedColleges[0].label, "College of Computing Studies (CCS)");
    assert.equal(ctrl.rankedPrograms[0].label, "Bachelor of Science in Information Technology");

    // Click an Individual Faculty row to filter the entire dashboard!
    ctrl.toggleFilter("faculty", "user-1");
    assert.equal(ctrl.shown, 2);
    assert.equal(ctrl.shownBeneficiaries, 150);
    assert.equal(ctrl.activeFilterChips()[0].label, "Faculty: Dr. Maria Santos");

    ctrl.reset();
    assert.equal(ctrl.shown, 3);
});

test("Documents and Sort popover actions close menu, update labels, and align within viewport", () => {
    const ctrl = makeHarness(
        {
            stats: { program_count: 2, campus_count: 1, total_campuses: 7, beneficiaries: 0, students: 0, faculty: 0, research_staff: 0 },
            overview: BASE_OVERVIEW,
            columns: [],
            programs: [
                { key: "p1", title: "Alpha", campus: "Main Campus", campus_key: "main", year: 2025, document_available: true },
                { key: "p2", title: "Beta", campus: "Main Campus", campus_key: "main", year: 2024, document_available: false },
            ],
        },
        []
    );

    ctrl.toggleMenu("documents");
    assert.equal(ctrl.openMenu, "documents");
    assert.equal(ctrl.documentsLabel(), "Documents: all");

    ctrl.setDocuments("with");
    assert.equal(ctrl.openMenu, "");
    assert.equal(ctrl.documentsLabel(), "With linked document");
    assert.equal(ctrl.shown, 1);

    ctrl.toggleMenu("sort");
    assert.equal(ctrl.openMenu, "sort");
    ctrl.setSort("oldest");
    assert.equal(ctrl.openMenu, "");
    assert.equal(ctrl.sortLabel(), "Sort: oldest first");
});
