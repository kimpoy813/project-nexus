/* NExUS select enhancement
   ────────────────────────────────────────────────────────────────────────────
   1. Application shell (.nexus-shell):
      Upgrades single-value <select> controls with a live-synchronized custom
      popover ([data-nx-select-popover]) while keeping the real <select> in its
      original parent for form submission, HTML5 validation, label forwarding,
      inline onchange handlers, repeater cloning, and AJAX option cascades.
      While open, the listbox portals to document.body with fixed viewport
      positioning so overflow-hidden cards and tables never clip the menu.

   2. Standalone surfaces outside .nexus-shell (e.g. Django's own admin):
      Uses progressive customizable base-select (<button class="nx-select__button">
      <selectedcontent>) where supported, leaving unsupported engines native.
   ──────────────────────────────────────────────────────────────────────────── */
(function (window, document) {
    "use strict";

    var SVG_NS = "http://www.w3.org/2000/svg";
    var SELECTOR = "select:not([multiple]):not([size]):not(.nx-select-native):not(.legacy-select-native):not([data-native-select]):not([data-native-select] *):not(.ck-editor *):not(.flatpickr-monthDropdown-months)";
    var LAYOUT_TOKEN_RE = /^(?:(?:sm|md|lg|xl|2xl):)?(?:w-\S+|min-w-\S+|max-w-\S+|flex-\S+|shrink(?:-0)?|grow(?:-0)?|self-\S+|col-span-\S+|mt-\S+|mb-\S+|my-\S+|ml-\S+|mr-\S+|mx-\S+)$/;
    var FULL_WIDTH_CLASS_RE = /\b(?:w-full|nx-input|adm-input|dir-input|pc-input|ht-input|ps-input)\b/;
    var EXPLICIT_WIDTH_CLASS_RE = /(?:^|\s)(?:(?:sm|md|lg|xl|2xl):)?w-\S+/;
    var COMPACT_CLASS_RE = /\b(?:pc-input|ht-input|ps-input|py-1\.5|py-1|h-9|h-8|text-xs)\b/;

    var popoverMap = new Map();
    var triggerToEntry = new Map();
    var menuToEntry = new Map();
    var uidCounter = 0;
    var globalBound = false;
    var rafId = 0;

    function createSvgEl(tag) {
        return typeof document.createElementNS === "function"
            ? document.createElementNS(SVG_NS, tag)
            : document.createElement(tag);
    }

    function createChevronIcon() {
        var svg = createSvgEl("svg");
        svg.setAttribute("viewBox", "0 0 20 20");
        svg.setAttribute("fill", "currentColor");
        svg.setAttribute("aria-hidden", "true");
        svg.setAttribute("class", "nx-select-popover__chevron");
        svg.setAttribute("data-nx-select-chevron", "");
        var path = createSvgEl("path");
        path.setAttribute("fill-rule", "evenodd");
        path.setAttribute("clip-rule", "evenodd");
        path.setAttribute(
            "d",
            "M5.23 7.21a.75.75 0 011.06.02L10 11.168l3.71-3.938a.75.75 0 111.08 1.04l-4.25 4.5a.75.75 0 01-1.08 0l-4.25-4.5a.75.75 0 01.02-1.06z"
        );
        svg.appendChild(path);
        return svg;
    }

    function createCheckIcon() {
        var svg = createSvgEl("svg");
        svg.setAttribute("viewBox", "0 0 20 20");
        svg.setAttribute("fill", "currentColor");
        svg.setAttribute("aria-hidden", "true");
        svg.setAttribute("class", "nx-select-popover__check");
        svg.setAttribute("data-nx-select-check", "");
        var path = createSvgEl("path");
        path.setAttribute("fill-rule", "evenodd");
        path.setAttribute("clip-rule", "evenodd");
        path.setAttribute(
            "d",
            "M16.704 4.153a.75.75 0 01.143 1.052l-8 10.5a.75.75 0 01-1.127.075l-4.5-4.5a.75.75 0 011.06-1.06l3.894 3.893 7.48-9.817a.75.75 0 011.05-.143z"
        );
        svg.appendChild(path);
        return svg;
    }

    function hasToken(className, token) {
        return (" " + (className || "") + " ").indexOf(" " + token + " ") !== -1;
    }

    function isShellPresent() {
        if (!document.body) return false;
        if (hasToken(document.body.className, "nexus-shell")) return true;
        if (typeof document.querySelector === "function") {
            return Boolean(document.querySelector(".nexus-shell"));
        }
        return false;
    }

    function isInNexusShell(node) {
        if (!node) return false;
        if (typeof node.closest === "function") {
            return Boolean(node.closest(".nexus-shell"));
        }
        var cur = node;
        while (cur) {
            if (hasToken(cur.className, "nexus-shell")) return true;
            cur = cur.parentNode;
        }
        return false;
    }

    function isInsideInertTemplate(node) {
        if (!node) return false;
        if (typeof node.closest === "function" && node.closest("template")) {
            return true;
        }
        var cur = node.parentNode;
        while (cur) {
            if (cur.tagName && String(cur.tagName).toLowerCase() === "template") return true;
            cur = cur.parentNode;
        }
        return false;
    }

    function supported() {
        return !!(window.CSS && typeof window.CSS.supports === "function" &&
            window.CSS.supports("appearance", "base-select"));
    }

    function makeEvent(name) {
        if (typeof window.Event === "function") {
            return new window.Event(name, { bubbles: true });
        }
        if (typeof Event === "function") {
            return new Event(name, { bubbles: true });
        }
        return { type: name, bubbles: true };
    }

    function readSelectItems(select) {
        var items = [];
        var options = [];

        function pushOption(opt) {
            var val = opt.value !== undefined && opt.value !== null
                ? String(opt.value)
                : (typeof opt.getAttribute === "function" ? opt.getAttribute("value") || "" : "");
            var text = (opt.textContent !== undefined && opt.textContent !== null
                ? String(opt.textContent)
                : (opt.label || "")).trim();
            var isDisabled = Boolean(
                opt.disabled || (typeof opt.hasAttribute === "function" && opt.hasAttribute("disabled"))
            );
            var item = {
                type: "option",
                node: opt,
                value: val,
                label: text,
                disabled: isDisabled,
                selected: Boolean(opt.selected)
            };
            items.push(item);
            options.push(item);
        }

        var children = select.children ? Array.from(select.children) : [];
        if (children.length > 0) {
            children.forEach(function (child) {
                var tag = child.tagName ? String(child.tagName).toLowerCase() : "";
                if (tag === "option") {
                    pushOption(child);
                } else if (tag === "optgroup") {
                    var groupLabel = (typeof child.getAttribute === "function" && child.getAttribute("label")) || child.label || "";
                    if (groupLabel) {
                        items.push({ type: "group", label: String(groupLabel) });
                    }
                    var groupKids = child.children ? Array.from(child.children) : [];
                    groupKids.forEach(function (sub) {
                        if (sub.tagName && String(sub.tagName).toLowerCase() === "option") {
                            pushOption(sub);
                        }
                    });
                }
            });
        } else if (select.options && select.options.length) {
            Array.from(select.options).forEach(pushOption);
        }

        return { items: items, options: options };
    }

    function resolveActiveOption(select, options) {
        if (!options.length) return null;
        var rawVal = select.value !== undefined && select.value !== null ? String(select.value) : null;
        if (rawVal !== null) {
            var byVal = options.find(function (opt) { return opt.value === rawVal; });
            if (byVal) return byVal;
        }
        if (typeof select.selectedIndex === "number" && select.selectedIndex >= 0 && options[select.selectedIndex]) {
            return options[select.selectedIndex];
        }
        var bySelectedFlag = options.find(function (opt) { return opt.selected; });
        return bySelectedFlag || options[0];
    }

    function applySizingClasses(select, popover) {
        var cls = String(select.className || "");
        var tokens = cls.split(/\s+/).filter(Boolean);
        var layoutClasses = ["nx-select-popover"];

        tokens.forEach(function (tok) {
            if (tok === "nx-select-native" || tok === "hidden") return;
            if (LAYOUT_TOKEN_RE.test(tok)) {
                layoutClasses.push(tok);
            }
        });

        var inlineStyle = typeof select.getAttribute === "function" ? (select.getAttribute("style") || "") : "";
        var isCompactRoleSelect = hasToken(cls, "adm-input--sm");
        var wantsAutoWidth = /width\s*:\s*auto/i.test(inlineStyle) ||
            (isCompactRoleSelect && !EXPLICIT_WIDTH_CLASS_RE.test(cls)) ||
            (!FULL_WIDTH_CLASS_RE.test(cls) && !EXPLICIT_WIDTH_CLASS_RE.test(cls));

        if (wantsAutoWidth) {
            layoutClasses.push("nx-select-popover--auto");
        }
        if (isCompactRoleSelect) {
            layoutClasses.push("nx-select-popover--sm");
        } else if (COMPACT_CLASS_RE.test(cls) || (hasToken(cls, "dir-input") && /width\s*:\s*auto/i.test(inlineStyle))) {
            layoutClasses.push("nx-select-popover--compact");
        }

        popover.className = layoutClasses.join(" ");

        if (inlineStyle && popover.style) {
            var explicitW = inlineStyle.match(/(?:^|;)\s*width\s*:\s*([^;]+)/i);
            var maxW = inlineStyle.match(/max-width\s*:\s*([^;]+)/i);
            var minW = inlineStyle.match(/min-width\s*:\s*([^;]+)/i);
            if (explicitW && explicitW[1] && !/^auto$/i.test(explicitW[1].trim())) {
                popover.style.width = explicitW[1].trim();
            }
            if (maxW && maxW[1]) popover.style.maxWidth = maxW[1].trim();
            if (minW && minW[1]) popover.style.minWidth = minW[1].trim();
        }

        var isHidden = Boolean(
            select.hidden ||
            (typeof select.hasAttribute === "function" && select.hasAttribute("hidden")) ||
            hasToken(cls, "hidden")
        );
        popover.hidden = isHidden;
        if (typeof popover.setAttribute === "function" && typeof popover.removeAttribute === "function") {
            if (isHidden) popover.setAttribute("hidden", "");
            else popover.removeAttribute("hidden");
        }
    }

    function wireAccessibleLabel(select, trigger, uid) {
        if (typeof select.getAttribute !== "function" || typeof trigger.setAttribute !== "function") return;
        var ariaLabel = select.getAttribute("aria-label");
        var ariaLabelledBy = select.getAttribute("aria-labelledby");
        var ariaDescribedBy = select.getAttribute("aria-describedby");

        if (ariaLabel) trigger.setAttribute("aria-label", ariaLabel);
        if (ariaDescribedBy) trigger.setAttribute("aria-describedby", ariaDescribedBy);
        if (ariaLabelledBy) {
            trigger.setAttribute("aria-labelledby", ariaLabelledBy);
            return;
        }

        var labelEl = null;
        if (select.id && typeof document.querySelector === "function") {
            try {
                labelEl = document.querySelector('label[for="' + select.id.replace(/"/g, '\\"') + '"]');
            } catch (_err) {
                labelEl = null;
            }
        }
        if (!labelEl && select.parentNode && select.parentNode.children) {
            var siblings = Array.from(select.parentNode.children);
            labelEl = siblings.find(function (el) {
                return el.tagName && String(el.tagName).toLowerCase() === "label" &&
                    !(typeof el.getAttribute === "function" && el.getAttribute("for"));
            }) || null;
        }
        if (labelEl) {
            if (!labelEl.id) {
                labelEl.id = uid + "-label";
            }
            trigger.setAttribute("aria-labelledby", labelEl.id);
        }
    }

    function isPopoverOpen(entry) {
        return Boolean(entry && entry.menu && !entry.menu.hidden);
    }

    function getFixedTopInset() {
        if (typeof document.querySelector !== "function") return 0;
        var nav = document.querySelector(".nexus-navbar");
        if (!nav || typeof nav.getBoundingClientRect !== "function") return 0;
        var navRect = nav.getBoundingClientRect();
        if (navRect && navRect.bottom > 0 && navRect.top <= 4) {
            return Math.round(navRect.bottom);
        }
        return 0;
    }

    function positionPortaledMenu(entry) {
        if (!entry || !isPopoverOpen(entry)) return;
        if (!entry.select.isConnected || !entry.trigger.isConnected) {
            closePopover(entry);
            return;
        }
        if (typeof entry.trigger.getBoundingClientRect !== "function") return;
        var rect = entry.trigger.getBoundingClientRect();
        var viewportH = window.innerHeight || 0;
        var viewportW = window.innerWidth || 0;
        if (!rect || rect.width <= 0 || viewportH <= 0 || viewportW <= 0) return;

        var topInset = getFixedTopInset();
        if (rect.bottom <= topInset || rect.top >= viewportH) {
            closePopover(entry);
            return;
        }

        var optionCount = entry.optionButtons ? entry.optionButtons.length : 0;
        var estHeight = Math.min(288, Math.max(80, optionCount * 38 + 12));
        var spaceBelow = viewportH - rect.bottom - 12;
        var spaceAbove = Math.max(0, rect.top - topInset - 12);
        var flipUp = spaceBelow < Math.min(estHeight, 200) && spaceAbove > spaceBelow;

        var menuMinW = Math.round(rect.width);
        var menuMaxW = Math.max(menuMinW, Math.min(360, viewportW - 24));
        var left = Math.max(12, Math.min(Math.round(rect.left), viewportW - menuMinW - 12));

        entry.menu.style.minWidth = menuMinW + "px";
        entry.menu.style.maxWidth = menuMaxW + "px";
        entry.menu.style.left = left + "px";

        if (flipUp) {
            entry.menu.classList.add("is-flipped");
            entry.menu.style.top = "auto";
            entry.menu.style.bottom = Math.round(viewportH - rect.top + 6) + "px";
            entry.menu.style.maxHeight = Math.min(288, Math.max(120, Math.floor(spaceAbove))) + "px";
        } else {
            entry.menu.classList.remove("is-flipped");
            entry.menu.style.bottom = "auto";
            entry.menu.style.top = Math.round(rect.bottom + 6) + "px";
            entry.menu.style.maxHeight = Math.min(288, Math.max(120, Math.floor(spaceBelow))) + "px";
        }
    }

    function closePopover(entry, opts) {
        if (!entry || !entry.menu) return;
        var wasOpen = !entry.menu.hidden;
        entry.menu.hidden = true;
        if (typeof entry.menu.setAttribute === "function") {
            entry.menu.setAttribute("hidden", "");
        }
        entry.menu.classList.remove("is-portaled", "is-flipped");
        if (entry.menu.style) {
            entry.menu.style.top = "";
            entry.menu.style.bottom = "";
            entry.menu.style.left = "";
            entry.menu.style.minWidth = "";
            entry.menu.style.maxWidth = "";
            entry.menu.style.maxHeight = "";
        }
        if (entry.menu.parentNode !== entry.popover) {
            if (entry.popover.isConnected) {
                entry.popover.appendChild(entry.menu);
            } else if (entry.menu.parentNode && typeof entry.menu.parentNode.removeChild === "function") {
                entry.menu.parentNode.removeChild(entry.menu);
            }
        }
        entry.popover.classList.remove("is-open");
        entry.trigger.setAttribute("aria-expanded", "false");
        if (wasOpen && opts && opts.restoreFocus && typeof entry.trigger.focus === "function") {
            entry.trigger.focus();
        }
    }

    function closeAllPopovers(exceptEntry) {
        popoverMap.forEach(function (entry) {
            if (entry !== exceptEntry && isPopoverOpen(entry)) {
                closePopover(entry);
            }
        });
    }

    function syncPopover(entry) {
        if (!entry || !entry.select) return;
        var select = entry.select;
        var parsed = readSelectItems(select);
        var active = resolveActiveOption(select, parsed.options);

        var labelText = active ? active.label : "";
        var isPlaceholder = !active || (
            active.value === "" &&
            (active.disabled || /^(?:[-—\s]*select\b|[-—]+$)/i.test(labelText))
        );
        entry.label.textContent = labelText;
        entry.label.classList.toggle("is-placeholder", isPlaceholder);

        var isDisabled = Boolean(
            select.disabled || (typeof select.hasAttribute === "function" && select.hasAttribute("disabled"))
        );
        entry.trigger.disabled = isDisabled;
        if (typeof entry.trigger.setAttribute === "function" && typeof entry.trigger.removeAttribute === "function") {
            if (isDisabled) entry.trigger.setAttribute("disabled", "");
            else entry.trigger.removeAttribute("disabled");
        }
        if (isDisabled && isPopoverOpen(entry)) {
            closePopover(entry);
        }

        var isInvalid = typeof select.getAttribute === "function" && select.getAttribute("aria-invalid") === "true";
        if (typeof entry.trigger.setAttribute === "function" && typeof entry.trigger.removeAttribute === "function") {
            if (isInvalid) entry.trigger.setAttribute("aria-invalid", "true");
            else entry.trigger.removeAttribute("aria-invalid");
        }

        applySizingClasses(select, entry.popover);

        while (entry.menu.firstChild) {
            entry.menu.removeChild(entry.menu.firstChild);
        }
        entry.optionButtons = [];

        parsed.items.forEach(function (item) {
            if (item.type === "group") {
                var heading = document.createElement("div");
                heading.className = "nx-select-popover__group-label";
                heading.setAttribute("role", "presentation");
                heading.textContent = item.label;
                entry.menu.appendChild(heading);
                return;
            }
            var btn = document.createElement("button");
            btn.type = "button";
            btn.className = "nx-select-popover__option";
            btn.setAttribute("role", "option");
            btn.setAttribute("data-nx-select-option", item.value);
            var isSelected = Boolean(active && item === active);
            btn.setAttribute("aria-selected", isSelected ? "true" : "false");
            if (item.disabled) {
                btn.disabled = true;
                btn.setAttribute("disabled", "");
                btn.setAttribute("aria-disabled", "true");
            }

            var textSpan = document.createElement("span");
            textSpan.className = "nx-select-popover__option-text";
            textSpan.textContent = item.label;
            btn.appendChild(textSpan);
            btn.appendChild(createCheckIcon());

            entry.menu.appendChild(btn);
            entry.optionButtons.push({ button: btn, item: item });
        });

        if (isPopoverOpen(entry) && entry.menu.classList.contains("is-portaled")) {
            positionPortaledMenu(entry);
        }
    }

    function openPopover(entry, opts) {
        if (!entry || entry.trigger.disabled) return;
        closeAllPopovers(entry);
        syncPopover(entry);

        var canPortal = false;
        if (document.body && typeof entry.trigger.getBoundingClientRect === "function") {
            var rect = entry.trigger.getBoundingClientRect();
            if (rect && rect.width > 0 && (window.innerHeight || 0) > 0) {
                canPortal = true;
            }
        }

        entry.menu.hidden = false;
        if (typeof entry.menu.removeAttribute === "function") {
            entry.menu.removeAttribute("hidden");
        }
        entry.popover.classList.add("is-open");
        entry.trigger.setAttribute("aria-expanded", "true");

        if (canPortal) {
            entry.menu.classList.add("is-portaled");
            if (entry.menu.parentNode !== document.body) {
                document.body.appendChild(entry.menu);
            }
            positionPortaledMenu(entry);
        }

        var focusTarget = null;
        for (var i = 0; i < entry.optionButtons.length; i += 1) {
            var candidate = entry.optionButtons[i];
            if (!candidate.item.disabled && candidate.button.getAttribute("aria-selected") === "true") {
                focusTarget = candidate.button;
                break;
            }
        }
        if (!focusTarget) {
            for (var j = 0; j < entry.optionButtons.length; j += 1) {
                if (!entry.optionButtons[j].item.disabled) {
                    focusTarget = entry.optionButtons[j].button;
                    break;
                }
            }
        }

        if (focusTarget && typeof focusTarget.scrollIntoView === "function") {
            focusTarget.scrollIntoView({ block: "nearest" });
        }
        if ((!opts || opts.focusOption !== false) && focusTarget && typeof focusTarget.focus === "function") {
            focusTarget.focus();
        }
    }

    function setNativeSelectValue(entry, chosenIndex, nextValue) {
        var select = entry.select;
        var parsed = readSelectItems(select);
        parsed.options.forEach(function (opt, idx) {
            if (opt.node) {
                opt.node.selected = idx === chosenIndex;
            }
        });
        entry.suppressHook = true;
        try {
            if (chosenIndex >= 0) {
                select.selectedIndex = chosenIndex;
            }
            select.value = nextValue;
        } finally {
            entry.suppressHook = false;
        }
    }

    function selectPopoverOption(entry, optionBtn, opts) {
        if (!entry || !optionBtn || optionBtn.disabled) return;
        var matchIdx = -1;
        for (var i = 0; i < entry.optionButtons.length; i += 1) {
            if (entry.optionButtons[i].button === optionBtn) {
                matchIdx = i;
                break;
            }
        }
        var nextValue = matchIdx >= 0
            ? entry.optionButtons[matchIdx].item.value
            : (optionBtn.getAttribute("data-nx-select-option") || "");
        var prevValue = entry.select.value !== undefined && entry.select.value !== null
            ? String(entry.select.value)
            : "";
        var prevIndex = typeof entry.select.selectedIndex === "number" ? entry.select.selectedIndex : -1;

        if (typeof entry.select.removeAttribute === "function") {
            entry.select.removeAttribute("aria-invalid");
        }
        if (typeof entry.trigger.removeAttribute === "function") {
            entry.trigger.removeAttribute("aria-invalid");
        }

        setNativeSelectValue(entry, matchIdx, nextValue);
        syncPopover(entry);
        closePopover(entry, { restoreFocus: Boolean(opts && opts.restoreFocus) });

        if (prevValue !== nextValue || (matchIdx >= 0 && prevIndex !== matchIdx)) {
            if (typeof entry.select.dispatchEvent === "function") {
                entry.select.dispatchEvent(makeEvent("input"));
                entry.select.dispatchEvent(makeEvent("change"));
            }
        }
    }

    function hookSelectProperties(entry) {
        var proto = window.HTMLSelectElement && window.HTMLSelectElement.prototype;
        if (!proto) return;
        ["value", "selectedIndex"].forEach(function (prop) {
            var desc = Object.getOwnPropertyDescriptor(proto, prop);
            if (!desc || typeof desc.get !== "function" || typeof desc.set !== "function") return;
            if (Object.prototype.hasOwnProperty.call(entry.select, prop)) return;
            Object.defineProperty(entry.select, prop, {
                configurable: true,
                enumerable: desc.enumerable,
                get: function () {
                    return desc.get.call(this);
                },
                set: function (val) {
                    desc.set.call(this, val);
                    if (!entry.suppressHook) {
                        syncPopover(entry);
                    }
                }
            });
        });
    }

    function destroyPopover(select) {
        var entry = popoverMap.get(select);
        if (!entry) return;
        closePopover(entry);
        if (entry.selectObserver && typeof entry.selectObserver.disconnect === "function") {
            entry.selectObserver.disconnect();
        }
        if (entry.menu && entry.menu.parentNode && typeof entry.menu.parentNode.removeChild === "function") {
            entry.menu.parentNode.removeChild(entry.menu);
        }
        if (entry.popover && entry.popover.parentNode && typeof entry.popover.parentNode.removeChild === "function") {
            entry.popover.parentNode.removeChild(entry.popover);
        }
        triggerToEntry.delete(entry.trigger);
        menuToEntry.delete(entry.menu);
        popoverMap.delete(select);
    }

    function bindGlobalPopoverListeners() {
        if (globalBound || typeof document.addEventListener !== "function") return;
        globalBound = true;

        document.addEventListener("click", function (event) {
            var target = event && event.target;
            if (!target || typeof target.closest !== "function") return;

            var trigger = target.closest("[data-nx-select-trigger]");
            if (trigger && triggerToEntry.has(trigger)) {
                var trigEntry = triggerToEntry.get(trigger);
                if (isPopoverOpen(trigEntry)) {
                    closePopover(trigEntry);
                } else {
                    openPopover(trigEntry);
                }
                return;
            }

            var optionBtn = target.closest("[data-nx-select-option]");
            if (optionBtn) {
                var menu = optionBtn.closest("[data-nx-select-menu]");
                var optEntry = menu ? menuToEntry.get(menu) : null;
                if (optEntry) {
                    selectPopoverOption(optEntry, optionBtn, { restoreFocus: false });
                }
                return;
            }

            var label = target.closest("label");
            if (label) {
                var forId = typeof label.getAttribute === "function" ? label.getAttribute("for") : "";
                var labeledSelect = null;
                if (forId && typeof document.getElementById === "function") {
                    labeledSelect = document.getElementById(forId);
                } else if (!forId && label.parentNode && typeof label.parentNode.querySelector === "function") {
                    labeledSelect = label.parentNode.querySelector("select.nx-select-native");
                }
                if (labeledSelect && popoverMap.has(labeledSelect)) {
                    var lblEntry = popoverMap.get(labeledSelect);
                    if (event.preventDefault) event.preventDefault();
                    if (!lblEntry.trigger.disabled) {
                        if (typeof lblEntry.trigger.focus === "function") {
                            lblEntry.trigger.focus();
                        }
                        if (isPopoverOpen(lblEntry)) {
                            closePopover(lblEntry);
                        } else {
                            openPopover(lblEntry);
                        }
                    }
                    return;
                }
            }

            popoverMap.forEach(function (entry) {
                if (!isPopoverOpen(entry)) return;
                var inPopover = typeof entry.popover.contains === "function" && entry.popover.contains(target);
                var inMenu = typeof entry.menu.contains === "function" && entry.menu.contains(target);
                if (!inPopover && !inMenu) {
                    closePopover(entry);
                }
            });
        });

        document.addEventListener("keydown", function (event) {
            var target = event && event.target;
            var activeEntry = null;
            popoverMap.forEach(function (entry) {
                if (!activeEntry && isPopoverOpen(entry)) {
                    activeEntry = entry;
                }
            });

            if (!activeEntry) {
                var closedTrigger = target && typeof target.closest === "function"
                    ? target.closest("[data-nx-select-trigger]")
                    : null;
                if (closedTrigger && triggerToEntry.has(closedTrigger)) {
                    if (event.key === "ArrowDown" || event.key === "ArrowUp" || event.key === "Enter" || event.key === " ") {
                        if (event.preventDefault) event.preventDefault();
                        openPopover(triggerToEntry.get(closedTrigger));
                    }
                }
                return;
            }

            if (event.key === "Escape") {
                if (event.preventDefault) event.preventDefault();
                if (event.stopPropagation) event.stopPropagation();
                closePopover(activeEntry, { restoreFocus: true });
                return;
            }

            if (event.key === "Tab") {
                closePopover(activeEntry, { restoreFocus: false });
                return;
            }

            var enabledButtons = activeEntry.optionButtons
                .filter(function (o) { return !o.item.disabled; })
                .map(function (o) { return o.button; });
            if (!enabledButtons.length) return;

            var currentBtn = target && typeof target.closest === "function"
                ? target.closest("[data-nx-select-option]")
                : null;
            var idx = currentBtn ? enabledButtons.indexOf(currentBtn) : -1;

            if (event.key === "ArrowDown") {
                if (event.preventDefault) event.preventDefault();
                var nextIdx = idx < 0 ? 0 : (idx + 1) % enabledButtons.length;
                enabledButtons[nextIdx].focus();
            } else if (event.key === "ArrowUp") {
                if (event.preventDefault) event.preventDefault();
                var prevIdx = idx <= 0 ? enabledButtons.length - 1 : idx - 1;
                enabledButtons[prevIdx].focus();
            } else if (event.key === "Home") {
                if (event.preventDefault) event.preventDefault();
                enabledButtons[0].focus();
            } else if (event.key === "End") {
                if (event.preventDefault) event.preventDefault();
                enabledButtons[enabledButtons.length - 1].focus();
            } else if ((event.key === "Enter" || event.key === " ") && currentBtn) {
                if (event.preventDefault) event.preventDefault();
                selectPopoverOption(activeEntry, currentBtn, { restoreFocus: true });
            }
        });

        document.addEventListener("reset", function (event) {
            var form = event && event.target;
            if (!form) return;
            var reschedule = typeof window.setTimeout === "function" ? window.setTimeout : setTimeout;
            reschedule(function () {
                popoverMap.forEach(function (entry) {
                    if (!form.contains || form.contains(entry.select)) {
                        syncPopover(entry);
                    }
                });
            }, 0);
        });

        function scheduleReposition(event) {
            var openEntry = null;
            popoverMap.forEach(function (entry) {
                if (!openEntry && isPopoverOpen(entry) && entry.menu.classList.contains("is-portaled")) {
                    openEntry = entry;
                }
            });
            if (!openEntry) return;
            if (event && event.target && openEntry.menu === event.target) return;
            if (event && event.target && typeof openEntry.menu.contains === "function" && openEntry.menu.contains(event.target)) {
                return;
            }
            if (typeof window.requestAnimationFrame === "function") {
                if (rafId) return;
                rafId = window.requestAnimationFrame(function () {
                    rafId = 0;
                    positionPortaledMenu(openEntry);
                });
            } else {
                positionPortaledMenu(openEntry);
            }
        }

        if (typeof window.addEventListener === "function") {
            window.addEventListener("resize", scheduleReposition);
            window.addEventListener("scroll", scheduleReposition, true);
        }
    }

    function enhanceShellPopover(select) {
        if (!select || !select.isConnected || !select.parentNode) return;
        if (popoverMap.has(select) || isInsideInertTemplate(select)) return;

        bindGlobalPopoverListeners();

        uidCounter += 1;
        var uid = "nx-sel-" + uidCounter;
        var menuId = (select.id ? select.id : uid) + "-listbox";

        select.className = (select.className ? select.className + " " : "") + "nx-select-native";
        if (typeof select.setAttribute === "function") {
            select.setAttribute("data-nx-select-enhanced", "popover");
            select.setAttribute("tabindex", "-1");
        }

        var popover = document.createElement("div");
        popover.setAttribute("data-nx-select-popover", "");

        var trigger = document.createElement("button");
        trigger.type = "button";
        trigger.className = "nx-select-popover__trigger";
        trigger.setAttribute("data-nx-select-trigger", "");
        trigger.setAttribute("aria-haspopup", "listbox");
        trigger.setAttribute("aria-expanded", "false");
        trigger.setAttribute("aria-controls", menuId);
        wireAccessibleLabel(select, trigger, uid);

        var labelSpan = document.createElement("span");
        labelSpan.className = "nx-select-popover__label";
        labelSpan.setAttribute("data-nx-select-label", "");

        trigger.appendChild(labelSpan);
        trigger.appendChild(createChevronIcon());

        var menu = document.createElement("div");
        menu.id = menuId;
        menu.className = "nx-select-popover__menu";
        menu.setAttribute("data-nx-select-menu", "");
        menu.setAttribute("role", "listbox");
        menu.setAttribute("tabindex", "-1");
        menu.hidden = true;
        menu.setAttribute("hidden", "");

        popover.appendChild(trigger);
        popover.appendChild(menu);

        select.parentNode.insertBefore(popover, select.nextSibling || null);

        var entry = {
            select: select,
            popover: popover,
            trigger: trigger,
            label: labelSpan,
            menu: menu,
            optionButtons: [],
            selectObserver: null,
            suppressHook: false
        };

        popoverMap.set(select, entry);
        triggerToEntry.set(trigger, entry);
        menuToEntry.set(menu, entry);

        hookSelectProperties(entry);

        if (typeof select.addEventListener === "function") {
            select.addEventListener("change", function () {
                syncPopover(entry);
            });
            select.addEventListener("focus", function () {
                if (!entry.trigger.disabled && typeof entry.trigger.focus === "function") {
                    entry.trigger.focus();
                }
            });
            select.addEventListener("invalid", function () {
                if (typeof entry.trigger.setAttribute === "function") {
                    entry.trigger.setAttribute("aria-invalid", "true");
                }
            });
        }

        if (typeof window.MutationObserver === "function") {
            var selectObserver = new window.MutationObserver(function () {
                if (!select.isConnected) {
                    destroyPopover(select);
                    return;
                }
                syncPopover(entry);
            });
            selectObserver.observe(select, {
                childList: true,
                subtree: true,
                attributes: true,
                attributeFilter: ["disabled", "hidden", "aria-invalid", "class"]
            });
            entry.selectObserver = selectObserver;
        }

        syncPopover(entry);
    }

    function enhanceBaseSelect(select) {
        if (!supported() || !select || !select.isConnected) return;
        if (isInsideInertTemplate(select)) return;
        if (select.querySelector(":scope > button")) return;

        var priorIndex = typeof select.selectedIndex === "number" ? select.selectedIndex : -1;
        var button = document.createElement("button");
        button.type = "button";
        button.className = "nx-select__button";
        button.appendChild(document.createElement("selectedcontent"));
        select.insertBefore(button, select.firstChild);
        if (priorIndex >= 0 && select.selectedIndex !== priorIndex) {
            select.selectedIndex = priorIndex;
        }
    }

    function enhance(root) {
        if (!root) return;

        var selects = [];
        if (root.nodeType === 1 && typeof root.matches === "function" && root.matches(SELECTOR)) {
            selects.push(root);
        }
        if (typeof root.querySelectorAll === "function") {
            Array.prototype.push.apply(selects, Array.from(root.querySelectorAll(SELECTOR)));
        }

        selects.forEach(function (select) {
            if (!select.isConnected) return;
            if (isInNexusShell(select)) {
                enhanceShellPopover(select);
            } else {
                enhanceBaseSelect(select);
            }
        });
    }

    function cleanupDisconnectedPopovers() {
        if (!popoverMap.size) return;
        Array.from(popoverMap.keys()).forEach(function (select) {
            if (!select.isConnected) {
                destroyPopover(select);
            }
        });
    }

    function init() {
        if (!document.body) return;
        var shellActive = isShellPresent();
        if (!shellActive && !supported()) return;

        enhance(document);

        if (typeof window.MutationObserver !== "function") return;
        var observer = new window.MutationObserver(function (records) {
            var sawRemovals = false;
            records.forEach(function (record) {
                if (record.target && record.target.nodeType === 1 &&
                    typeof record.target.matches === "function" && record.target.matches(SELECTOR)) {
                    enhance(record.target);
                }
                if (record.addedNodes) {
                    Array.from(record.addedNodes).forEach(function (node) {
                        if (node.nodeType === 1) enhance(node);
                    });
                }
                if (record.removedNodes && record.removedNodes.length) {
                    sawRemovals = true;
                }
            });
            if (sawRemovals) {
                cleanupDisconnectedPopovers();
            }
        });
        observer.observe(document.body, { childList: true, subtree: true });
    }

    if (document.body) {
        init();
    } else {
        document.addEventListener("DOMContentLoaded", init, { once: true });
    }
})(window, document);
