import test from 'node:test';
import assert from 'node:assert/strict';
import {
  ENDPOINT, TOKEN, STORAGE_KEY, UUID_V7,
  uuidv7, tabId, reportedPath, referrerAddress, referringDomain, deviceType, utmParams,
  declinesMeasurement, measurable, pageContext, buildPayload, install,
} from '../../measure.js';

// The site's measurement module posts two events straight to PostHog's
// capture endpoint: a page view, and a click on an App Store link. These
// tests pin the pure parts without a browser, then drive the page wiring
// through stubs, because nothing here may ever reach a visitor's page
// broken: it runs on every page but the privacy policy.
//
//   node --test scripts/tests/measure.test.mjs

const ORIGIN = 'https://habitflame.vishutdhar.com';
const STORE = 'https://apps.apple.com/us/app/habit-flame-streak-tracker/id6756961710';
const INVITE_STORE = 'https://apps.apple.com/app/id6756961710';
// An invite link as the app sends it: the code in the path, and for a
// second version invite the inviter's name and id in the query.
const INVITE_URL = `${ORIGIN}/invite/K7QM2P?v=2&n=Sam%20Rivera&uid=3f2a9c1e-77aa-4c1b-9e0d-5a6b7c8d9e0f`;

/// A sessionStorage stand in that records every write.
function memoryStorage() {
  const map = new Map();
  return {
    map,
    getItem: (key) => (map.has(key) ? map.get(key) : null),
    setItem: (key, value) => { map.set(key, String(value)); },
  };
}

/// A storage whose every access throws, as Safari's does with site data blocked.
const refusingStorage = {
  getItem() { throw new Error('SecurityError'); },
  setItem() { throw new Error('SecurityError'); },
};

/// A page as the module sees it: document, navigator and window stubs, with
/// every request captured instead of sent. Cookies and localStorage record any
/// touch, so the tests can prove neither is used.
function world({
  url = `${ORIGIN}/`, referrer = '', readyState = 'interactive',
  nav = {}, storage = memoryStorage(), beacon = () => true, fetchImpl = null,
  innerWidth = 1280, innerHeight = 800,
} = {}) {
  const sent = [];
  const listeners = new Map();
  const touched = [];
  const doc = {
    referrer,
    readyState,
    addEventListener(type, handler, options) {
      listeners.set(type, [...(listeners.get(type) ?? []), { handler, options }]);
    },
    get cookie() { touched.push('cookie read'); return ''; },
    set cookie(value) { touched.push(`cookie write ${value}`); },
  };
  const navigator = {
    sendBeacon(target, body) {
      const accepted = beacon(target, body);
      if (accepted) sent.push({ via: 'beacon', target, body: JSON.parse(body) });
      return accepted;
    },
    ...nav,
  };
  const at = new URL(url);
  const win = {
    location: {
      href: at.href, origin: at.origin, pathname: at.pathname, host: at.host, hostname: at.hostname,
      protocol: at.protocol, search: at.search, hash: at.hash,
    },
    screen: { width: 1179, height: 2556 },
    innerWidth,
    innerHeight,
    get sessionStorage() { return storage; },
    get localStorage() { touched.push('localStorage'); return memoryStorage(); },
    fetch: fetchImpl ?? ((target, init) => {
      sent.push({ via: 'fetch', target, init, body: JSON.parse(init.body) });
      return Promise.resolve({ ok: true });
    }),
  };
  const fire = (type, event = {}) => {
    for (const { handler } of listeners.get(type) ?? []) handler({ type, button: 0, ...event });
  };
  return { doc, navigator, win, sent, listeners, touched, fire, storage };
}

/// An anchor and the image inside it, the shape of the footer badge. A click
/// lands on the image, so the module has to find the link from its target.
function link(href, placement) {
  const anchor = {
    href: new URL(href, ORIGIN).href,
    getAttribute: (name) => (name === 'data-placement' ? placement ?? null : name === 'href' ? href : null),
    closest: (selector) => (selector === 'a[href]' ? anchor : null),
  };
  const image = { closest: (selector) => anchor.closest(selector) };
  return { anchor, image };
}

const events = (w, name) => w.sent.filter((s) => s.body.event === name);
const everything = (w) => JSON.stringify(w.sent);

// ----- Identity -----

test('a uuid v7 carries version 7 and the RFC variant whatever the random bits are', () => {
  for (const fill of [0x00, 0xff, 0x5a, 0xa5]) {
    const id = uuidv7(1_700_000_000_000, (n) => new Uint8Array(n).fill(fill));
    assert.match(id, UUID_V7);
    assert.equal(id[14], '7', `version nibble in ${id}`);
    assert.match(id[19], /[89ab]/, `variant bits in ${id}`);
  }
  assert.equal(uuidv7(0, (n) => new Uint8Array(n).fill(0xff)), '00000000-0000-7fff-bfff-ffffffffffff');
  assert.equal(uuidv7(0, (n) => new Uint8Array(n)), '00000000-0000-7000-8000-000000000000');
});

test('a uuid v7 starts with the time in milliseconds, so ids sort by when they were made', () => {
  assert.ok(uuidv7(0x0123456789ab).startsWith('01234567-89ab-7'));
  const times = [1_700_000_000_000, 1_700_000_000_001, 1_700_000_000_256, 1_800_000_000_000];
  const ids = times.map((t) => uuidv7(t));
  assert.deepEqual([...ids].sort(), ids);
  const before = Date.now();
  const now = uuidv7();
  const after = Date.now();
  const stamp = parseInt(now.slice(0, 8) + now.slice(9, 13), 16);
  assert.ok(stamp >= before && stamp <= after, `time prefix ${stamp} outside ${before}..${after}`);
});

test('a uuid v7 draws its random bits from the platform generator', () => {
  const ids = new Set(Array.from({ length: 64 }, () => uuidv7(1_700_000_000_000)));
  assert.equal(ids.size, 64, 'ids made in the same millisecond must still differ');
  for (const id of ids) assert.match(id, UUID_V7);
});

test('one id per tab: kept in sessionStorage under one key and reused', () => {
  const storage = memoryStorage();
  const first = tabId({ sessionStorage: storage });
  assert.match(first, UUID_V7);
  assert.deepEqual([...storage.map.keys()], [STORAGE_KEY]);
  assert.equal(STORAGE_KEY, 'habitflame_measure_id');
  assert.equal(tabId({ sessionStorage: storage }), first, 'the next page in the tab keeps the id');
});

test('a stored value that is not a uuid v7 is replaced, not sent', () => {
  const storage = memoryStorage();
  storage.setItem(STORAGE_KEY, 'someone@example.com');
  const id = tabId({ sessionStorage: storage });
  assert.match(id, UUID_V7);
  assert.equal(storage.getItem(STORAGE_KEY), id);
});

test('refused storage falls back to a fresh id for this page load', () => {
  const a = tabId({ sessionStorage: refusingStorage });
  const b = tabId({ sessionStorage: refusingStorage });
  assert.match(a, UUID_V7);
  assert.match(b, UUID_V7);
  assert.notEqual(a, b);
  const throwingGetter = { get sessionStorage() { throw new Error('SecurityError'); } };
  assert.match(tabId(throwingGetter), UUID_V7);
});

// ----- Addresses -----

test('an invite address is reported as /invite, never with its code', () => {
  assert.equal(reportedPath('/invite/K7QM2P'), '/invite');
  assert.equal(reportedPath('/invite/K7QM2P/'), '/invite');
  assert.equal(reportedPath('/invite/'), '/invite');
  assert.equal(reportedPath('/invite'), '/invite');
  assert.equal(reportedPath('/invite.html'), '/invite');
  assert.equal(reportedPath('/Invite/K7QM2P'), '/invite');
  assert.equal(reportedPath('/invite/a/b/c'), '/invite');
});

test('every other address is reported as it is', () => {
  assert.equal(reportedPath('/'), '/');
  assert.equal(reportedPath('/support'), '/support');
  assert.equal(reportedPath('/habit-tracker-with-friends'), '/habit-tracker-with-friends');
  assert.equal(reportedPath('/invites'), '/invites', 'only the invite page itself is collapsed');
  assert.equal(reportedPath('/inviteK7QM2P'), '/inviteK7QM2P');
  assert.equal(reportedPath(''), '/');
  assert.equal(reportedPath(undefined), '/');
});

test('the referrer is reported as its origin and path, with no query, fragment or invite code', () => {
  assert.equal(referrerAddress(''), '$direct');
  assert.equal(referrerAddress(undefined), '$direct');
  assert.equal(referrerAddress('not a url'), '$direct');
  assert.equal(referrerAddress('android-app://com.google.android.gm/'), '$direct');
  assert.equal(referrerAddress('https://www.google.com/'), 'https://www.google.com/');
  assert.equal(referrerAddress('https://www.reddit.com/r/getdisciplined/comments/abc/?utm_source=share#top'),
    'https://www.reddit.com/r/getdisciplined/comments/abc/');
  assert.equal(referrerAddress(`${ORIGIN}/streak-tracker-app?x=1`), `${ORIGIN}/streak-tracker-app`);
  assert.equal(referrerAddress(INVITE_URL), `${ORIGIN}/invite`);
});

test('the referring domain is the referrer host, or $direct', () => {
  assert.equal(referringDomain(''), '$direct');
  assert.equal(referringDomain(undefined), '$direct');
  assert.equal(referringDomain('not a url'), '$direct');
  assert.equal(referringDomain('https://www.google.com/search?q=habit+tracker'), 'www.google.com');
  assert.equal(referringDomain(INVITE_URL), 'habitflame.vishutdhar.com');
});

test('the device type is Mobile under a 768 pixel viewport', () => {
  assert.equal(deviceType(375), 'Mobile');
  assert.equal(deviceType(767), 'Mobile');
  assert.equal(deviceType(768), 'Desktop');
  assert.equal(deviceType(1280), 'Desktop');
});

test('only the campaign parameters present on the URL are forwarded', () => {
  assert.deepEqual(utmParams(''), {});
  assert.deepEqual(utmParams('?v=2&n=Sam&uid=1'), {});
  assert.deepEqual(utmParams('?utm_source=reddit&utm_medium=post&other=1'),
    { utm_source: 'reddit', utm_medium: 'post' });
  assert.deepEqual(utmParams('?utm_source=&utm_term=habit%20buddy'), { utm_term: 'habit buddy' });
  assert.deepEqual(
    utmParams('?utm_source=a&utm_medium=b&utm_campaign=c&utm_content=d&utm_term=e'),
    { utm_source: 'a', utm_medium: 'b', utm_campaign: 'c', utm_content: 'd', utm_term: 'e' },
  );
});

test('Global Privacy Control and Do Not Track both decline measurement', () => {
  assert.equal(declinesMeasurement({ globalPrivacyControl: true }), true);
  assert.equal(declinesMeasurement({ doNotTrack: '1' }), true);
  assert.equal(declinesMeasurement({ globalPrivacyControl: false, doNotTrack: '0' }), false);
  assert.equal(declinesMeasurement({ doNotTrack: 'unspecified' }), false);
  assert.equal(declinesMeasurement({}), false);
});

test('local and file pages are never measured', () => {
  const at = (href) => { const u = new URL(href); return { hostname: u.hostname, protocol: u.protocol }; };
  assert.equal(measurable({}, at(`${ORIGIN}/`)), true);
  assert.equal(measurable({}, at('https://habitflame-web-git-x-vishutdhar.vercel.app/')), true);
  assert.equal(measurable({}, at('http://localhost:3000/')), false);
  assert.equal(measurable({}, at('http://127.0.0.1:8080/support')), false);
  assert.equal(measurable({}, at('file:///Users/x/habitflame-web/index.html')), false);
  assert.equal(measurable({ globalPrivacyControl: true }, at(`${ORIGIN}/`)), false);
});

// ----- Payload -----

const REQUIRED_PROPERTIES = [
  'distinct_id', '$session_id', '$current_url', '$pathname', '$host', '$referrer', '$referring_domain',
  'page', '$lib', '$lib_version', '$process_person_profile', 'app', 'bundle_id', 'surface',
  '$screen_width', '$screen_height', '$viewport_width', '$viewport_height', '$device_type',
];

test('a payload carries the token, the event, a timestamp and every required property', () => {
  const w = world({ url: `${ORIGIN}/streak-tracker-app`, referrer: 'https://duckduckgo.com/' });
  const id = uuidv7();
  const payload = buildPayload({
    event: '$pageview', id, page: pageContext(w.doc, w.win), timestamp: '2026-11-02T12:00:00.000Z',
  });
  assert.deepEqual(Object.keys(payload).sort(), ['api_key', 'event', 'properties', 'timestamp']);
  assert.equal(payload.api_key, TOKEN);
  assert.equal(TOKEN, 'phc_J1tSpBnq3nRgP8VrUlkhQCoB0wIORi3m6EU2q2N537O', 'the shared project every app reports to');
  assert.equal(payload.event, '$pageview');
  assert.equal(payload.timestamp, '2026-11-02T12:00:00.000Z');
  assert.deepEqual(Object.keys(payload.properties).sort(), [...REQUIRED_PROPERTIES].sort());
  assert.deepEqual(payload.properties, {
    distinct_id: id,
    $session_id: id,
    $current_url: `${ORIGIN}/streak-tracker-app`,
    $pathname: '/streak-tracker-app',
    $host: 'habitflame.vishutdhar.com',
    $referrer: 'https://duckduckgo.com/',
    $referring_domain: 'duckduckgo.com',
    page: '/streak-tracker-app',
    $lib: 'habitflame-web',
    $lib_version: '1',
    $process_person_profile: false,
    app: 'habitflame',
    bundle_id: 'habitflame.vishutdhar.com',
    surface: 'web',
    $screen_width: 1179,
    $screen_height: 2556,
    $viewport_width: 1280,
    $viewport_height: 800,
    $device_type: 'Desktop',
  });
});

test('the page address is sent without its query or fragment', () => {
  const w = world({ url: `${ORIGIN}/support?ref=newsletter&email=sam%40example.com#restore` });
  const { properties } = buildPayload({ event: '$pageview', id: uuidv7(), page: pageContext(w.doc, w.win), timestamp: 'x' });
  assert.equal(properties.$current_url, `${ORIGIN}/support`);
  assert.equal(properties.$pathname, '/support');
  assert.equal(properties.page, '/support');
  assert.ok(!JSON.stringify(properties).includes('example.com'));
});

test('an invite page is reported as /invite, without the code, the name or the id', () => {
  const w = world({ url: INVITE_URL, referrer: '' });
  install(w.doc, w.navigator, w.win);
  w.fire('click', { target: link(INVITE_STORE, 'invite_step').anchor });
  assert.deepEqual(w.sent.map((s) => s.body.event), ['$pageview', 'store_link_clicked']);
  for (const { body } of w.sent) {
    assert.equal(body.properties.$current_url, `${ORIGIN}/invite`);
    assert.equal(body.properties.$pathname, '/invite');
    assert.equal(body.properties.page, '/invite');
  }
  const sent = everything(w);
  for (const secret of ['K7QM2P', 'Sam', 'Rivera', '3f2a9c1e', 'uid', 'v=2']) {
    assert.ok(!sent.includes(secret), `${secret} reached the payload`);
  }
});

test('a page reached from an invite page names /invite as its referrer, never the code', () => {
  const w = world({ url: `${ORIGIN}/support`, referrer: INVITE_URL });
  install(w.doc, w.navigator, w.win);
  const [{ body }] = w.sent;
  assert.equal(body.properties.$referrer, `${ORIGIN}/invite`);
  assert.equal(body.properties.$referring_domain, 'habitflame.vishutdhar.com');
  for (const secret of ['K7QM2P', 'Sam', '3f2a9c1e']) assert.ok(!everything(w).includes(secret), secret);
});

test('a direct visit reads $direct for both referrer properties', () => {
  const w = world();
  const { properties } = buildPayload({ event: '$pageview', id: uuidv7(), page: pageContext(w.doc, w.win), timestamp: 'x' });
  assert.equal(properties.$referrer, '$direct');
  assert.equal(properties.$referring_domain, '$direct');
});

test('campaign parameters ride on the payload only when the URL has them', () => {
  const plain = world();
  const tagged = world({ url: `${ORIGIN}/?utm_source=reddit&utm_campaign=new-year` });
  const props = (w) => buildPayload({ event: '$pageview', id: uuidv7(), page: pageContext(w.doc, w.win), timestamp: 'x' }).properties;
  assert.ok(!Object.keys(props(plain)).some((k) => k.startsWith('utm_')));
  assert.equal(props(tagged).utm_source, 'reddit');
  assert.equal(props(tagged).utm_campaign, 'new-year');
  assert.ok(!('utm_medium' in props(tagged)));
  assert.equal(props(tagged).$current_url, `${ORIGIN}/`);
});

test('event properties cannot overwrite identity or the fixed properties', () => {
  const w = world();
  const id = uuidv7();
  const { properties } = buildPayload({
    event: 'store_link_clicked', id, page: pageContext(w.doc, w.win), timestamp: 'x',
    properties: { placement: 'home_hero', distinct_id: 'other', app: 'other', page: '/x', $process_person_profile: true },
  });
  assert.equal(properties.placement, 'home_hero');
  assert.equal(properties.distinct_id, id);
  assert.equal(properties.app, 'habitflame');
  assert.equal(properties.page, '/');
  assert.equal(properties.$process_person_profile, false);
});

test('a narrow viewport is reported as Mobile', () => {
  const w = world({ innerWidth: 390, innerHeight: 844 });
  const { properties } = buildPayload({ event: '$pageview', id: uuidv7(), page: pageContext(w.doc, w.win), timestamp: 'x' });
  assert.equal(properties.$device_type, 'Mobile');
  assert.equal(properties.$viewport_width, 390);
});

// ----- Wiring -----

test('one page view is sent at install', () => {
  const w = world({ url: `${ORIGIN}/` });
  install(w.doc, w.navigator, w.win);
  assert.equal(w.sent.length, 1);
  const [{ via, target, body }] = w.sent;
  assert.equal(via, 'beacon');
  assert.equal(target, ENDPOINT);
  assert.equal(ENDPOINT, 'https://us.i.posthog.com/i/v0/e/');
  assert.equal(body.event, '$pageview');
  assert.equal(body.properties.$pathname, '/');
  assert.match(body.timestamp, /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z$/);
  assert.match(body.properties.distinct_id, UUID_V7);
  assert.equal(body.properties.$session_id, body.properties.distinct_id);
});

test('the page view goes at install, first, even while the document is still parsing', () => {
  const w = world({ readyState: 'loading' });
  install(w.doc, w.navigator, w.win);
  assert.deepEqual(w.sent.map((s) => s.body.event), ['$pageview']);
  w.fire('DOMContentLoaded');
  w.fire('load');
  assert.deepEqual(w.sent.map((s) => s.body.event), ['$pageview'], 'loading sends nothing more');
});

test('only two events exist: the page view and the store click', () => {
  const w = world();
  install(w.doc, w.navigator, w.win);
  w.fire('click', { target: link(STORE, 'home_hero').image });
  w.fire('scroll');
  w.fire('visibilitychange');
  w.fire('pagehide');
  assert.deepEqual(w.sent.map((s) => s.body.event), ['$pageview', 'store_link_clicked']);
  assert.deepEqual([...w.listeners.keys()].sort(), ['auxclick', 'click']);
});

test('the pages of one tab share one id, and nothing goes to cookies or localStorage', () => {
  const storage = memoryStorage();
  const first = world({ url: `${ORIGIN}/`, storage });
  install(first.doc, first.navigator, first.win);
  const second = world({ url: `${ORIGIN}/support`, storage });
  install(second.doc, second.navigator, second.win);
  assert.equal(first.sent[0].body.properties.distinct_id, second.sent[0].body.properties.distinct_id);
  assert.deepEqual([...storage.map.keys()], [STORAGE_KEY]);
  assert.deepEqual([...first.touched, ...second.touched], []);
});

test('refused storage still measures, with an id for this page load only', () => {
  const w = world({ storage: refusingStorage });
  install(w.doc, w.navigator, w.win);
  assert.equal(w.sent.length, 1);
  assert.match(w.sent[0].body.properties.distinct_id, UUID_V7);
});

for (const [label, nav] of [['Global Privacy Control', { globalPrivacyControl: true }], ['Do Not Track', { doNotTrack: '1' }]]) {
  test(`${label} means nothing is sent, stored or listened for`, () => {
    const storage = memoryStorage();
    const w = world({ nav, storage });
    install(w.doc, w.navigator, w.win);
    w.fire('click', { target: link(STORE, 'home_hero').image });
    w.fire('DOMContentLoaded');
    assert.deepEqual(w.sent, []);
    assert.equal(storage.map.size, 0, 'no id is kept for a visitor who declined');
    assert.equal(w.listeners.size, 0);
    assert.deepEqual(w.touched, []);
  });
}

test('a local page sends nothing', () => {
  for (const url of ['http://localhost:8000/', 'http://127.0.0.1:5173/support']) {
    const w = world({ url });
    install(w.doc, w.navigator, w.win);
    w.fire('click', { target: link(STORE, 'home_hero').image });
    assert.deepEqual(w.sent, [], url);
  }
});

test('a click on a store link sends one store_link_clicked with its placement', () => {
  const w = world({ url: `${ORIGIN}/` });
  install(w.doc, w.navigator, w.win);
  w.fire('click', { target: link(STORE, 'home_hero').image });
  const clicks = events(w, 'store_link_clicked');
  assert.equal(clicks.length, 1);
  assert.equal(clicks[0].via, 'beacon');
  assert.equal(clicks[0].body.properties.placement, 'home_hero');
  assert.equal(clicks[0].body.properties.page, '/');
  assert.equal(clicks[0].body.properties.distinct_id, w.sent[0].body.properties.distinct_id);
});

test('a store link with campaign parameters is still a store link', () => {
  const w = world();
  install(w.doc, w.navigator, w.win);
  w.fire('click', { target: link(`${STORE}?pt=123456&ct=site-home&mt=8`, 'home_cta').anchor });
  assert.equal(events(w, 'store_link_clicked')[0].body.properties.placement, 'home_cta');
});

test('the click listener runs in the capture phase, so no other handler can hide a click', () => {
  const w = world();
  install(w.doc, w.navigator, w.win);
  for (const type of ['click', 'auxclick']) {
    const [entry] = w.listeners.get(type);
    assert.ok(entry.options === true || entry.options?.capture === true, `${type} listener must capture`);
  }
});

test('a store link without a placement is reported as unknown', () => {
  const w = world();
  install(w.doc, w.navigator, w.win);
  w.fire('click', { target: link(STORE).anchor });
  assert.equal(events(w, 'store_link_clicked')[0].body.properties.placement, 'unknown');
});

test('clicks anywhere else send nothing', () => {
  const w = world();
  install(w.doc, w.navigator, w.win);
  w.fire('click', { target: link('/support', 'nav').image });
  w.fire('click', { target: link('https://freedom-terminal.com/', 'footer').anchor });
  w.fire('click', { target: link('https://example.com/?next=apps.apple.com', 'x').anchor });
  w.fire('click', { target: link('habitflame://invite?code=K7QM2P', 'open').anchor });
  w.fire('click', { target: { closest: () => null } });
  w.fire('click', { target: null });
  assert.equal(events(w, 'store_link_clicked').length, 0);
});

test('a middle click opens the store in a new tab and counts once; a right click does not', () => {
  const w = world();
  install(w.doc, w.navigator, w.win);
  w.fire('auxclick', { button: 1, target: link(STORE, 'guide_cta').image });
  w.fire('auxclick', { button: 2, target: link(STORE, 'guide_cta').image });
  const clicks = events(w, 'store_link_clicked');
  assert.equal(clicks.length, 1);
  assert.equal(clicks[0].body.properties.placement, 'guide_cta');
});

test('a refused beacon falls back to a keepalive fetch with the same body', () => {
  const w = world({ beacon: () => false });
  install(w.doc, w.navigator, w.win);
  assert.equal(w.sent.length, 1);
  const [{ via, target, init, body }] = w.sent;
  assert.equal(via, 'fetch');
  assert.equal(target, ENDPOINT);
  assert.equal(init.method, 'POST');
  assert.equal(init.keepalive, true);
  assert.equal(init.credentials, 'omit');
  assert.equal(body.event, '$pageview');
});

test('a throwing beacon falls back to fetch too', () => {
  const w = world({ beacon: () => { throw new TypeError('Illegal invocation'); } });
  install(w.doc, w.navigator, w.win);
  assert.equal(w.sent.length, 1);
  assert.equal(w.sent[0].via, 'fetch');
});

test('every failure is silent: no transport, a rejecting fetch, a throwing fetch', async () => {
  const unhandled = [];
  const onUnhandled = (reason) => unhandled.push(reason);
  process.on('unhandledRejection', onUnhandled);
  try {
    const cases = [
      world({ beacon: () => false, fetchImpl: () => Promise.reject(new TypeError('Failed to fetch')) }),
      world({ beacon: () => false, fetchImpl: () => { throw new TypeError('blocked'); } }),
      world({ nav: { sendBeacon: undefined } }),
    ];
    cases[2].win.fetch = undefined;
    for (const w of cases) {
      install(w.doc, w.navigator, w.win);
      w.fire('click', { target: link(STORE, 'home_hero').image });
    }
    await new Promise((resolve) => setImmediate(resolve));
    assert.deepEqual(unhandled, []);
  } finally {
    process.off('unhandledRejection', onUnhandled);
  }
});

test('a broken page context never throws out of install', () => {
  const w = world();
  Object.defineProperty(w.win, 'screen', { get() { throw new Error('no screen'); } });
  assert.doesNotThrow(() => install(w.doc, w.navigator, w.win));
  assert.doesNotThrow(() => install(null, null, null));
  assert.doesNotThrow(() => install({}, {}, {}));
});

test('importing the module outside a browser installs nothing', async () => {
  const module = await import('../../measure.js');
  assert.equal(typeof module.install, 'function');
});
