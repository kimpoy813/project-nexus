/**
 * Makes Remotion Studio's same-origin guard reverse-proxy aware.
 *
 * Upstream validate-same-origin.js rejects a request whenever
 * `new URL(origin).origin !== 'http://' + host`. That breaks behind an HTTPS
 * preview proxy for two reasons:
 *   1. the browser Origin is https while the internal Host is served over http;
 *   2. the proxy may rewrite Host to an internal name and pass the public
 *      hostname in X-Forwarded-Host (or the RFC 7239 Forwarded header).
 * Without this patch every state-changing studio API call fails with HTTP 500
 * "Request from different origin not allowed" and the UI cannot load.
 *
 * Patched behaviour, in order of trust:
 *   - read the public host from X-Forwarded-Host, then the RFC 7239
 *     `Forwarded: host=...` parameter, then fall back to the Host header;
 *   - compare the Origin's hostname (and an explicit port, if both sides
 *     state one) rather than scheme + host, so the https -> http hop is fine;
 *   - if no forwarded host is present but X-Forwarded-Proto/Forwarded says
 *     https and Host is a loopback/private address, the request arrived via a
 *     TLS-terminating proxy, so the browser's Origin host is accepted.
 * Genuinely cross-origin requests against a public Host are still rejected,
 * so DNS-rebinding protection stays in place for normal (non-proxied) use.
 *
 * Idempotent: safe to run from `postinstall` on every npm install.
 */
import { existsSync, readFileSync, writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const here = dirname(fileURLToPath(import.meta.url));
const target = join(
  here,
  "..",
  "node_modules",
  "@remotion",
  "studio-server",
  "dist",
  "preview-server",
  "validate-same-origin.js"
);

const MARKER = "nexus-proxy-aware-origin";
const PATCHED_BLOCK = `    // [${MARKER}] Reverse-proxy-aware comparison. Trust the public host
    // supplied by the proxy (X-Forwarded-Host, then RFC 7239 Forwarded),
    // fall back to Host, and compare hostnames (plus explicit ports) rather
    // than scheme+host so an https preview proxy in front of this http studio
    // is not treated as cross-origin.
    const forwardedHeader = req.headers['forwarded'];
    const rfcForwardedHost =
        typeof forwardedHeader === 'string'
            ? (forwardedHeader.match(/(?:^|;|\\s)host=("?)([^";]+)\\1/i) || [])[2]
            : undefined;
    const xForwardedHost = req.headers['x-forwarded-host'];
    const forwardedHost =
        (typeof xForwardedHost === 'string' && xForwardedHost.split(',')[0].trim()) ||
        rfcForwardedHost;
    const effectiveHost = forwardedHost || host;
    const effectiveHostName = effectiveHost.split(':')[0];
    const effectiveHostPort = effectiveHost.includes(':')
        ? Number(effectiveHost.split(':')[1])
        : null;
    const originPort = originUrl.port ? Number(originUrl.port) : null;
    const portsMismatch =
        effectiveHostPort !== null &&
        ![null, 80, 443].includes(originPort) &&
        originPort !== effectiveHostPort;
    const behindTlsProxy =
        req.headers['x-forwarded-proto'] === 'https' ||
        (typeof forwardedHeader === 'string' && /proto=("?)https\\1/i.test(forwardedHeader));
    const hostIsPrivate =
        effectiveHostName === 'localhost' ||
        effectiveHostName === '127.0.0.1' ||
        effectiveHostName === '0.0.0.0' ||
        effectiveHostName === '::1' ||
        /^10\\.|^192\\.168\\.|^172\\.(1[6-9]|2\\d|3[01])\\./.test(effectiveHostName);
    const hostMatches = originUrl.hostname === effectiveHostName && !portsMismatch;
    const proxiedLoopback = behindTlsProxy && hostIsPrivate;
    if (!hostMatches && !proxiedLoopback) {
        throw new Error('Request from different origin not allowed');
    }`;

// Every upstream/previous block this script might encounter.
const REPLACEABLE = [
  `    if (originUrl.origin !== \`http://\${host}\`) {
        throw new Error('Request from different origin not allowed');
    }`,
];

if (!existsSync(target)) {
  console.log(`[${MARKER}] studio-server not found yet — skipping (run after npm install).`);
  process.exit(0);
}

let source = readFileSync(target, "utf8");

if (source.includes(MARKER)) {
  // Re-apply: strip any earlier revision of our block back to the upstream
  // shape so a single replacement rule stays the source of truth.
  const previous = source.match(
    new RegExp(`    // \\[${MARKER}\\][\\s\\S]*?throw new Error\\('Request from different origin not allowed'\\);\\n`)
  );
  if (previous) {
    source = source.replace(previous[0], REPLACEABLE[0] + "\n");
  }
}

if (!source.includes(REPLACEABLE[0])) {
  console.error(
    `[${MARKER}] expected upstream snippet not found in ${target}. ` +
      "A Remotion upgrade may have changed validate-same-origin.js — re-check this patch."
  );
  process.exit(1);
}

source = source.replace(REPLACEABLE[0], PATCHED_BLOCK);
writeFileSync(target, source);
console.log(`[${MARKER}] applied proxy-aware same-origin check to studio-server.`);
