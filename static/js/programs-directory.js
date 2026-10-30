/**
 * Alpine controller for the public Extension Programs directory (/programs/).
 *
 * Powers:
 *  - 6 live Summary KPI cards
 *  - 5 interactive Visual Overview charts (Programs per year, Programs by
 *    campus, By type of extension, By research basis, By proponent)
 *  - 4 interactive Extension Activity Leaderboards (Campuses, Colleges,
 *    Academic Programs, and Individual Faculty) with switchable metric
 *    (Most Programs, Most Completed, Most Beneficiaries)
 *  - Full multi-select Filter bar (Campuses, Years, Extension types, Research
 *    bases, Proponents, quoted-phrase Search, Columns preset/field picker,
 *    Documents filter, Sort order, Cards/Table view switch, CSV export, and
 *    Print / PDF) — even when zero programs are published yet.
 */
(function (global) {
    "use strict";

    var FIELD_TO_GROUP = {
        campus: "campuses",
        campuses: "campuses",
        college: "colleges",
        colleges: "colleges",
        program: "academicPrograms",
        academicPrograms: "academicPrograms",
        faculty: "faculty",
        year: "years",
        years: "years",
        type: "types",
        types: "types",
        basis: "bases",
        bases: "bases",
        led: "proponents",
        proponents: "proponents"
    };

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

    function parseSearchQuery(raw) {
        var phrases = [];
        var remainder = String(raw || "").replace(/"([^"]+)"/g, function (_, phrase) {
            var clean = phrase.trim().toLowerCase();
            if (clean) phrases.push(clean);
            return " ";
        });
        var tokens = remainder
            .toLowerCase()
            .split(/\s+/)
            .filter(Boolean);
        return { phrases: phrases, tokens: tokens };
    }

    function matchesSearchQuery(haystack, parsed) {
        if (!parsed.phrases.length && !parsed.tokens.length) return true;
        var text = String(haystack || "").toLowerCase();
        for (var i = 0; i < parsed.phrases.length; i++) {
            if (text.indexOf(parsed.phrases[i]) === -1) return false;
        }
        for (var j = 0; j < parsed.tokens.length; j++) {
            if (text.indexOf(parsed.tokens[j]) === -1) return false;
        }
        return true;
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

    function rankLeaderboard(baseCatalog, bucketMap, metric) {
        var activeMetric = (metric === "completed" || metric === "beneficiaries") ? metric : "programs";
        var merged = {};
        (baseCatalog || []).forEach(function (item) {
            merged[item.key] = {
                key: item.key,
                label: item.label,
                subtitle: item.subtitle || "",
                programs: 0,
                completed: 0,
                beneficiaries: 0
            };
        });
        Object.keys(bucketMap || {}).forEach(function (key) {
            var b = bucketMap[key];
            if (!merged[key]) {
                merged[key] = {
                    key: key,
                    label: b.label || key,
                    subtitle: b.subtitle || "",
                    programs: 0,
                    completed: 0,
                    beneficiaries: 0
                };
            }
            merged[key].programs = b.programs || 0;
            merged[key].completed = b.completed || 0;
            merged[key].beneficiaries = b.beneficiaries || 0;
        });

        var rows = Object.keys(merged).map(function (k) { return merged[k]; });
        rows.sort(function (a, b) {
            var primaryDiff;
            if (activeMetric === "completed") {
                primaryDiff = (b.completed - a.completed) || (b.programs - a.programs) || (b.beneficiaries - a.beneficiaries);
            } else if (activeMetric === "beneficiaries") {
                primaryDiff = (b.beneficiaries - a.beneficiaries) || (b.programs - a.programs) || (b.completed - a.completed);
            } else {
                primaryDiff = (b.programs - a.programs) || (b.completed - a.completed) || (b.beneficiaries - a.beneficiaries);
            }
            if (primaryDiff !== 0) return primaryDiff;
            var lblCmp = String(a.label || "").toLowerCase().localeCompare(String(b.label || "").toLowerCase());
            if (lblCmp !== 0) return lblCmp;
            return String(a.subtitle || "").toLowerCase().localeCompare(String(b.subtitle || "").toLowerCase());
        });

        var maxVal = 0;
        rows.forEach(function (r) {
            if (r[activeMetric] > maxVal) maxVal = r[activeMetric];
        });

        var prevSig = "";
        var curRank = 0;
        rows.forEach(function (r, idx) {
            var val = r[activeMetric] || 0;
            if (val > 0) {
                var sig = r.programs + ":" + r.completed + ":" + r.beneficiaries;
                if (sig !== prevSig) {
                    curRank = idx + 1;
                    prevSig = sig;
                }
                r.rank = curRank;
            } else {
                r.rank = null;
            }
            r.bar_percent = maxVal > 0 ? Math.round((100 * val) / maxVal) : 0;
        });

        return rows;
    }

    function comparePrograms(a, b, sortKey) {
        var titleA = String(a.title || "").toLowerCase();
        var titleB = String(b.title || "").toLowerCase();
        var yearA = Number(a.year || 0);
        var yearB = Number(b.year || 0);

        if (sortKey === "oldest") {
            var ascYearA = yearA || 9999;
            var ascYearB = yearB || 9999;
            if (ascYearA !== ascYearB) return ascYearA - ascYearB;
            return titleA.localeCompare(titleB);
        }
        if (sortKey === "title") {
            return titleA.localeCompare(titleB);
        }
        if (sortKey === "beneficiaries") {
            var benDiff = (Number(b.beneficiaries) || 0) - (Number(a.beneficiaries) || 0);
            if (benDiff !== 0) return benDiff;
            return titleA.localeCompare(titleB);
        }
        if (sortKey === "students") {
            var stuDiff = (Number(b.student_participants) || 0) - (Number(a.student_participants) || 0);
            if (stuDiff !== 0) return stuDiff;
            return titleA.localeCompare(titleB);
        }
        if (sortKey === "campus") {
            var campA = String(a.campus || "zzz").toLowerCase();
            var campB = String(b.campus || "zzz").toLowerCase();
            var campCmp = campA.localeCompare(campB);
            if (campCmp !== 0) return campCmp;
            if (yearB !== yearA) return yearB - yearA;
            return titleA.localeCompare(titleB);
        }
        if (yearB !== yearA) return yearB - yearA;
        return titleA.localeCompare(titleB);
    }

    function escapeCsvCell(val) {
        var text = val == null ? "" : String(val);
        if (/[",\r\n]/.test(text)) {
            return '"' + text.replace(/"/g, '""') + '"';
        }
        return text;
    }

    function createProgramsDirectory(seedId) {
        var el = typeof document !== "undefined" && document.getElementById
            ? document.getElementById(seedId)
            : null;
        var seed = el && el.textContent ? JSON.parse(el.textContent) : { stats: {}, overview: {}, rankings: {} };
        var stats = seed.stats || {};
        var overview = seed.overview || {};
        var rankings = seed.rankings || {};
        var columns = seed.columns || [
            { key: "year", label: "Year", default: true, minimal: true },
            { key: "campus", label: "Campus", default: true, minimal: true },
            { key: "title", label: "Program title", default: true, minimal: true },
            { key: "extension_type_label", label: "Extension type", default: true, minimal: true },
            { key: "research_basis_label", label: "Research basis", default: true, minimal: false },
            { key: "led_by_label", label: "Led by", default: true, minimal: false },
            { key: "target_community", label: "Target community / beneficiaries", default: true, minimal: true },
            { key: "duration", label: "Duration & frequency", default: true, minimal: false },
            { key: "objectives", label: "Objectives", default: false, minimal: false },
            { key: "research_output", label: "Research output applied", default: false, minimal: false },
            { key: "expected_deliverables", label: "Expected deliverables", default: false, minimal: false },
            { key: "student_participants", label: "Students", default: true, minimal: false },
            { key: "faculty_participants", label: "Faculty", default: true, minimal: false },
            { key: "research_staff_participants", label: "Research staff", default: false, minimal: false },
            { key: "beneficiaries", label: "Beneficiaries", default: true, minimal: true },
            { key: "document_url", label: "Document link", default: false, minimal: false }
        ];
        var defaultColumnKeys = columns
            .filter(function (c) { return c.default; })
            .map(function (c) { return c.key; });
        if (!defaultColumnKeys.length && columns.length) {
            defaultColumnKeys = [columns[0].key];
        }

        return {
            campuses: [],
            colleges: [],
            academicPrograms: [],
            faculty: [],
            years: [],
            types: [],
            bases: [],
            proponents: [],
            documents: "",
            sort: "newest",
            viewMode: "cards",
            rankMetric: "programs",
            expandedRankings: {
                campuses: false,
                colleges: false,
                programs: false,
                faculty: false
            },
            openMenu: "",
            query: "",
            columns: columns,
            selectedColumns: defaultColumnKeys.slice(),
            allPrograms: Array.isArray(seed.programs) ? seed.programs.slice() : null,
            filteredPrograms: [],
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
            baseRankCampuses: rankings.campuses || [],
            baseRankColleges: rankings.colleges || [],
            baseRankPrograms: rankings.programs || [],
            baseRankFaculty: rankings.faculty || [],
            rankedCampuses: rankings.campuses || [],
            rankedColleges: rankings.colleges || [],
            rankedPrograms: rankings.programs || [],
            rankedFaculty: rankings.faculty || [],
            _lastRankBuckets: {
                campuses: {},
                colleges: {},
                programs: {},
                faculty: {}
            },
            yearsByVal: buildMap(overview.years || [], "value"),
            campusesByKey: buildMap(overview.campuses || [], "key"),
            donuts: {
                extensionTypes: buildMap(overview.extension_types || [], "value"),
                researchBases: buildMap(overview.research_bases || [], "value"),
                proponents: buildMap(overview.proponents || [], "value")
            },
            normalizeCampus: normalizeCampus,
            toggleMenu: function (name) {
                this.openMenu = this.openMenu === name ? "" : name;
            },
            closeMenu: function () {
                this.openMenu = "";
            },
            setRankMetric: function (metric) {
                this.rankMetric = metric;
                this.recomputeRankings();
            },
            toggleExpandRanking: function (board) {
                this.expandedRankings[board] = !this.expandedRankings[board];
            },
            visibleRankingRows: function (board) {
                var list = board === "campuses"
                    ? this.rankedCampuses
                    : board === "colleges"
                        ? this.rankedColleges
                        : board === "programs"
                            ? this.rankedPrograms
                            : this.rankedFaculty;
                return this.expandedRankings[board] ? list : list.slice(0, 7);
            },
            rankBadgeClass: function (rank) {
                if (rank === 1) return "bg-amber-100 text-amber-800 ring-1 ring-amber-300";
                if (rank === 2) return "bg-slate-200 text-slate-800 ring-1 ring-slate-300";
                if (rank === 3) return "bg-orange-100 text-orange-800 ring-1 ring-orange-300";
                if (rank) return "bg-gray-100 text-gray-700";
                return "bg-gray-50 text-gray-400";
            },
            recomputeRankings: function () {
                var m = this.rankMetric;
                var b = this._lastRankBuckets;
                this.rankedCampuses = rankLeaderboard(this.baseRankCampuses, b.campuses, m);
                this.rankedColleges = rankLeaderboard(this.baseRankColleges, b.colleges, m);
                this.rankedPrograms = rankLeaderboard(this.baseRankPrograms, b.programs, m);
                this.rankedFaculty = rankLeaderboard(this.baseRankFaculty, b.faculty, m);
            },
            _groupList: function (field) {
                var group = FIELD_TO_GROUP[field] || field;
                return this[group] || [];
            },
            _normalizeVal: function (field, val) {
                var group = FIELD_TO_GROUP[field] || field;
                if (group === "campuses") return normalizeCampus(val);
                return String(val || "");
            },
            isSelected: function (field, val) {
                var list = this._groupList(field);
                var norm = this._normalizeVal(field, val);
                return Boolean(norm) && list.indexOf(norm) !== -1;
            },
            isCampusSelected: function (val) {
                return this.isSelected("campuses", val);
            },
            toggleFilter: function (field, val) {
                var group = FIELD_TO_GROUP[field] || field;
                var norm = this._normalizeVal(group, val);
                if (!norm || !Array.isArray(this[group])) return;
                var idx = this[group].indexOf(norm);
                if (idx === -1) {
                    this[group] = this[group].concat([norm]);
                } else {
                    var copy = this[group].slice();
                    copy.splice(idx, 1);
                    this[group] = copy;
                }
                this.apply();
            },
            selectAllFacet: function (field) {
                var group = FIELD_TO_GROUP[field] || field;
                if (group === "campuses") {
                    this.campuses = this.baseCampuses.map(function (c) { return c.key; });
                } else if (group === "years") {
                    this.years = this.baseYears.map(function (y) { return String(y.value); });
                } else if (group === "types") {
                    this.types = this.baseExtensionTypes.map(function (t) { return String(t.value); });
                } else if (group === "bases") {
                    this.bases = this.baseResearchBases.map(function (b) { return String(b.value); });
                } else if (group === "proponents") {
                    this.proponents = this.baseProponents.map(function (p) { return String(p.value); });
                }
                this.apply();
            },
            clearFacet: function (field) {
                var group = FIELD_TO_GROUP[field] || field;
                if (Array.isArray(this[group])) {
                    this[group] = [];
                    this.apply();
                }
            },
            facetCount: function (field) {
                return this._groupList(field).length;
            },
            facetButtonLabel: function (field, prefix) {
                var group = FIELD_TO_GROUP[field] || field;
                var list = this[group] || [];
                if (!list.length) return prefix + ": All";
                if (list.length === 1) {
                    return prefix + ": " + this._optionLabel(group, list[0]);
                }
                return prefix + ": " + list.length + " selected";
            },
            _optionLabel: function (group, val) {
                var i;
                if (group === "campuses") {
                    for (i = 0; i < this.baseCampuses.length; i++) {
                        if (this.baseCampuses[i].key === val) return this.baseCampuses[i].label;
                    }
                    return val;
                }
                if (group === "colleges") {
                    for (i = 0; i < this.baseRankColleges.length; i++) {
                        if (this.baseRankColleges[i].key === val) return this.baseRankColleges[i].label;
                    }
                    return val;
                }
                if (group === "academicPrograms") {
                    for (i = 0; i < this.baseRankPrograms.length; i++) {
                        if (this.baseRankPrograms[i].key === val) return this.baseRankPrograms[i].label;
                    }
                    return val;
                }
                if (group === "faculty") {
                    for (i = 0; i < this.baseRankFaculty.length; i++) {
                        if (this.baseRankFaculty[i].key === val) return this.baseRankFaculty[i].label;
                    }
                    return val;
                }
                if (group === "years") return val;
                var source = group === "types"
                    ? this.baseExtensionTypes
                    : group === "bases"
                        ? this.baseResearchBases
                        : this.baseProponents;
                for (i = 0; i < source.length; i++) {
                    if (String(source[i].value) === String(val)) {
                        return source[i].short_label || source[i].label;
                    }
                }
                return val;
            },
            activeFilterCount: function () {
                return (
                    this.campuses.length +
                    this.colleges.length +
                    this.academicPrograms.length +
                    this.faculty.length +
                    this.years.length +
                    this.types.length +
                    this.bases.length +
                    this.proponents.length +
                    (this.documents ? 1 : 0) +
                    (this.query.trim() ? 1 : 0)
                );
            },
            hasActiveFilters: function () {
                return this.activeFilterCount() > 0;
            },
            activeFilterChips: function () {
                var self = this;
                var chips = [];
                this.campuses.forEach(function (v) {
                    chips.push({ id: "campuses:" + v, group: "campuses", value: v, label: self._optionLabel("campuses", v) });
                });
                this.colleges.forEach(function (v) {
                    chips.push({ id: "colleges:" + v, group: "colleges", value: v, label: "College: " + self._optionLabel("colleges", v) });
                });
                this.academicPrograms.forEach(function (v) {
                    chips.push({ id: "academicPrograms:" + v, group: "academicPrograms", value: v, label: "Program: " + self._optionLabel("academicPrograms", v) });
                });
                this.faculty.forEach(function (v) {
                    chips.push({ id: "faculty:" + v, group: "faculty", value: v, label: "Faculty: " + self._optionLabel("faculty", v) });
                });
                this.years.forEach(function (v) {
                    chips.push({ id: "years:" + v, group: "years", value: v, label: "Year: " + v });
                });
                this.types.forEach(function (v) {
                    chips.push({ id: "types:" + v, group: "types", value: v, label: self._optionLabel("types", v) });
                });
                this.bases.forEach(function (v) {
                    chips.push({ id: "bases:" + v, group: "bases", value: v, label: self._optionLabel("bases", v) });
                });
                this.proponents.forEach(function (v) {
                    chips.push({ id: "proponents:" + v, group: "proponents", value: v, label: "Proponent: " + self._optionLabel("proponents", v) });
                });
                if (this.documents === "with") {
                    chips.push({ id: "documents:with", group: "documents", value: "with", label: "With linked document" });
                } else if (this.documents === "without") {
                    chips.push({ id: "documents:without", group: "documents", value: "without", label: "No document" });
                }
                if (this.query.trim()) {
                    chips.push({ id: "query", group: "query", value: this.query.trim(), label: "Search: " + this.query.trim() });
                }
                return chips;
            },
            removeChip: function (chip) {
                if (!chip) return;
                if (chip.group === "documents") {
                    this.documents = "";
                    this.apply();
                } else if (chip.group === "query") {
                    this.query = "";
                    this.apply();
                } else {
                    this.toggleFilter(chip.group, chip.value);
                }
            },
            hasColumn: function (key) {
                return this.selectedColumns.indexOf(key) !== -1;
            },
            toggleColumn: function (key) {
                var idx = this.selectedColumns.indexOf(key);
                if (idx !== -1) {
                    if (this.selectedColumns.length <= 1) return;
                    var next = this.selectedColumns.slice();
                    next.splice(idx, 1);
                    this.selectedColumns = next;
                } else {
                    var allowed = this.selectedColumns.concat([key]);
                    this.selectedColumns = this.columns
                        .map(function (c) { return c.key; })
                        .filter(function (k) { return allowed.indexOf(k) !== -1; });
                }
            },
            setColumnPreset: function (preset) {
                if (preset === "minimal") {
                    this.selectedColumns = this.columns
                        .filter(function (c) { return c.minimal; })
                        .map(function (c) { return c.key; });
                } else if (preset === "all") {
                    this.selectedColumns = this.columns.map(function (c) { return c.key; });
                } else {
                    this.selectedColumns = this.columns
                        .filter(function (c) { return c.default; })
                        .map(function (c) { return c.key; });
                }
            },
            columnSummaryLabel: function () {
                var minKeys = this.columns.filter(function (c) { return c.minimal; }).map(function (c) { return c.key; }).join(",");
                var defKeys = this.columns.filter(function (c) { return c.default; }).map(function (c) { return c.key; }).join(",");
                var allKeys = this.columns.map(function (c) { return c.key; }).join(",");
                var curKeys = this.selectedColumns.join(",");
                if (curKeys === defKeys) return "Columns: Default";
                if (curKeys === minKeys) return "Columns: Minimal";
                if (curKeys === allKeys) return "Columns: All " + this.columns.length;
                return "Columns: Custom";
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
            _matchesRecord: function (rec, parsedQuery) {
                var campusKey = rec.campus_key || normalizeCampus(rec.campus);
                if (this.campuses.length && this.campuses.indexOf(campusKey) === -1) return false;
                if (this.colleges.length && this.colleges.indexOf(String(rec.college_key || "")) === -1) return false;
                if (this.academicPrograms.length && this.academicPrograms.indexOf(String(rec.program_key || "")) === -1) return false;
                if (this.faculty.length) {
                    var fKeys = rec.faculty_keys || [];
                    var hasFac = false;
                    for (var f = 0; f < this.faculty.length; f++) {
                        if (fKeys.indexOf(this.faculty[f]) !== -1) {
                            hasFac = true;
                            break;
                        }
                    }
                    if (!hasFac) return false;
                }
                if (this.years.length && this.years.indexOf(String(rec.year || "")) === -1) return false;
                if (this.types.length && this.types.indexOf(String(rec.extension_type || "")) === -1) return false;
                if (this.bases.length && this.bases.indexOf(String(rec.research_basis || "")) === -1) return false;
                if (this.proponents.length && this.proponents.indexOf(String(rec.led_by || "")) === -1) return false;
                if (this.documents === "with" && !rec.document_available) return false;
                if (this.documents === "without" && rec.document_available) return false;
                if (!matchesSearchQuery(rec._searchText, parsedQuery)) return false;
                return true;
            },
            apply: function () {
                var self = this;
                var parsedQuery = parseSearchQuery(this.query);
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
                var rankBuckets = {
                    campuses: {},
                    colleges: {},
                    programs: {},
                    faculty: {}
                };

                function addRankCount(bucket, key, label, subtitle, isCompleted, benCount) {
                    if (!key) return;
                    if (!bucket[key]) {
                        bucket[key] = {
                            label: label || key,
                            subtitle: subtitle || "",
                            programs: 0,
                            completed: 0,
                            beneficiaries: 0
                        };
                    }
                    bucket[key].programs += 1;
                    bucket[key].completed += isCompleted ? 1 : 0;
                    bucket[key].beneficiaries += benCount;
                }

                var root = this.$el || this.$root;
                var cards = root && root.querySelectorAll ? root.querySelectorAll("[data-program]") : [];
                var cardMap = {};
                var records = [];

                if (Array.isArray(this.allPrograms)) {
                    records = this.allPrograms.map(function (p) {
                        var facNames = (p.faculty_credits || []).map(function (fc) { return fc.label; }).join(" ");
                        return Object.assign({}, p, {
                            _searchText: [
                                p.title,
                                p.campus,
                                p.college,
                                p.department,
                                facNames,
                                p.target_community,
                                p.objectives,
                                p.research_output,
                                p.expected_deliverables,
                                p.extension_type_label,
                                p.research_basis_label,
                                p.led_by_label,
                                p.year
                            ].join(" ")
                        });
                    });
                    for (var cIdx = 0; cIdx < cards.length; cIdx++) {
                        var cKey = cards[cIdx].dataset && cards[cIdx].dataset.key;
                        if (cKey) cardMap[cKey] = cards[cIdx];
                    }
                } else {
                    for (var i = 0; i < cards.length; i++) {
                        var d = cards[i].dataset || {};
                        var key = d.key || ("dom-" + i);
                        cardMap[key] = cards[i];
                        records.push({
                            key: key,
                            title: d.title || d.search || "",
                            campus: d.campus || "",
                            campus_key: d.campusKey || normalizeCampus(d.campus),
                            college: d.college || "",
                            college_key: d.collegeKey || "",
                            department: d.department || "",
                            program_key: d.programKey || "",
                            faculty_credits: [],
                            faculty_keys: d.facultyKeys ? d.facultyKeys.split(",").filter(Boolean) : [],
                            is_completed: d.completed === "true",
                            year: d.year ? parseInt(d.year, 10) || d.year : "",
                            extension_type: d.type || "",
                            research_basis: d.basis || "",
                            led_by: d.led || "",
                            beneficiaries: parseInt(d.beneficiaries || "0", 10) || 0,
                            student_participants: parseInt(d.students || "0", 10) || 0,
                            faculty_participants: parseInt(d.faculty || "0", 10) || 0,
                            research_staff_participants: parseInt(d.researchStaff || "0", 10) || 0,
                            document_available: d.hasDocument === "true" || Boolean(d.documentUrl),
                            _searchText: d.search || ""
                        });
                    }
                }

                var matched = [];
                records.forEach(function (rec) {
                    var ok = self._matchesRecord(rec, parsedQuery);
                    var cardEl = cardMap[rec.key];
                    if (cardEl && cardEl.style) {
                        cardEl.style.display = ok ? "" : "none";
                    }
                    if (ok) {
                        matched.push(rec);
                        shown += 1;
                        var benVal = Number(rec.beneficiaries) || 0;
                        var isComp = Boolean(rec.is_completed);
                        beneficiaries += benVal;
                        students += Number(rec.student_participants) || 0;
                        faculty += Number(rec.faculty_participants) || 0;
                        researchStaff += Number(rec.research_staff_participants) || 0;

                        var ck = rec.campus_key || normalizeCampus(rec.campus);
                        if (ck) {
                            campusSet[ck] = true;
                            campusCounts[ck] = (campusCounts[ck] || 0) + 1;
                            addRankCount(rankBuckets.campuses, ck, rec.campus || ck, "ISPSC Campus", isComp, benVal);
                        }
                        if (rec.college_key) {
                            addRankCount(rankBuckets.colleges, rec.college_key, rec.college, rec.campus, isComp, benVal);
                        }
                        if (rec.program_key) {
                            var progSub = [rec.campus, rec.college].filter(Boolean).join(" · ");
                            addRankCount(rankBuckets.programs, rec.program_key, rec.department, progSub, isComp, benVal);
                        }
                        (rec.faculty_credits || []).forEach(function (fc) {
                            addRankCount(rankBuckets.faculty, fc.key, fc.label, fc.subtitle, isComp, benVal);
                        });

                        if (rec.year) {
                            yearCounts[String(rec.year)] = (yearCounts[String(rec.year)] || 0) + 1;
                        }
                        if (rec.extension_type) {
                            typeCounts[rec.extension_type] = (typeCounts[rec.extension_type] || 0) + 1;
                        }
                        if (rec.research_basis) {
                            basisCounts[rec.research_basis] = (basisCounts[rec.research_basis] || 0) + 1;
                        }
                        if (rec.led_by) {
                            ledCounts[rec.led_by] = (ledCounts[rec.led_by] || 0) + 1;
                        }
                    }
                });

                var sortKey = this.sort || "newest";
                matched.sort(function (a, b) {
                    return comparePrograms(a, b, sortKey);
                });
                this.filteredPrograms = matched;

                var grid = root && root.querySelector ? root.querySelector("[data-program-grid]") : null;
                if (grid && grid.appendChild) {
                    matched.forEach(function (rec) {
                        var cardEl = cardMap[rec.key];
                        if (cardEl) grid.appendChild(cardEl);
                    });
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

                this._lastRankBuckets = rankBuckets;
                this.recomputeRankings();
            },
            formatCell: function (program, colKey) {
                var val = program[colKey];
                if (
                    colKey === "student_participants" ||
                    colKey === "faculty_participants" ||
                    colKey === "research_staff_participants" ||
                    colKey === "beneficiaries"
                ) {
                    var num = Number(val) || 0;
                    return num > 0 ? num.toLocaleString() : "—";
                }
                return val ? String(val) : "—";
            },
            downloadCsv: function () {
                var self = this;
                var activeCols = this.columns.filter(function (c) {
                    return self.selectedColumns.indexOf(c.key) !== -1;
                });
                var lines = [
                    activeCols.map(function (c) { return escapeCsvCell(c.label); }).join(",")
                ];
                this.filteredPrograms.forEach(function (prog) {
                    var row = activeCols.map(function (c) {
                        var raw = prog[c.key];
                        if (c.key === "document_url" && raw && typeof window !== "undefined" && window.location) {
                            raw = new URL(raw, window.location.origin).href;
                        }
                        return escapeCsvCell(raw == null ? "" : raw);
                    });
                    lines.push(row.join(","));
                });
                var csvContent = "\uFEFF" + lines.join("\r\n");
                if (typeof Blob !== "undefined" && typeof URL !== "undefined" && URL.createObjectURL && typeof document !== "undefined") {
                    var blob = new Blob([csvContent], { type: "text/csv;charset=utf-8;" });
                    var url = URL.createObjectURL(blob);
                    var link = document.createElement("a");
                    link.href = url;
                    link.download = "ispsc-extension-programs.csv";
                    document.body.appendChild(link);
                    link.click();
                    document.body.removeChild(link);
                    URL.revokeObjectURL(url);
                }
                return csvContent;
            },
            printReport: function () {
                if (typeof window !== "undefined" && typeof window.print === "function") {
                    window.print();
                }
            },
            reset: function () {
                this.campuses = [];
                this.colleges = [];
                this.academicPrograms = [];
                this.faculty = [];
                this.years = [];
                this.types = [];
                this.bases = [];
                this.proponents = [];
                this.documents = "";
                this.sort = "newest";
                this.query = "";
                this.openMenu = "";
                this.apply();
            }
        };
    }

    global.nexusProgramsDirectory = createProgramsDirectory;
    global.NexusProgramsDirectory = {
        create: createProgramsDirectory,
        normalizeCampus: normalizeCampus,
        parseSearchQuery: parseSearchQuery,
        matchesSearchQuery: matchesSearchQuery,
        recomputeDonut: recomputeDonut,
        rankLeaderboard: rankLeaderboard
    };
})(typeof window !== "undefined" ? window : globalThis);
