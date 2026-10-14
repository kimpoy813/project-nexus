const test = require('node:test');
const assert = require('node:assert/strict');
const { readFileSync } = require('node:fs');
const { runInNewContext } = require('node:vm');
const source = readFileSync('static/js/organization-fields.js', 'utf8');
const flush = () => new Promise(resolve => setImmediate(resolve));

class Element {
  constructor(value = '') { this.value = value; this.options = []; this.children = []; this.events = {}; this.disabled = false; }
  addEventListener(name, fn) { this.events[name] = fn; }
  setAttribute() {}
  append(...children) { this.children.push(...children); }
  replaceChildren(...options) { this.options = options; this.value = ''; }
  add(option) { this.options.push(option); }
  focus() { this.focused = true; }
}
function setup({ campusValue = 'A', collegeValue = '', departmentValue = '' } = {}) {
  const form = new Element(), campus = new Element(campusValue), college = new Element(collegeValue), department = new Element(departmentValue);
  department.parentElement = new Element(); campus.closest = () => form;
  const nodes = { id_campus: campus, id_college: college, id_department: department, 'organization-fields-config': { dataset: { collegesUrl: '/colleges/', departmentsUrl: '/departments/' } } };
  const requests = [];
  runInNewContext(source, {
    document: { getElementById: id => nodes[id], createElement: () => new Element() },
    Option: function (label, value) { this.label = label; this.value = value; },
    AbortController, URLSearchParams,
    fetch: (url, options) => new Promise((resolve, reject) => requests.push({ url, options, resolve: (data, ok = true) => resolve({ ok, json: async () => data }), reject })),
    window: { NexusSkeleton: { hide() {} } },
  });
  const [status, retry] = department.parentElement.children[0].children;
  function submit() { let prevented = false; form.events.submit({ preventDefault() { prevented = true; } }); return prevented; }
  return { campus, college, department, status, retry, requests, submit };
}

test('initial loading preserves legacy saved choices instead of wiping the form', async () => {
  const s = setup({ collegeValue: 'Saved College', departmentValue: 'Saved Department' });
  s.requests[0].resolve({ colleges: [] }); await flush();
  s.requests[1].resolve({ departments: [] }); await flush();
  assert.equal(s.college.value, 'Saved College'); assert.equal(s.department.value, 'Saved Department');
  assert.equal(s.submit(), false);
});
test('late responses for an old campus cannot overwrite the current campus options', async () => {
  const s = setup();
  s.campus.value = 'B'; s.campus.events.change();
  s.requests[1].resolve({ colleges: [{ value: 'B College', label: 'B College' }] }); await flush();
  s.requests[2].resolve({ departments: [{ value: 'B Department', label: 'B Department' }] }); await flush();
  s.requests[0].resolve({ colleges: [{ value: 'A College', label: 'A College' }] }); await flush();
  assert.equal(s.requests.length, 3, 'stale request must not start another department fetch');
  assert.ok(s.college.options.some(option => option.value === 'B College'));
  assert.ok(!s.college.options.some(option => option.value === 'A College'));
});
test('loading choices blocks incomplete form submission', () => {
  const s = setup(); assert.equal(s.college.disabled, true); assert.equal(s.submit(), true);
});
test('failure preserves saved values and exposes a retry rather than silently allowing data loss', async () => {
  const s = setup({ collegeValue: 'Saved' });
  s.requests[0].resolve({}, false); await flush();
  assert.equal(s.college.value, 'Saved'); assert.equal(s.retry.hidden, false);
  assert.match(s.status.textContent, /Unable to load/); assert.equal(s.submit(), true);
});
test('retry recovers a failed request and restores normal submission', async () => {
  const s = setup(); s.requests[0].reject(new Error('Offline')); await flush();
  s.retry.events.click();
  s.requests[1].resolve({ colleges: [] }); await flush();
  s.requests[2].resolve({ departments: [] }); await flush();
  assert.equal(s.retry.hidden, true); assert.equal(s.college.disabled, false); assert.equal(s.submit(), false);
});
test('a blank campus needs no network request', () => {
  const s = setup({ campusValue: '' }); assert.equal(s.requests.length, 0); assert.equal(s.submit(), false);
});
