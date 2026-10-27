/* Progressive enhancement for the admin legacy import; no external UI dependencies. */
(() => {
  const form = document.getElementById('legacy-import-form');
  if (!form) return;
  const byId = (id) => document.getElementById(id);
  const state = () => form.querySelector('[name="activity_state"]:checked')?.value || 'HISTORICAL';
  const accounts = [...form.querySelectorAll('[name="assigned_proponents"]')];
  const selectedAccounts = () => accounts.filter((input) => input.checked);
  const ongoing = () => ['MOA_PENDING', 'ONGOING'].includes(state());
  const text = (id, value) => { byId(id).textContent = value; };
  const optionLabel = (id) => byId(id).selectedOptions[0]?.textContent || 'Not Started';
  const showField = (id, visible) => {
    const wrapper = byId(id);
    wrapper.hidden = !visible;
    wrapper.querySelectorAll('input, select').forEach((input) => { input.disabled = !visible; });
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
  form.addEventListener('change', () => { updateReview(); filterAccounts(); });
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
      }
    }
  }
  campus.addEventListener('change', () => loadUnits(true));
  college.addEventListener('change', () => loadUnits(false));
  byId('unit-retry').addEventListener('click', () => loadUnits(lastLoadColleges));
  college.disabled = !campus.value;
  department.disabled = !campus.value;

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
      byId(failedUnits ? 'unit-retry' : 'id_campus').focus();
      return;
    }
    if (ongoing() && selectedAccounts().length === 0) {
      event.preventDefault();
      byId('assignment-error').hidden = false;
      byId('account-search').focus();
      return;
    }
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
    updateReview();
  });
  byId('legacy-errors')?.querySelectorAll('a').forEach((link) => link.addEventListener('click', (event) => {
    const target = byId(link.hash.slice(1));
    if (!target) return;
    const details = target.closest('details');
    if (details) details.open = true;
    if (!target.closest('[hidden]')) {
      event.preventDefault();
      (target.matches('fieldset') ? target.querySelector('input') || target : target).focus();
      target.scrollIntoView({ block: 'center' });
    }
  }));
  document.querySelector('.legacy-account-tools').hidden = false;
  byId('live-review').hidden = false;
  updateReview();
  if (byId('legacy-errors')) byId('legacy-errors').focus();
})();
