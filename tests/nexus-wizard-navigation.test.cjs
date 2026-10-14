const {test} = require('node:test');
const assert = require('node:assert/strict');
const {readFileSync} = require('node:fs');
const {runInNewContext} = require('node:vm');
const script = readFileSync('static/js/nexus-wizard.js', 'utf8');

function boot(desktop, supportsMatchMedia = true) {
    const navigation = {open: true}; // Server-rendered native details: no-JS fallback.
    const root = {getAttribute: () => null};
    const media = {matches: desktop, addEventListener: (name, callback) => {media.change = callback;}};
    const document = {
        readyState: 'complete',
        getElementById: id => id === 'nx-wizard-root' ? root : id === 'wizard-step-navigation' ? navigation : null,
        querySelector: () => null,
        addEventListener() {},
    };
    const window = {addEventListener() {}, matchMedia: supportsMatchMedia ? () => media : undefined};
    runInNewContext(script, {window, document});
    return {navigation, media};
}

test('wizard starts with mobile steps collapsed', () => {
    assert.equal(boot(false).navigation.open, false);
});
test('wizard keeps desktop steps visible', () => {
    assert.equal(boot(true).navigation.open, true);
});
test('crossing the layout breakpoint updates the native disclosure', () => {
    const {navigation, media} = boot(false);
    media.matches = true;
    media.change();
    assert.equal(navigation.open, true);
    media.matches = false;
    media.change();
    assert.equal(navigation.open, false);
});
test('without matchMedia, the server-rendered navigation stays available', () => {
    assert.equal(boot(false, false).navigation.open, true);
});
