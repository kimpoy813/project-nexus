/* Shared campus -> college -> department control for account forms.
   Latest request wins; a failed request must never silently erase saved values. */
(function () {
  'use strict';
  const config = document.getElementById('organization-fields-config');
  const campus = document.getElementById('id_campus');
  const college = document.getElementById('id_college');
  const department = document.getElementById('id_department');
  if (!config || !campus || !college || !department || campus.disabled) return;
  const form = campus.closest('form');
  const feedback = document.createElement('div');
  feedback.className = 'mt-2 text-sm text-gray-600';
  const status = document.createElement('span');
  status.setAttribute('role', 'status');
  status.setAttribute('aria-live', 'polite');
  status.id = 'organization-fields-status';
  const retry = document.createElement('button');
  retry.type = 'button'; retry.textContent = 'Retry';
  retry.className = 'ml-2 underline font-semibold text-primary';
  retry.hidden = true;
  feedback.append(status, retry);
  department.parentElement.append(feedback);
  let generation = 0, controller, busy = false, failed = false;
  let lastRequest = { college: college.value, department: department.value, departmentOnly: false };

  function populate(select, items, saved, placeholder) {
    select.replaceChildren(new Option(placeholder, ''));
    items.forEach(item => select.add(new Option(item.label, item.value)));
    // Keep an existing legacy value only on initial load/retry, never carry it
    // into a newly selected parent scope.
    if (saved && !items.some(item => item.value === saved)) select.add(new Option(saved, saved));
    select.value = saved;
  }
  async function fetchItems(url, key, signal) {
    const response = await fetch(url, { signal, headers: { Accept: 'application/json' } });
    if (!response.ok) throw new Error('Choice request failed');
    const data = await response.json();
    if (!Array.isArray(data[key])) throw new Error('Invalid choice response');
    return data[key];
  }
  async function refresh(options = lastRequest) {
    lastRequest = options;
    const current = ++generation;
    if (controller) controller.abort();
    controller = new AbortController();
    const signal = controller.signal;
    busy = true; failed = false; retry.hidden = true;
    college.disabled = department.disabled = true;
    status.textContent = 'Loading organization choices…';
    try {
      let colleges = [], departments = [];
      const params = new URLSearchParams({ campus: campus.value });
      if (campus.value) {
        if (!options.departmentOnly) colleges = await fetchItems(config.dataset.collegesUrl + '?' + params, 'colleges', signal);
        if (current !== generation) return;
        params.set('college', options.college);
        departments = await fetchItems(config.dataset.departmentsUrl + '?' + params, 'departments', signal);
      }
      if (current !== generation) return;
      if (!options.departmentOnly) populate(college, colleges, options.college, 'Select College (Optional)');
      populate(department, departments, options.department, 'Select Department (Optional)');
      status.textContent = '';
    } catch (error) {
      if (current !== generation || error.name === 'AbortError') return;
      failed = true; retry.hidden = false;
      status.textContent = 'Unable to load organization choices. Check your connection and retry before saving.';
    } finally {
      if (current === generation) {
        busy = false;
        college.disabled = department.disabled = false;
      }
    }
  }
  campus.addEventListener('change', () => {
    populate(college, [], '', 'Select College (Optional)');
    populate(department, [], '', 'Select Department (Optional)');
    refresh({ college: '', department: '', departmentOnly: false });
  });
  college.addEventListener('change', () => {
    populate(department, [], '', 'Select Department (Optional)');
    refresh({ college: college.value, department: '', departmentOnly: true });
  });
  retry.addEventListener('click', () => refresh());
  form.addEventListener('submit', event => {
    if (!busy && !failed) return;
    event.preventDefault();
    if (window.NexusSkeleton) window.NexusSkeleton.hide();
    if (window.nexusToast) window.nexusToast(busy ? 'Please wait for organization choices to finish loading.' : 'Please retry loading organization choices before saving.', 'warning');
    if (failed) retry.focus();
  });
  refresh();
})();
