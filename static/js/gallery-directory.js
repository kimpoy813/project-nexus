/**
 * Alpine controller for the public Program Gallery (/gallery/).
 *
 * Powers:
 *  - 5 live Summary KPI cards (#gallery-summary)
 *  - 3 interactive Visual Overview charts (#gallery-overview: Photos per year,
 *    Photos by campus, By documentation source)
 *  - Multi-select Filter & Sort popover menus (#gallery-filters: Search,
 *    Campuses, Years, Sources, Sort order, Active filter chips, and Reset)
 *  - Live photo grid filtering and non-destructive CSS order sorting (#gallery-photos)
 *    even when zero photos are published yet.
 */
(function (global) {
    "use strict";

    var FIELD_TO_GROUP = {
        campus: "campuses",
        campuses: "campuses",
        year: "years",
        years: "years",
        source: "sources",
        sources: "sources"
    };

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

    function sortPhotos(list, sortBy) {
        var copy = list.slice();
        copy.sort(function (a, b) {
            if (sortBy === "oldest") {
                var ya = parseInt(a.year, 10) || 9999;
                var yb = parseInt(b.year, 10) || 9999;
                if (ya !== yb) return ya - yb;
                var ta = a.taken_on || "9999-99-99";
                var tb = b.taken_on || "9999-99-99";
                if (ta !== tb) return ta.localeCompare(tb);
                return (a.order_index || 0) - (b.order_index || 0);
            }
            if (sortBy === "program_asc") {
                var pa = String(a.subtitle || a.title || "").toLowerCase();
                var pb = String(b.subtitle || b.title || "").toLowerCase();
                if (pa !== pb) return pa.localeCompare(pb);
                return (a.order_index || 0) - (b.order_index || 0);
            }
            if (sortBy === "campus_asc") {
                var ca = String(a.campus || "zzz").toLowerCase();
                var cb = String(b.campus || "zzz").toLowerCase();
                if (ca !== cb) return ca.localeCompare(cb);
                return (a.order_index || 0) - (b.order_index || 0);
            }
            // Default: newest
            var nYa = parseInt(a.year, 10) || 0;
            var nYb = parseInt(b.year, 10) || 0;
            if (nYb !== nYa) return nYb - nYa;
            var nTa = a.taken_on || "";
            var nTb = b.taken_on || "";
            if (nTb !== nTa) return nTb.localeCompare(nTa);
            return (a.order_index || 0) - (b.order_index || 0);
        });
        return copy;
    }

    function createController(seed) {
        var baseOverview = (seed && seed.overview) || {};
        var baseStats = (seed && seed.stats) || {};
        var baseCampuses = baseOverview.campuses || [];
        var baseYears = baseOverview.years || [];
        var baseSources = baseOverview.sources || [];
        var allPhotos = ((seed && seed.photos) || []).map(function (p, index) {
            var copy = Object.assign({}, p);
            copy.order_index = typeof p.order_index === "number" ? p.order_index : index;
            copy._haystack = [
                p.title || "",
                p.caption || "",
                p.subtitle || "",
                p.campus || "",
                p.year || "",
                p.source_label || ""
            ].join(" ");
            return copy;
        });

        return {
            q: "",
            campuses: [],
            years: [],
            sources: [],
            sortBy: "newest",
            openMenu: "",
            menuAlign: "left",

            total: allPhotos.length,
            shown: baseStats.photo_count || 0,
            shownActivities: baseStats.activity_count || 0,
            shownCampuses: baseStats.campus_count || 0,
            shownTerminal: baseStats.terminal_report_count || 0,
            shownLegacy: baseStats.legacy_count || 0,
            chartDenom: baseStats.photo_count || 0,

            baseCampuses: baseCampuses,
            baseYears: baseYears,
            baseSources: baseSources,
            yearsMap: buildMap(baseYears, "value"),
            campusesMap: buildMap(baseCampuses, "key"),
            sourcesMap: buildMap(baseSources, "value"),
            filteredKeys: allPhotos.map(function (p) { return p.key; }),

            toggleMenu: function (name, evt) {
                if (this.openMenu === name) {
                    this.openMenu = "";
                    return;
                }
                var align = "left";
                var trigger = evt && evt.currentTarget;
                if (
                    trigger &&
                    typeof trigger.getBoundingClientRect === "function" &&
                    typeof window !== "undefined" &&
                    window.innerWidth
                ) {
                    var rect = trigger.getBoundingClientRect();
                    var panelWidth = 256;
                    if (rect.left + panelWidth > window.innerWidth - 16 && rect.right >= panelWidth) {
                        align = "right";
                    }
                }
                this.menuAlign = align;
                this.openMenu = name;
            },

            closeMenu: function () {
                this.openMenu = "";
            },

            _groupList: function (field) {
                var group = FIELD_TO_GROUP[field] || field;
                return this[group] || [];
            },

            isSelected: function (field, val) {
                var list = this._groupList(field);
                var clean = String(val || "");
                return Boolean(clean) && list.indexOf(clean) !== -1;
            },

            toggleFilter: function (field, val) {
                var group = FIELD_TO_GROUP[field] || field;
                var clean = String(val || "");
                if (!clean || !Array.isArray(this[group])) return;
                var idx = this[group].indexOf(clean);
                if (idx === -1) {
                    this[group] = this[group].concat([clean]);
                } else {
                    var copy = this[group].slice();
                    copy.splice(idx, 1);
                    this[group] = copy;
                }
                this.apply();
            },

            toggleCampus: function (key) {
                this.toggleFilter("campuses", key);
            },

            toggleYear: function (yr) {
                this.toggleFilter("years", yr);
            },

            toggleSource: function (src) {
                this.toggleFilter("sources", src);
            },

            selectAllFacet: function (field) {
                var group = FIELD_TO_GROUP[field] || field;
                if (group === "campuses") {
                    this.campuses = this.baseCampuses.map(function (c) { return String(c.key); });
                } else if (group === "years") {
                    this.years = this.baseYears.map(function (y) { return String(y.value); });
                } else if (group === "sources") {
                    this.sources = this.baseSources.map(function (s) { return String(s.value); });
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

            _optionLabel: function (group, val) {
                var i;
                if (group === "campuses") {
                    for (i = 0; i < this.baseCampuses.length; i++) {
                        if (String(this.baseCampuses[i].key) === String(val)) {
                            return this.baseCampuses[i].label;
                        }
                    }
                    return val;
                }
                if (group === "years") return val;
                for (i = 0; i < this.baseSources.length; i++) {
                    if (String(this.baseSources[i].value) === String(val)) {
                        return this.baseSources[i].short_label || this.baseSources[i].label;
                    }
                }
                return val;
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

            sortLabel: function () {
                var labels = {
                    newest: "Sort: newest first",
                    oldest: "Sort: oldest first",
                    program_asc: "Sort: program A–Z",
                    campus_asc: "Sort: campus A–Z"
                };
                return labels[this.sortBy] || "Sort: newest first";
            },

            setSort: function (val) {
                this.sortBy = val || "newest";
                this.openMenu = "";
                this.apply();
            },

            hasActiveFilters: function () {
                return this.activeFilterCount() > 0;
            },

            activeFilterCount: function () {
                return (
                    this.campuses.length +
                    this.years.length +
                    this.sources.length +
                    (this.q.trim() ? 1 : 0)
                );
            },

            activeFilterChips: function () {
                var self = this;
                var chips = [];
                this.campuses.forEach(function (v) {
                    chips.push({ id: "campuses:" + v, group: "campuses", value: v, label: self._optionLabel("campuses", v) });
                });
                this.years.forEach(function (v) {
                    chips.push({ id: "years:" + v, group: "years", value: v, label: "Year: " + v });
                });
                this.sources.forEach(function (v) {
                    chips.push({ id: "sources:" + v, group: "sources", value: v, label: self._optionLabel("sources", v) });
                });
                if (this.q.trim()) {
                    chips.push({ id: "q", group: "q", value: this.q.trim(), label: "Search: " + this.q.trim() });
                }
                return chips;
            },

            removeChip: function (chip) {
                if (!chip) return;
                if (chip.group === "q") {
                    this.q = "";
                    this.apply();
                } else {
                    this.toggleFilter(chip.group, chip.value);
                }
            },

            reset: function () {
                this.q = "";
                this.campuses = [];
                this.years = [];
                this.sources = [];
                this.sortBy = "newest";
                this.openMenu = "";
                this.apply();
            },

            matchesPhoto: function (photo, parsedSearch) {
                if (!matchesSearchQuery(photo._haystack, parsedSearch)) {
                    return false;
                }
                if (this.campuses.length && this.campuses.indexOf(String(photo.campus_key || "")) === -1) {
                    return false;
                }
                if (this.years.length && this.years.indexOf(String(photo.year || "")) === -1) {
                    return false;
                }
                if (this.sources.length && this.sources.indexOf(String(photo.source || "")) === -1) {
                    return false;
                }
                return true;
            },

            apply: function () {
                var self = this;
                var parsedSearch = parseSearchQuery(this.q);

                var matched = allPhotos.filter(function (photo) {
                    return self.matchesPhoto(photo, parsedSearch);
                });
                var ordered = sortPhotos(matched, this.sortBy);
                this.filteredKeys = ordered.map(function (p) { return p.key; });

                var activitySet = {};
                var campusSet = {};
                var terminalCount = 0;
                var legacyCount = 0;
                var yearCounts = {};
                var campusCounts = {};
                var sourceCounts = {};

                ordered.forEach(function (p) {
                    if (p.proposal_id) activitySet[String(p.proposal_id)] = true;
                    if (p.campus_key) {
                        campusSet[p.campus_key] = true;
                        campusCounts[p.campus_key] = (campusCounts[p.campus_key] || 0) + 1;
                    }
                    if (p.year) {
                        yearCounts[String(p.year)] = (yearCounts[String(p.year)] || 0) + 1;
                    }
                    if (p.source) {
                        sourceCounts[p.source] = (sourceCounts[p.source] || 0) + 1;
                    }
                    if (p.source === "LEGACY") {
                        legacyCount += 1;
                    } else {
                        terminalCount += 1;
                    }
                });

                var denom = ordered.length;
                this.shown = denom;
                this.chartDenom = denom;
                this.shownActivities = Object.keys(activitySet).length;
                this.shownCampuses = Object.keys(campusSet).length;
                this.shownTerminal = terminalCount;
                this.shownLegacy = legacyCount;

                var maxYear = 0;
                baseYears.forEach(function (yr) {
                    var c = yearCounts[String(yr.value)] || 0;
                    if (c > maxYear) maxYear = c;
                });
                var nextYears = {};
                baseYears.forEach(function (yr) {
                    var c = yearCounts[String(yr.value)] || 0;
                    nextYears[String(yr.value)] = {
                        value: yr.value,
                        label: yr.label,
                        short_label: yr.short_label,
                        count: c,
                        percent: denom > 0 ? Math.round((100 * c) / denom) : 0,
                        bar_percent: maxYear > 0 ? Math.round((100 * c) / maxYear) : 0
                    };
                });
                this.yearsMap = nextYears;

                var nextCampuses = {};
                baseCampuses.forEach(function (camp) {
                    var c = campusCounts[camp.key] || 0;
                    nextCampuses[String(camp.key)] = {
                        key: camp.key,
                        value: camp.value,
                        label: camp.label,
                        count: c,
                        percent: denom > 0 ? Math.round((100 * c) / denom) : 0
                    };
                });
                this.campusesMap = nextCampuses;

                this.sourcesMap = recomputeDonut(
                    baseSources,
                    sourceCounts,
                    denom
                );

                this.syncDom(ordered);
            },

            syncDom: function (ordered) {
                if (!this.$el || typeof this.$el.querySelector !== "function") return;
                var grid = this.$el.querySelector("[data-gallery-grid]");
                if (!grid) return;

                var posByKey = {};
                ordered.forEach(function (item, idx) {
                    posByKey[item.key] = idx + 1;
                });

                var figures = grid.querySelectorAll("[data-gallery-key]");
                for (var i = 0; i < figures.length; i++) {
                    var fig = figures[i];
                    var key = fig.getAttribute("data-gallery-key") || "";
                    var pos = posByKey[key];
                    if (pos) {
                        fig.hidden = false;
                        fig.style.order = String(pos);
                    } else {
                        fig.hidden = true;
                        fig.style.order = "";
                    }
                }
            },

            yearStat: function (val) {
                return this.yearsMap[String(val)] || { count: 0, percent: 0, bar_percent: 0 };
            },

            campusStat: function (key) {
                return this.campusesMap[String(key)] || { count: 0, percent: 0 };
            },

            sourceStat: function (val) {
                return this.sourcesMap[String(val)] || {
                    count: 0,
                    percent: 0,
                    dash: 0,
                    gap: 100,
                    dashoffset: 25
                };
            },

            sourceSegments: function () {
                var self = this;
                return baseSources.map(function (item) {
                    return self.sourcesMap[String(item.value)] || item;
                });
            }
        };
    }

    function nexusGalleryDirectory(seedId) {
        var seed = {};
        if (seedId && global.document && typeof global.document.getElementById === "function") {
            var el = global.document.getElementById(seedId);
            if (el && el.textContent) {
                try {
                    seed = JSON.parse(el.textContent);
                } catch (_err) {
                    seed = {};
                }
            }
        }
        return createController(seed);
    }

    global.NexusGalleryDirectory = {
        parseSearchQuery: parseSearchQuery,
        matchesSearchQuery: matchesSearchQuery,
        recomputeDonut: recomputeDonut,
        sortPhotos: sortPhotos,
        createController: createController
    };
    global.nexusGalleryDirectory = nexusGalleryDirectory;
})(typeof window !== "undefined" ? window : globalThis);
