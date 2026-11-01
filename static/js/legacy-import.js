/* Progressive enhancement for the admin legacy import; no external UI dependencies. */
(() => {
  const form = document.getElementById('legacy-import-form');
  if (!form) return;
  const byId = (id) => document.getElementById(id);
  const canEnhanceSelects = typeof document.createElement === 'function'
    && typeof document.addEventListener === 'function';
  const SVG_NS = 'http://www.w3.org/2000/svg';
  const dropdownMap = new Map();

  function createSvgIcon(viewBox, pathAttrs, className) {
    const svg = typeof document.createElementNS === 'function'
      ? document.createElementNS(SVG_NS, 'svg')
      : document.createElement('svg');
    svg.setAttribute('viewBox', viewBox);
    svg.setAttribute('aria-hidden', 'true');
    if (className) svg.setAttribute('class', className);
    const path = typeof document.createElementNS === 'function'
      ? document.createElementNS(SVG_NS, 'path')
      : document.createElement('path');
    Object.entries(pathAttrs).forEach(([k, v]) => path.setAttribute(k, v));
    svg.appendChild(path);
    return svg;
  }

  function createChevronIcon() {
    const svg = createSvgIcon(
      '0 0 24 24',
      {
        d: 'M19 9l-7 7-7-7',
        fill: 'none',
        stroke: 'currentColor',
        'stroke-width': '2',
        'stroke-linecap': 'round',
        'stroke-linejoin': 'round',
      },
      'legacy-dropdown__chevron'
    );
    svg.setAttribute('data-li-dropdown-chevron', '');
    return svg;
  }

  function createCheckIcon() {
    const svg = createSvgIcon(
      '0 0 20 20',
      {
        d: 'M16.704 4.153a.75.75 0 01.143 1.052l-8 10.5a.75.75 0 01-1.127.075l-4.5-4.5a.75.75 0 011.06-1.06l3.894 3.893 7.48-9.817a.75.75 0 011.05-.143z',
        fill: 'currentColor',
        'fill-rule': 'evenodd',
        'clip-rule': 'evenodd',
      },
      'legacy-dropdown__check'
    );
    svg.setAttribute('data-li-dropdown-check', '');
    return svg;
  }

  function isDropdownOpen(entry) {
    return Boolean(entry && !entry.menu.hidden);
  }

  function updateHostElevation(entry) {
    const field = entry.wrapper.closest?.('.legacy-field');
    const stageDetail = entry.wrapper.closest?.('.legacy-stage-detail');
    const card = entry.wrapper.closest?.('.legacy-card');
    if (field) {
      const anyInField = [...dropdownMap.values()].some(
        (item) => isDropdownOpen(item) && item.wrapper.closest?.('.legacy-field') === field
      );
      field.classList?.toggle('legacy-field--open', anyInField);
    }
    if (stageDetail) {
      const anyInStage = [...dropdownMap.values()].some(
        (item) => isDropdownOpen(item) && item.wrapper.closest?.('.legacy-stage-detail') === stageDetail
      );
      stageDetail.classList?.toggle('legacy-stage-detail--open', anyInStage);
    }
    if (card) {
      const anyInCard = [...dropdownMap.values()].some(
        (item) => isDropdownOpen(item) && item.wrapper.closest?.('.legacy-card') === card
      );
      card.classList?.toggle('legacy-card--open', anyInCard);
    }
  }

  function closeLegacyDropdown(entry, { restoreFocus = false } = {}) {
    if (!entry) return;
    entry.menu.hidden = true;
    entry.trigger.setAttribute('aria-expanded', 'false');
    entry.wrapper.classList?.remove('is-open');
    updateHostElevation(entry);
    if (restoreFocus && !entry.trigger.disabled) {
      entry.trigger.focus();
    }
  }

  function closeAllLegacyDropdowns(exceptEntry = null, opts = {}) {
    dropdownMap.forEach((entry) => {
      if (entry !== exceptEntry && isDropdownOpen(entry)) {
        closeLegacyDropdown(entry, opts);
      }
    });
  }

  function openLegacyDropdown(entry, { focusSelected = false } = {}) {
    if (!entry || entry.trigger.disabled || entry.select.disabled) return;
    closeAllLegacyDropdowns(entry);

    let openUpward = false;
    if (typeof entry.trigger.getBoundingClientRect === 'function'
        && typeof window.innerHeight === 'number'
        && window.innerHeight > 0) {
      const rect = entry.trigger.getBoundingClientRect();
      const nav = typeof document.querySelector === 'function' ? document.querySelector('.nexus-navbar') : null;
      const navRect = nav && typeof nav.getBoundingClientRect === 'function' ? nav.getBoundingClientRect() : null;
      const topInset = navRect && navRect.bottom > 0 && navRect.top <= 4 ? Math.round(navRect.bottom) : 0;
      const spaceBelow = window.innerHeight - rect.bottom;
      const spaceAbove = Math.max(0, rect.top - topInset);
      const optionCount = entry.menu.querySelectorAll?.('[data-li-dropdown-option]').length || 0;
      const estimatedHeight = Math.min(280, optionCount * 38 + 16);
      openUpward = spaceBelow < estimatedHeight + 16 && spaceAbove > spaceBelow;
    }
    entry.menu.classList?.toggle('is-upward', openUpward);

    entry.menu.hidden = false;
    entry.trigger.setAttribute('aria-expanded', 'true');
    entry.wrapper.classList?.add('is-open');
    updateHostElevation(entry);

    const selectedBtn = entry.menu.querySelector?.('[data-li-dropdown-option][aria-selected="true"]')
      || entry.menu.querySelector?.('[data-li-dropdown-option]:not(:disabled)');
    if (selectedBtn) {
      selectedBtn.scrollIntoView?.({ block: 'nearest' });
      if (focusSelected) selectedBtn.focus();
    }
  }

  function syncLegacyDropdown(select) {
    const entry = dropdownMap.get(select);
    if (!entry) return;

    const options = Array.from(select.options || []);
    const selectedOpt = select.selectedOptions?.[0]
      || options.find((opt) => opt.value === select.value)
      || options[0]
      || null;

    entry.labelSpan.textContent = selectedOpt ? selectedOpt.textContent.trim() : '';
    entry.trigger.dataset.placeholder = (!selectedOpt || selectedOpt.value === '') ? 'true' : 'false';
    entry.trigger.disabled = Boolean(select.disabled);
    if (select.disabled && isDropdownOpen(entry)) {
      closeLegacyDropdown(entry);
    }

    const fieldWrap = entry.wrapper.closest?.('.legacy-field');
    const hasError = select.getAttribute?.('aria-invalid') === 'true'
      || Boolean(fieldWrap?.querySelector?.('.errorlist'));
    if (hasError) entry.trigger.setAttribute('aria-invalid', 'true');
    else entry.trigger.removeAttribute('aria-invalid');

    const optionButtons = options.map((opt) => {
      const btn = document.createElement('button');
      btn.type = 'button';
      btn.className = 'legacy-dropdown__option';
      btn.setAttribute('role', 'option');
      btn.setAttribute('data-li-dropdown-option', opt.value);
      const isSelected = opt === selectedOpt;
      btn.setAttribute('aria-selected', isSelected ? 'true' : 'false');
      if (opt.disabled) btn.disabled = true;

      const textSpan = document.createElement('span');
      textSpan.textContent = opt.textContent.trim();
      btn.appendChild(textSpan);
      btn.appendChild(createCheckIcon());
      return btn;
    });

    if (typeof entry.menu.replaceChildren === 'function') {
      entry.menu.replaceChildren(...optionButtons);
    } else {
      entry.menu.innerHTML = '';
      optionButtons.forEach((btn) => entry.menu.appendChild(btn));
    }
  }

  function selectLegacyOption(entry, optionBtn, { restoreFocus = false } = {}) {
    if (!entry || !optionBtn || optionBtn.disabled) return;
    const nextValue = optionBtn.getAttribute('data-li-dropdown-option') ?? '';
    const previousValue = entry.select.value;

    entry.select.value = nextValue;
    Array.from(entry.select.options || []).forEach((opt) => {
      opt.selected = opt.value === nextValue;
    });

    syncLegacyDropdown(entry.select);
    closeLegacyDropdown(entry, { restoreFocus });

    if (previousValue !== nextValue && typeof entry.select.dispatchEvent === 'function') {
      const EventCtor = window.Event || Event;
      entry.select.dispatchEvent(new EventCtor('input', { bubbles: true }));
      entry.select.dispatchEvent(new EventCtor('change', { bubbles: true }));
    }
  }

  function enhanceLegacySelect(select) {
    if (!select || dropdownMap.has(select) || !select.parentNode) return;

    select.querySelector?.(':scope > button.nx-select__button')?.remove?.();
    select.classList?.add('legacy-select-native');
    select.tabIndex = -1;
    select.setAttribute('aria-hidden', 'true');

    const wrapper = document.createElement('div');
    wrapper.className = 'legacy-dropdown';
    wrapper.setAttribute('data-li-dropdown', '');

    const trigger = document.createElement('button');
    trigger.type = 'button';
    trigger.className = 'legacy-dropdown__trigger';
    trigger.setAttribute('data-li-dropdown-trigger', '');
    trigger.setAttribute('aria-haspopup', 'listbox');
    trigger.setAttribute('aria-expanded', 'false');

    const labelSpan = document.createElement('span');
    labelSpan.className = 'legacy-dropdown__label';
    labelSpan.setAttribute('data-li-dropdown-label', '');
    trigger.appendChild(labelSpan);
    trigger.appendChild(createChevronIcon());

    const menu = document.createElement('div');
    menu.className = 'legacy-dropdown__menu';
    menu.setAttribute('data-li-dropdown-menu', '');
    menu.setAttribute('role', 'listbox');
    menu.hidden = true;

    const fieldLabel = select.id ? form.querySelector?.(`label[for="${select.id}"]`) : null;
    if (fieldLabel) {
      if (!fieldLabel.id) fieldLabel.id = `${select.id}_label`;
      trigger.setAttribute('aria-labelledby', fieldLabel.id);
      menu.setAttribute('aria-labelledby', fieldLabel.id);
      fieldLabel.addEventListener?.('click', (event) => {
        event.preventDefault();
        if (trigger.disabled) return;
        trigger.focus();
        const entry = dropdownMap.get(select);
        if (entry && !isDropdownOpen(entry)) openLegacyDropdown(entry);
      });
    }

    select.parentNode.insertBefore(wrapper, select);
    wrapper.appendChild(select);
    wrapper.appendChild(trigger);
    wrapper.appendChild(menu);

    const entry = { select, wrapper, trigger, labelSpan, menu };
    dropdownMap.set(select, entry);
    syncLegacyDropdown(select);
  }

  function enhanceLegacySelects() {
    if (!canEnhanceSelects) return;
    Array.from(form.querySelectorAll('select:not([multiple]):not([size])')).forEach(enhanceLegacySelect);

    document.addEventListener('click', (event) => {
      const target = event.target;
      if (!target || typeof target.closest !== 'function') return;

      const trigger = target.closest('[data-li-dropdown-trigger]');
      if (trigger && form.contains?.(trigger)) {
        const wrapper = trigger.closest('[data-li-dropdown]');
        const entry = [...dropdownMap.values()].find((item) => item.wrapper === wrapper);
        if (!entry) return;
        if (isDropdownOpen(entry)) closeLegacyDropdown(entry);
        else openLegacyDropdown(entry);
        return;
      }

      const optionBtn = target.closest('[data-li-dropdown-option]');
      if (optionBtn && form.contains?.(optionBtn)) {
        const wrapper = optionBtn.closest('[data-li-dropdown]');
        const entry = [...dropdownMap.values()].find((item) => item.wrapper === wrapper);
        selectLegacyOption(entry, optionBtn, { restoreFocus: false });
        return;
      }

      if (!target.closest('[data-li-dropdown]')) {
        closeAllLegacyDropdowns();
      }
    });

    document.addEventListener('keydown', (event) => {
      const activeEntry = [...dropdownMap.values()].find(isDropdownOpen);

      if (event.key === 'Escape' && activeEntry) {
        event.preventDefault();
        event.stopPropagation?.();
        closeLegacyDropdown(activeEntry, { restoreFocus: true });
        return;
      }

      const target = event.target;
      const trigger = target?.closest?.('[data-li-dropdown-trigger]');
      if (trigger && form.contains?.(trigger)) {
        const wrapper = trigger.closest('[data-li-dropdown]');
        const entry = [...dropdownMap.values()].find((item) => item.wrapper === wrapper);
        if (entry && !isDropdownOpen(entry)
            && ['ArrowDown', 'ArrowUp', 'Enter', ' '].includes(event.key)) {
          event.preventDefault();
          openLegacyDropdown(entry, { focusSelected: true });
          return;
        }
      }

      if (!activeEntry || !activeEntry.wrapper.contains?.(target)) return;

      if (event.key === 'Tab') {
        closeLegacyDropdown(activeEntry, { restoreFocus: false });
        return;
      }

      const options = Array.from(
        activeEntry.menu.querySelectorAll('[data-li-dropdown-option]:not(:disabled)')
      );
      if (!options.length) return;
      const currentOpt = target?.closest?.('[data-li-dropdown-option]');
      const currentIndex = options.indexOf(currentOpt);

      if (event.key === 'ArrowDown') {
        event.preventDefault();
        options[currentIndex < 0 ? 0 : (currentIndex + 1) % options.length].focus();
      } else if (event.key === 'ArrowUp') {
        event.preventDefault();
        options[currentIndex <= 0 ? options.length - 1 : currentIndex - 1].focus();
      } else if (event.key === 'Home') {
        event.preventDefault();
        options[0].focus();
      } else if (event.key === 'End') {
        event.preventDefault();
        options[options.length - 1].focus();
      } else if ((event.key === 'Enter' || event.key === ' ') && currentIndex >= 0) {
        event.preventDefault();
        selectLegacyOption(activeEntry, options[currentIndex], { restoreFocus: true });
      }
    });

    Array.from(form.querySelectorAll('details')).forEach((detailsEl) => {
      detailsEl.addEventListener?.('toggle', () => {
        if (!detailsEl.open) {
          dropdownMap.forEach((entry) => {
            if (isDropdownOpen(entry) && detailsEl.contains?.(entry.wrapper)) {
              closeLegacyDropdown(entry);
            }
          });
        }
      });
    });
  }

  function focusControl(target) {
    if (!target) return;
    const entry = dropdownMap.get(target);
    if (entry) {
      entry.trigger.focus();
      return;
    }
    target.focus();
  }

  const state = () => form.querySelector('[name="activity_state"]:checked')?.value || 'HISTORICAL';
  const accounts = [...form.querySelectorAll('[name="assigned_proponents"]')];
  const selectedAccounts = () => accounts.filter((input) => input.checked);
  const ongoing = () => ['MOA_PENDING', 'ONGOING'].includes(state());
  const text = (id, value) => { byId(id).textContent = value; };
  const optionLabel = (id) => byId(id).selectedOptions[0]?.textContent || 'Not Started';
  const showField = (id, visible) => {
    const wrapper = byId(id);
    wrapper.hidden = !visible;
    wrapper.querySelectorAll('input, select').forEach((input) => {
      input.disabled = !visible;
      syncLegacyDropdown(input);
    });
  };
  const phase = (id, label, status) => {
    text(id, label);
    byId(id).closest('li').dataset.phaseState = status;
  };

  function updateReview() {
    const current = state();
    const historical = current === 'HISTORICAL';
    const pending = current === 'MOA_PENDING';
    const implementation = current === 'ONGOING';
    const completed = current === 'COMPLETED';
    showField('historical-status-field', historical);
    showField('moa-stage-field', pending);
    showField('implementation-stage-field', implementation);
    showField('terminal-report-field', historical || completed);
    // Photo documentation is part of the terminal report (appendix E.13), so it
    // only opens once the activity is completed.
    showField('photo-documentation-field', completed);
    showField('moa-file-field', !pending || byId('id_moa_stage').value !== 'NOT_STARTED');
    text('assignment-help', ongoing() ? 'Select at least one account to continue the remaining workflow.' : 'Optional. Select the accounts that should have access to this activity.');
    text('document-guidance', historical
      ? 'Historical mode uses files to record progress: an MOA file marks MOA complete; a terminal report marks Implementation complete. Your proposal status stays as selected.'
      : pending && byId('id_moa_stage').value === 'NOT_STARTED'
        ? 'No MOA document is needed yet. You can add the approved proposal and supporting files. MOA and Implementation will remain Not Started.'
        : 'Files are optional. The stage selected above determines progress, not the attached documents. Files in hidden fields will not be imported.');

    const count = selectedAccounts().length;
    text('selected-count', `${count} selected`);
    text('review-accounts', String(count));
    if (count || !ongoing()) byId('assignment-error').hidden = true;
    text('review-title', byId('id_title').value.trim() || 'Activity title not entered');
    text('review-campus', byId('id_campus').value || 'No campus selected');
    let proposalDone = !historical || byId('id_proposal_status').value === 'COMPLETED';
    let moaDone = completed || implementation || (historical && byId('id_moa_draft_file').files.length > 0);
    let implementationDone = completed || (historical && byId('id_terminal_report_file').files.length > 0);
    phase('review-proposal', proposalDone ? 'Completed' : optionLabel('id_proposal_status'), proposalDone ? 'done' : 'active');
    phase('review-moa', moaDone ? 'Completed' : pending ? optionLabel('id_moa_stage') : 'Not Started', moaDone ? 'done' : pending && byId('id_moa_stage').value !== 'NOT_STARTED' ? 'active' : 'waiting');
    phase('review-implementation', implementationDone ? 'Completed' : implementation ? optionLabel('id_implementation_stage') : 'Not Started', implementationDone ? 'done' : implementation ? 'active' : 'waiting');
    const allDone = proposalDone && moaDone && implementationDone;
    const process = allDone ? 'Completed' : implementation || implementationDone ? 'Implementation' : pending || moaDone || proposalDone ? 'MOA' : 'Proposal';
    const overall = allDone ? 'Completed' : historical && byId('id_proposal_status').value === 'DRAFTING' && !moaDone && !implementationDone ? 'Draft' : 'In progress';
    text('review-reporting', `Director view: ${process} · ${overall}.`);
    const files = [...form.querySelectorAll('input[type="file"]:not(:disabled)')].reduce((sum, input) => sum + input.files.length, 0);
    text('review-files', String(files));
  }

  function filterAccounts() {
    const search = byId('account-search').value.trim().toLocaleLowerCase();
    const selectedOnly = byId('show-selected').getAttribute('aria-pressed') === 'true';
    let visible = 0;
    accounts.forEach((input) => {
      const row = input.closest('label');
      const show = row.textContent.toLocaleLowerCase().includes(search) && (!selectedOnly || input.checked);
      row.hidden = !show;
      if (show) visible += 1;
    });
    byId('account-empty').hidden = visible > 0 || accounts.length === 0;
  }

  byId('account-search').addEventListener('input', filterAccounts);
  byId('show-selected').addEventListener('click', () => {
    const button = byId('show-selected');
    button.setAttribute('aria-pressed', button.getAttribute('aria-pressed') === 'true' ? 'false' : 'true');
    filterAccounts();
  });
  form.addEventListener('input', updateReview);
  form.addEventListener('change', (event) => {
    if (event?.target && dropdownMap.has(event.target)) {
      syncLegacyDropdown(event.target);
    }
    updateReview();
    filterAccounts();
  });
  // Searching should never submit the form via Enter.
  byId('account-search').addEventListener('keydown', (event) => {
    if (event.key === 'Enter') event.preventDefault();
  });

  const campus = byId('id_campus');
  const college = byId('id_college');
  const department = byId('id_department');
  let controller;
  let loadingUnits = false;
  let failedUnits = false;
  let lastLoadColleges = false;
  function reset(select, label) { select.replaceChildren(new Option(label, '')); }
  async function loadUnits(loadColleges) {
    controller?.abort();
    const current = new AbortController();
    controller = current;
    lastLoadColleges = loadColleges;
    failedUnits = false;
    loadingUnits = true;
    byId('unit-retry').hidden = true;
    byId('unit-feedback').dataset.error = 'false';
    if (loadColleges) reset(college, 'Choose college');
    reset(department, 'Choose department');
    college.disabled = true;
    department.disabled = true;
    syncLegacyDropdown(college);
    syncLegacyDropdown(department);
    text('unit-feedback', campus.value ? 'Loading available units…' : 'Choose a campus to see its colleges and departments.');
    async function fetchOptions(url, key, select, params) {
      const response = await fetch(`${url}?${new URLSearchParams(params)}`, { signal: current.signal });
      if (!response.ok) throw new Error('Unable to load units');
      const data = await response.json();
      if (!Array.isArray(data[key])) throw new Error('Invalid unit response');
      if (current.signal.aborted) return;
      data[key].forEach((item) => select.add(new Option(item.label, item.value)));
    }
    try {
      if (campus.value) {
        if (loadColleges) await fetchOptions(form.dataset.collegesUrl, 'colleges', college, { campus: campus.value });
        await fetchOptions(form.dataset.departmentsUrl, 'departments', department, { campus: campus.value, college: college.value });
        if (!current.signal.aborted) text('unit-feedback', 'Units updated. Select the applicable college and department.');
      }
    } catch (error) {
      if (current.signal.aborted) return;
      failedUnits = true;
      text('unit-feedback', 'We couldn’t load the units. Retry before importing so the activity is assigned correctly.');
      byId('unit-feedback').dataset.error = 'true';
      byId('unit-retry').hidden = false;
    } finally {
      if (!current.signal.aborted) {
        loadingUnits = false;
        college.disabled = !campus.value;
        department.disabled = !campus.value;
        syncLegacyDropdown(college);
        syncLegacyDropdown(department);
      }
    }
  }
  campus.addEventListener('change', () => loadUnits(true));
  college.addEventListener('change', () => loadUnits(false));
  byId('unit-retry').addEventListener('click', () => loadUnits(lastLoadColleges));
  college.disabled = !campus.value;
  department.disabled = !campus.value;
  enhanceLegacySelects();

  // Open optional details before the browser focuses an invalid control.
  form.addEventListener('invalid', (event) => {
    const details = event.target.closest('details');
    if (details) details.open = true;
  }, true);
  let submitting = false;
  form.addEventListener('submit', (event) => {
    if (submitting) { event.preventDefault(); return; }
    if (loadingUnits || failedUnits) {
      event.preventDefault();
      focusControl(byId(failedUnits ? 'unit-retry' : 'id_campus'));
      return;
    }
    if (ongoing() && selectedAccounts().length === 0) {
      event.preventDefault();
      byId('assignment-error').hidden = false;
      byId('account-search').focus();
      return;
    }
    closeAllLegacyDropdowns();
    submitting = true;
    byId('import-submit').disabled = true;
    text('import-submit', 'Importing activity…');
    form.setAttribute('aria-busy', 'true');
  });
  window.addEventListener('pageshow', () => {
    submitting = false;
    byId('import-submit').disabled = false;
    text('import-submit', 'Import activity →');
    form.removeAttribute('aria-busy');
    dropdownMap.forEach((_, select) => syncLegacyDropdown(select));
    updateReview();
  });
  byId('legacy-errors')?.querySelectorAll('a').forEach((link) => link.addEventListener('click', (event) => {
    const target = byId(link.hash.slice(1));
    if (!target) return;
    const details = target.closest('details');
    if (details) details.open = true;
    if (!target.closest('[hidden]')) {
      event.preventDefault();
      const focusTarget = target.matches('fieldset') ? target.querySelector('input') || target : target;
      focusControl(focusTarget);
      (dropdownMap.get(focusTarget)?.trigger || focusTarget).scrollIntoView({ block: 'center' });
    }
  }));
  document.querySelector('.legacy-account-tools').hidden = false;
  byId('live-review').hidden = false;
  updateReview();
  if (byId('legacy-errors')) byId('legacy-errors').focus();
})();
