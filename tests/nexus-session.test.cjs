const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const source = fs.readFileSync('static/js/nexus-session.js', 'utf8');

function setup({ status = 200, reject = false } = {}) {
  let now = 0;
  const calls = [], redirects = [], events = {}, intervals = [], timeouts = [];
  const warning = { hidden: true }, countdown = {}, stay = {};
  stay.addEventListener = (_, callback) => { stay.click = callback; };
  const config = { activityKey: 'activity', timeoutMs: 120000, warningMs: 24000, heartbeatUrl: '/session/activity/', logoutUrl: '/logout-idle/', loginUrl: '/login/' };
  const nodes = { 'nexus-session-config': { textContent: JSON.stringify(config) }, 'idle-warning': warning, 'idle-countdown': countdown, 'idle-stay': stay };
  const window = {
    addEventListener: (name, callback) => { events[name] = callback; },
    location: { assign: url => redirects.push(url) },
  };
  vm.runInNewContext(source, {
    window, document: { hidden: false, getElementById: id => nodes[id], querySelector: () => ({ value: 'test-csrf' }), addEventListener: (name, callback) => { events[name] = callback; } },
    Date: { now: () => now },
    setInterval: callback => intervals.push(callback), setTimeout: callback => timeouts.push(callback),
    fetch: async (url, options) => {
      calls.push({ url, options });
      if (reject) throw new Error('Offline');
      return { ok: status === 200, status, redirected: false };
    },
  });
  return { calls, redirects, warning, countdown, stay, events, timeouts, setTime: value => { now = value; }, tick: () => intervals.forEach(fn => fn()) };
}
const flush = () => new Promise(resolve => setImmediate(resolve));

test('idle pages do not silently renew sessions', () => {
  const s = setup(); s.setTime(60000); s.tick();
  assert.equal(s.calls.length, 0);
});
test('real interaction renews with POST and a DOM-sourced CSRF token', async () => {
  const s = setup(); s.setTime(31000); s.events.keydown(); await flush();
  assert.equal(s.calls[0].url, '/session/activity/');
  assert.equal(s.calls[0].options.method, 'POST');
  assert.equal(s.calls[0].options.headers['X-CSRFToken'], 'test-csrf');
});
test('rapid pointer movement is throttled, not one request per event', async () => {
  const s = setup(); s.setTime(31000);
  for (let i = 0; i < 50; i++) s.events.pointermove();
  await flush(); assert.equal(s.calls.length, 1);
});
test('warning countdown uses the configured deadline', () => {
  const s = setup(); s.setTime(100000); s.tick();
  assert.equal(s.warning.hidden, false); assert.equal(s.countdown.textContent, 20);
});
test('returning to an expired tab logs out instead of resetting its clock', async () => {
  const s = setup(); s.setTime(121000); s.events.visibilitychange(); await flush();
  assert.equal(s.calls[0].url, '/logout-idle/');
  assert.equal(s.redirects[0], '/login/?reason=idle');
});
test('server expiry during renewal returns to login', async () => {
  const s = setup({ status: 401 }); s.setTime(31000); s.events.keydown(); await flush();
  assert.equal(s.redirects[0], '/login/?reason=idle');
});
test('Stay logged in explicitly renews and clears the warning', async () => {
  const s = setup(); s.setTime(100000); s.tick(); s.stay.click(); await flush();
  assert.equal(s.warning.hidden, true); assert.equal(s.calls[0].url, '/session/activity/');
});

test('activity in another tab prevents an idle tab from logging out the shared session', () => {
  const s = setup(); s.setTime(100000); s.tick();
  s.events.storage({ key: 'activity', newValue: '100000' });
  s.setTime(125000); s.tick();
  assert.equal(s.redirects.length, 0); assert.equal(s.warning.hidden, true);
});

test('offline expiry still navigates without an unhandled rejected promise', async () => {
  const s = setup({ reject: true }); s.setTime(121000); s.tick(); await flush();
  assert.equal(s.redirects[0], '/login/?reason=idle');
});
