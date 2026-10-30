/**
 * Alpine controller for the public Program Gallery (/gallery/).
 *
 * Powers:
 *  - 5 live Summary KPI cards (#gallery-summary)
 *  - 3 interactive Visual Overview charts (#gallery-overview: Photos per year,
 *    Photos by campus, By documentation source)
 *  - Filter & Sort controls (#gallery-filters: quoted-phrase Search, Campus,
 *    Year, Source, Sort order, and Reset)
 *  - Live photo grid filtering and non-destructive CSS order sorting (#gallery-photos)
 *    even when zero photos are published yet.
 */
(function (global) {
    "use strict";

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
            campus: "",
            year: "",
            source: "",
            sortBy: "newest",

            total: allPhotos.length,
            shown: baseStats.photo_count || 0,
            shownActivities: baseStats.activity_count || 0,
            shownCampuses: baseStats.campus_count || 0,
            shownTerminal: baseStats.terminal_report_count || 0,
            shownLegacy: baseStats.legacy_count || 0,
            chartDenom: baseStats.photo_count || 0,

            yearsMap: buildMap(baseOverview.years, "value"),
            campusesMap: buildMap(baseOverview.campuses, "key"),
            sourcesMap: buildMap(baseOverview.sources, "value"),
            filteredKeys: allPhotos.map(function (p) { return p.key; }),

            hasActiveFilters: function () {
                return Boolean(
                    this.q.trim() ||
                    this.campus ||
                    this.year ||
                    this.source
                );
            },

            activeFilterCount: function () {
                var total = 0;
                if (this.q.trim()) total += 1;
                if (this.campus) total += 1;
                if (this.year) total += 1;
                if (this.source) total += 1;
                return total;
            },

            toggleCampus: function (key) {
                var clean = String(key || "");
                this.campus = this.campus === clean ? "" : clean;
                this.apply();
            },

            toggleYear: function (yr) {
                var clean = String(yr || "");
                this.year = this.year === clean ? "" : clean;
                this.apply();
            },

            toggleSource: function (src) {
                var clean = String(src || "");
                this.source = this.source === clean ? "" : clean;
                this.apply();
            },

            reset: function () {
                this.q = "";
                this.campus = "";
                this.year = "";
                this.source = "";
                this.sortBy = "newest";
                this.apply();
            },

            matchesPhoto: function (photo, parsedSearch, ignoreField) {
                if (ignoreField !== "q" && !matchesSearchQuery(photo._haystack, parsedSearch)) {
                    return false;
                }
                if (ignoreField !== "campus" && this.campus && photo.campus_key !== this.campus) {
                    return false;
                }
                if (ignoreField !== "year" && this.year && String(photo.year || "") !== this.year) {
                    return false;
                }
                if (ignoreField !== "source" && this.source && photo.source !== this.source) {
                    return false;
                }
                return true;
            },

            apply: function () {
                var self = this;
                var parsedSearch = parseSearchQuery(this.q);

                var matched = allPhotos.filter(function (photo) {
                    return self.matchesPhoto(photo, parsedSearch, null);
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
                (baseOverview.years || []).forEach(function (yr) {
                    var c = yearCounts[String(yr.value)] || 0;
                    if (c > maxYear) maxYear = c;
                });
                var nextYears = {};
                (baseOverview.years || []).forEach(function (yr) {
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
                (baseOverview.campuses || []).forEach(function (camp) {
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
                    baseOverview.sources,
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
                return (baseOverview.sources || []).map(function (item) {
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
