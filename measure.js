// Site measurement: anonymous page views and App Store link clicks, posted
// straight to PostHog's capture endpoint.
//
// No PostHog SDK and no third party script: this file is served from this
// site. No cookies, no localStorage, no person profiles, no autocapture, no
// replay. The only identifier is a random UUID kept in sessionStorage for the
// life of the tab. A browser that sends Global Privacy Control or Do Not Track
// is not measured at all, and nothing is sent from a copy of the site served
// from this machine or the local network, or opened as a file.
// The privacy policy page never loads this file.
//
// Addresses are sent without their query or fragment. An invite link carries
// the invite code in its path and the inviter's name and id in its query, so
// an invite page, and a referrer that was one, is reported as /invite alone.
//
// Pages load it with <script type="module" async>, so a slow or blocked
// download never holds up anything else on the page.
//
// Follows the RateProof site measurement design (RateProof app repository,
// docs/superpowers/specs/2026-11-01-site-measurement-design.md), without its
// calculator events.

export const ENDPOINT = 'https://us.i.posthog.com/i/v0/e/';
// The shared project's public, write only token: it can send events, not
// read them. The HabitFlame app reports to the same project.
export const TOKEN = 'phc_J1tSpBnq3nRgP8VrUlkhQCoB0wIORi3m6EU2q2N537O';
export const STORAGE_KEY = 'habitflame_measure_id';
export const UUID_V7 = /^[0-9a-f]{8}-[0-9a-f]{4}-7[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/;

const UTM_KEYS = ['utm_source', 'utm_medium', 'utm_campaign', 'utm_content', 'utm_term'];
const MOBILE_BELOW = 768;
const STORE_HOST = 'apps.apple.com';
const INVITE_PATH = /^\/invite(?:\/|\.html$|$)/i;

const randomBytes = (count) => crypto.getRandomValues(new Uint8Array(count));

/// A UUID version 7: the Unix time in milliseconds in the first 48 bits, then
/// random bits with the version and variant set. PostHog reads a session's
/// start from that time prefix, which is why its sessions need version 7.
export function uuidv7(now = Date.now(), random = randomBytes) {
  const bytes = new Uint8Array(16);
  bytes.set(random(10).subarray(0, 10), 6);
  let ms = Math.max(0, Math.floor(now));
  for (let i = 5; i >= 0; i -= 1) {
    bytes[i] = ms % 256;
    ms = Math.floor(ms / 256);
  }
  bytes[6] = (bytes[6] & 0x0f) | 0x70;
  bytes[8] = (bytes[8] & 0x3f) | 0x80;
  const hex = Array.from(bytes, (b) => b.toString(16).padStart(2, '0')).join('');
  return `${hex.slice(0, 8)}-${hex.slice(8, 12)}-${hex.slice(12, 16)}-${hex.slice(16, 20)}-${hex.slice(20)}`;
}

/// The tab's id: one UUID kept in sessionStorage, so every page a tab opens
/// shares it and nothing outlives the tab. When storage is refused, which some
/// browsers do with site data blocked, a fresh id serves this page load alone.
/// A browser copies sessionStorage into a duplicated tab, so a duplicate keeps
/// the id it was copied from and counts as the same session.
export function tabId(win, make = uuidv7) {
  let id = null;
  try {
    const storage = win.sessionStorage;
    const kept = storage.getItem(STORAGE_KEY);
    if (typeof kept === 'string' && UUID_V7.test(kept)) return kept;
    id = make();
    storage.setItem(STORAGE_KEY, id);
  } catch {
    // Storage is unavailable; the id below lives only as long as this page.
  }
  return id ?? make();
}

/// The path an event reports: the page's own path, except that every invite
/// address (/invite/<code>, and the page's own file) is reported as /invite.
export function reportedPath(pathname) {
  if (typeof pathname !== 'string' || pathname === '') return '/';
  return INVITE_PATH.test(pathname) ? '/invite' : pathname;
}

/// The page that linked here as its origin and path only, or "$direct" when
/// there was none: a query or a fragment can carry anything, and a link from
/// an invite page names the code in its path.
export function referrerAddress(referrer) {
  if (!referrer) return '$direct';
  try {
    const at = new URL(referrer);
    if (at.protocol !== 'https:' && at.protocol !== 'http:') return '$direct';
    return `${at.origin}${reportedPath(at.pathname)}`;
  } catch {
    return '$direct';
  }
}

/// The host of the page that linked here, or "$direct" when there was none.
export function referringDomain(referrer) {
  if (!referrer) return '$direct';
  try {
    return new URL(referrer).hostname || '$direct';
  } catch {
    return '$direct';
  }
}

export function deviceType(viewportWidth) {
  return viewportWidth < MOBILE_BELOW ? 'Mobile' : 'Desktop';
}

/// The campaign parameters on the URL, only those present with a value.
export function utmParams(search) {
  const found = {};
  try {
    const params = new URLSearchParams(search ?? '');
    for (const key of UTM_KEYS) {
      const value = params.get(key);
      if (value) found[key] = value;
    }
  } catch {
    // An unreadable query carries no campaign.
  }
  return found;
}

export function declinesMeasurement(nav) {
  return nav?.globalPrivacyControl === true || nav?.doNotTrack === '1';
}

/// An IPv4 address as its four numbers, or null for anything else.
function ipv4Octets(host) {
  const m = /^(\d{1,3})\.(\d{1,3})\.(\d{1,3})\.(\d{1,3})$/.exec(host);
  return m ? m.slice(1).map(Number) : null;
}

/// Addresses that never leave this machine or the local network: this
/// network (0/8), the private ranges 10/8, 172.16/12 and 192.168/16,
/// loopback 127/8 and link local 169.254/16.
function isLocalIPv4([a, b]) {
  return a === 0 || a === 10 || a === 127 || (a === 169 && b === 254)
    || (a === 172 && b >= 16 && b <= 31) || (a === 192 && b === 168);
}

/// Whether a host is this machine or the local network: localhost and any
/// name under .localhost, mDNS names under .local, local IPv4 addresses (see
/// isLocalIPv4), IPv6 loopback and the unspecified address, unique local
/// fc00::/7 and link local fe80::/10 addresses, and any of the IPv4 ones
/// written as IPv4 mapped IPv6, in the forms a browser leaves in
/// location.hostname. A trailing dot changes nothing; a missing host counts
/// as local, so it is never measured.
export function isLocalHost(hostname) {
  if (typeof hostname !== 'string') return true;
  const host = hostname.toLowerCase().replace(/\.$/, '');
  if (host === '') return true;
  if (host === 'localhost' || host.endsWith('.localhost') || host.endsWith('.local')) return true;
  const v4 = ipv4Octets(host);
  if (v4) return isLocalIPv4(v4);
  const v6 = host.startsWith('[') && host.endsWith(']') ? host.slice(1, -1) : host;
  if (v6 === '::1' || v6 === '::') return true;
  const mapped = /^::ffff:([0-9a-f]{1,4}):([0-9a-f]{1,4})$/.exec(v6);
  if (mapped) {
    const hi = parseInt(mapped[1], 16);
    const lo = parseInt(mapped[2], 16);
    return isLocalIPv4([hi >> 8, hi & 255, lo >> 8, lo & 255]);
  }
  return /^f[cd][0-9a-f]{2}:/.test(v6) || /^fe[89ab][0-9a-f]:/.test(v6);
}

/// Whether this page load may send anything: a public host over http or
/// https, and a browser that has not asked not to be measured.
export function measurable(nav, location) {
  if (declinesMeasurement(nav)) return false;
  if (location?.protocol !== 'https:' && location?.protocol !== 'http:') return false;
  return !isLocalHost(location.hostname);
}

/// What an event says about the page it came from, read at the moment it is
/// sent. The query is read only for its campaign parameters.
export function pageContext(doc, win) {
  const { location, screen } = win;
  return {
    origin: `${location.protocol}//${location.host}`,
    path: reportedPath(location.pathname),
    host: location.host,
    search: location.search,
    referrer: doc.referrer || '',
    screenWidth: screen?.width,
    screenHeight: screen?.height,
    viewportWidth: win.innerWidth,
    viewportHeight: win.innerHeight,
  };
}

/// The capture request body. Event properties come first, so they can never
/// replace the identity or the fixed properties after them.
export function buildPayload({ event, properties = {}, id, page, timestamp }) {
  return {
    api_key: TOKEN,
    event,
    properties: {
      ...utmParams(page.search),
      ...properties,
      distinct_id: id,
      $session_id: id,
      $current_url: `${page.origin}${page.path}`,
      $pathname: page.path,
      $host: page.host,
      $referrer: referrerAddress(page.referrer),
      $referring_domain: referringDomain(page.referrer),
      page: page.path,
      $lib: 'habitflame-web',
      $lib_version: '1',
      $process_person_profile: false,
      app: 'habitflame',
      bundle_id: 'habitflame.vishutdhar.com',
      surface: 'web',
      $screen_width: page.screenWidth,
      $screen_height: page.screenHeight,
      $viewport_width: page.viewportWidth,
      $viewport_height: page.viewportHeight,
      $device_type: deviceType(page.viewportWidth),
    },
    timestamp,
  };
}

/// Sends one body without waiting on it. A beacon is queued by the browser and
/// survives the navigation a store click starts; a keepalive fetch is the
/// fallback. A plain text body keeps it a simple request with no preflight.
/// Every failure is dropped: measurement never surfaces an error to the page.
function transmit(nav, win, body) {
  try {
    if (typeof nav.sendBeacon === 'function' && nav.sendBeacon(ENDPOINT, body)) return;
  } catch {
    // Fall through to fetch.
  }
  try {
    const pending = win.fetch(ENDPOINT, { method: 'POST', body, keepalive: true, credentials: 'omit' });
    pending?.catch?.(() => {});
  } catch {
    // Nothing left to try.
  }
}

/// The store link a click landed on, or null. The click often lands on the
/// badge image inside the link, so the link is found from the target.
function storeLink(target) {
  const anchor = target?.closest?.('a[href]');
  if (!anchor) return null;
  try {
    return new URL(anchor.href).hostname === STORE_HOST ? anchor : null;
  } catch {
    return null;
  }
}

/// Wires measurement into a page: a page view now, and a store_link_clicked
/// for every activation of an App Store link, with the link's placement.
/// When the page may not be measured, nothing is sent, stored or listened for.
export function install(doc, nav, win) {
  try {
    if (!doc || !nav || !win || !measurable(nav, win.location)) return;
    const id = tabId(win);
    const send = (event, properties) => {
      try {
        const payload = buildPayload({
          event, properties, id, page: pageContext(doc, win), timestamp: new Date().toISOString(),
        });
        transmit(nav, win, JSON.stringify(payload));
      } catch {
        // A page that cannot be described sends nothing.
      }
    };

    // Click covers mouse, touch and keyboard activation; a middle click opens
    // the link in a new tab without one, so auxclick on that button counts too.
    // Not pointerdown: it fires on presses that never open the link, such as
    // the start of a touch scroll, and with click it would count twice.
    const onActivate = (event) => {
      try {
        if (event.type === 'auxclick' && event.button !== 1) return;
        const anchor = storeLink(event.target);
        if (!anchor) return;
        send('store_link_clicked', { placement: anchor.getAttribute('data-placement') || 'unknown' });
      } catch {
        // A click is never blocked by measurement.
      }
    };
    doc.addEventListener('click', onActivate, true);
    doc.addEventListener('auxclick', onActivate, true);

    // At install, not at DOMContentLoaded: this module is async and can install
    // while the page is still parsing. The page view needs nothing the parser
    // produces, so sending it now keeps it the first event of every visit.
    send('$pageview', {});
  } catch {
    // Measurement is optional; the page never depends on it.
  }
}

if (typeof window !== 'undefined' && typeof document !== 'undefined') {
  install(document, navigator, window);
}
