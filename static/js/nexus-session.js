/* One idle policy, supplied by Django. Only real interaction renews the session. */
(function () {
  'use strict';
  const node = document.getElementById('nexus-session-config');
  if (!node) return;
  const config = JSON.parse(node.textContent);
  const warning = document.getElementById('idle-warning');
  const countdown = document.getElementById('idle-countdown');
  const csrf = document.querySelector('#nexus-session-csrf input').value;
  let lastActivity = Date.now();
  let lastSync = Date.now();
  let pending = false;
  let leaving = false;
  let lastBroadcast = 0;
  const syncInterval = Math.min(30000, config.timeoutMs / 4);

  function signIn() {
    if (leaving) return;
    leaving = true;
    if (window.NexusSkeleton) window.NexusSkeleton.show("auth");
    window.location.assign(config.loginUrl + '?reason=idle');
  }
  async function post(url) {
    return fetch(url, { method: 'POST', credentials: 'same-origin', headers: { 'X-CSRFToken': csrf } });
  }
  async function renew(force) {
    if (pending || leaving || (!force && Date.now() - lastSync < syncInterval)) return;
    pending = true;
    try {
      const response = await post(config.heartbeatUrl);
      if (response.status === 401 || response.redirected) { signIn(); return; }
      if (!response.ok) throw new Error('Session renewal failed');
      lastSync = Date.now();
    } catch (_) {
      if (force && window.nexusToast) window.nexusToast('Could not renew your session. Check your connection and try again.', 'warning');
    } finally { pending = false; }
  }
  function activity() {
    // A suspended tab must not silently reset an already elapsed deadline.
    if (Date.now() - lastActivity >= config.timeoutMs) { expire(); return; }
    lastActivity = Date.now();
    if (lastActivity - lastBroadcast >= 1000) {
      try { window.localStorage.setItem(config.activityKey, String(lastActivity)); } catch (_) { /* Storage can be disabled. */ }
      lastBroadcast = lastActivity;
    }
    warning.hidden = true;
    renew(false);
  }
  function expire() {
    if (leaving) return;
    leaving = true;
    if (window.NexusSkeleton) window.NexusSkeleton.show("auth");
    // Navigate even if the network stalls; server middleware enforces expiry.
    const redirect = () => window.location.assign(config.loginUrl + '?reason=idle');
    setTimeout(redirect, 3000);
    post(config.logoutUrl).then(redirect, redirect);
  }
  function tick() {
    const remaining = config.timeoutMs - (Date.now() - lastActivity);
    if (remaining <= 0) { expire(); return; }
    warning.hidden = remaining > config.warningMs;
    countdown.textContent = Math.ceil(remaining / 1000);
    // A keystroke near a throttle boundary still reaches the server.
    if (lastActivity > lastSync) renew(false);
  }
  document.getElementById('idle-stay').addEventListener('click', () => { activity(); renew(true); });
  ['pointerdown', 'pointermove', 'keydown', 'touchstart', 'scroll'].forEach(event => window.addEventListener(event, activity, { passive: true }));
  // A background tab must not log out another tab where the user is working.
  window.addEventListener('storage', event => {
    if (event.key !== config.activityKey) return;
    const timestamp = Number(event.newValue);
    if (timestamp > lastActivity && timestamp <= Date.now()) {
      lastActivity = timestamp;
      warning.hidden = true;
    }
  });
  document.addEventListener('visibilitychange', () => { if (!document.hidden) tick(); });
  setInterval(tick, 1000);
})();
