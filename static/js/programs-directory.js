/**
 * Alpine controller for the public Extension Programs directory (/programs/).
 *
 * Reads the server-rendered JSON seed (`stats` + `overview`) so the 6 Summary
 * KPI cards and all 5 Visual Overview charts (Programs per year, Programs by
 * campus, By type of extension, By research basis, By proponent) initialise
 * cleanly — even when zero programs are published yet — and recalculate live
 * whenever any chart bar, donut segment, legend row, or filter changes.
 */
(function (global) {
    "use strict";

    function normalizeCampus(val) {
        return String(val || "")
            .toLowerCase()
            .replace(/campus/g, "")
            .replace(/[^a-z0-9]/g, "");
    }

    function buildMap(list, keyField) {
        var map = {};
        (list || []).forEach(function (item) {
            map[String(item[keyField])] = item;
        });
        return map;
    }

    function recomputeDonut(baseList, counts, denom) {
        var cum = 0;
        var out = {};
        (baseList || []).forEach(function (item) {
            var count = counts[item.value] || 0;
            var percent = denom > 0 ? Math.round((100 * count) / denom) : 0;
            var dash = denom > 0 && count > 0 ? Number(((100 * count) / denom).toFixed(3)) : 0;
            var gap = Number((100 - dash).toFixed(3));
            var dashoffset = Number((25 - cum).toFixed(3));
            cum += dash;
            out[String(item.value)] = {
                value: item.value,
                label: item.label,
                short_label: item.short_label,
                color: item.color,
                count: count,
                percent: percent,
                dash: dash,
                gap: gap,
                dashoffset: dashoffset
            };
        });
        return out;
    }

    function createProgramsDirectory(seedId) {
        var el = typeof document !== "undefined" && document.getElementById
            ? document.getElementById(seedId)
            : null;
        var seed = el && el.textContent ? JSON.parse(el.textContent) : { stats: {}, overview: {} };
        var stats = seed.stats || {};
        var overview = seed.overview || {};

        return {
            campus: "",
            year: "",
            type: "",
            basis: "",
            led: "",
            query: "",
            total: stats.program_count || 0,
            totalCampuses: stats.total_campuses || 0,
            shown: stats.program_count || 0,
            shownCampuses: stats.campus_count || 0,
            shownBeneficiaries: stats.beneficiaries || 0,
            shownStudents: stats.students || 0,
            shownFaculty: stats.faculty || 0,
            shownResearchStaff: stats.research_staff || 0,
            baseYears: overview.years || [],
            baseCampuses: overview.campuses || [],
            baseExtensionTypes: overview.extension_types || [],
            baseResearchBases: overview.research_bases || [],
            baseProponents: overview.proponents || [],
            yearsByVal: buildMap(overview.years || [], "value"),
            campusesByKey: buildMap(overview.campuses || [], "key"),
            donuts: {
                extensionTypes: buildMap(overview.extension_types || [], "value"),
                researchBases: buildMap(overview.research_bases || [], "value"),
                proponents: buildMap(overview.proponents || [], "value")
            },
            normalizeCampus: normalizeCampus,
            hasActiveFilters: function () {
                return Boolean(
                    this.campus ||
                    this.year ||
                    this.type ||
                    this.basis ||
                    this.led ||
                    this.query.trim()
                );
            },
            isCampusSelected: function (val) {
                return Boolean(this.campus) && normalizeCampus(this.campus) === normalizeCampus(val);
            },
            toggleFilter: function (field, val) {
                if (field === "campus") {
                    this.campus = this.isCampusSelected(val) ? "" : String(val);
                } else {
                    this[field] = String(this[field]) === String(val) ? "" : String(val);
                }
                this.apply();
            },
            yearStat: function (val) {
                return this.yearsByVal[String(val)] || { count: 0, percent: 0, bar_percent: 0 };
            },
            campusStat: function (key) {
                return this.campusesByKey[String(key)] || { count: 0, percent: 0 };
            },
            donutStat: function (group, val) {
                var bucket = this.donuts[group] || {};
                return bucket[String(val)] || { count: 0, percent: 0, dash: 0, gap: 100, dashoffset: 25 };
            },
            apply: function () {
                var needle = this.query.trim().toLowerCase();
                var targetCampusKey = normalizeCampus(this.campus);
                var shown = 0;
                var beneficiaries = 0;
                var students = 0;
                var faculty = 0;
                var researchStaff = 0;
                var campusSet = {};
                var yearCounts = {};
                var campusCounts = {};
                var typeCounts = {};
                var basisCounts = {};
                var ledCounts = {};

                var root = this.$el || this.$root;
                var cards = root && root.querySelectorAll ? root.querySelectorAll("[data-program]") : [];
                for (var i = 0; i < cards.length; i++) {
                    var card = cards[i];
                    var d = card.dataset || {};
                    var cardCampusKey = d.campusKey || normalizeCampus(d.campus);
                    var matches = (!targetCampusKey || cardCampusKey === targetCampusKey)
                        && (!this.year || String(d.year) === String(this.year))
                        && (!this.type || d.type === this.type)
                        && (!this.basis || d.basis === this.basis)
                        && (!this.led || d.led === this.led)
                        && (!needle || (d.search || "").indexOf(needle) !== -1);

                    if (card.style) {
                        card.style.display = matches ? "" : "none";
                    }
                    if (matches) {
                        shown += 1;
                        beneficiaries += parseInt(d.beneficiaries || "0", 10) || 0;
                        students += parseInt(d.students || "0", 10) || 0;
                        faculty += parseInt(d.faculty || "0", 10) || 0;
                        researchStaff += parseInt(d.researchStaff || "0", 10) || 0;
                        if (cardCampusKey) {
                            campusSet[cardCampusKey] = true;
                            campusCounts[cardCampusKey] = (campusCounts[cardCampusKey] || 0) + 1;
                        }
                        if (d.year) {
                            yearCounts[String(d.year)] = (yearCounts[String(d.year)] || 0) + 1;
                        }
                        if (d.type) {
                            typeCounts[d.type] = (typeCounts[d.type] || 0) + 1;
                        }
                        if (d.basis) {
                            basisCounts[d.basis] = (basisCounts[d.basis] || 0) + 1;
                        }
                        if (d.led) {
                            ledCounts[d.led] = (ledCounts[d.led] || 0) + 1;
                        }
                    }
                }

                this.shown = shown;
                this.shownCampuses = Object.keys(campusSet).length;
                this.shownBeneficiaries = beneficiaries;
                this.shownStudents = students;
                this.shownFaculty = faculty;
                this.shownResearchStaff = researchStaff;

                var maxYear = 0;
                this.baseYears.forEach(function (y) {
                    var c = yearCounts[String(y.value)] || 0;
                    if (c > maxYear) maxYear = c;
                });
                var nextYears = {};
                this.baseYears.forEach(function (y) {
                    var c = yearCounts[String(y.value)] || 0;
                    nextYears[String(y.value)] = {
                        value: y.value,
                        label: y.label,
                        short_label: y.short_label,
                        count: c,
                        percent: shown > 0 ? Math.round((100 * c) / shown) : 0,
                        bar_percent: maxYear > 0 ? Math.round((100 * c) / maxYear) : 0
                    };
                });
                this.yearsByVal = nextYears;

                var nextCampuses = {};
                this.baseCampuses.forEach(function (cItem) {
                    var c = campusCounts[cItem.key] || 0;
                    nextCampuses[String(cItem.key)] = {
                        key: cItem.key,
                        value: cItem.value,
                        label: cItem.label,
                        count: c,
                        percent: shown > 0 ? Math.round((100 * c) / shown) : 0
                    };
                });
                this.campusesByKey = nextCampuses;

                this.donuts = {
                    extensionTypes: recomputeDonut(this.baseExtensionTypes, typeCounts, shown),
                    researchBases: recomputeDonut(this.baseResearchBases, basisCounts, shown),
                    proponents: recomputeDonut(this.baseProponents, ledCounts, shown)
                };
            },
            reset: function () {
                this.campus = "";
                this.year = "";
                this.type = "";
                this.basis = "";
                this.led = "";
                this.query = "";
                this.apply();
            }
        };
    }

    global.nexusProgramsDirectory = createProgramsDirectory;
    global.NexusProgramsDirectory = {
        create: createProgramsDirectory,
        normalizeCampus: normalizeCampus,
        recomputeDonut: recomputeDonut
    };
})(typeof window !== "undefined" ? window : globalThis);
