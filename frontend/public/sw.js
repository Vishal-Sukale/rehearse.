// Minimal service worker: makes the app installable and keeps the app shell available offline.
// It NEVER caches API calls, so interview data is always live.
const CACHE = "rehearse-shell-v2";
const SHELL = ["/", "/manifest.webmanifest", "/icon.svg"];
// Files that are not content-hashed must be fetched fresh whenever you are online,
// or people keep running an old copy after an update (for example the Python test runner).
const NETWORK_FIRST = ["/pyrunner.js", "/manifest.webmanifest", "/icon.svg"];

self.addEventListener("install", (event) => {
  event.waitUntil(caches.open(CACHE).then((c) => c.addAll(SHELL)).then(() => self.skipWaiting()));
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys()
      .then((keys) => Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k))))
      .then(() => self.clients.claim())
  );
});

self.addEventListener("fetch", (event) => {
  const req = event.request;
  const url = new URL(req.url);
  if (req.method !== "GET" || url.origin !== self.location.origin || url.pathname.startsWith("/api/")) return;

  if (req.mode === "navigate" || NETWORK_FIRST.includes(url.pathname)) {   // network first, cached copy when offline
    event.respondWith(
      fetch(req)
        .then((res) => {
          if (res.ok) { const copy = res.clone(); caches.open(CACHE).then((c) => c.put(req, copy)); }
          return res;
        })
        .catch(() => caches.match(req).then((hit) => hit || caches.match("/")))
    );
    return;
  }
  event.respondWith(               // built assets are content-hashed, so cache-first is safe
    caches.match(req).then((hit) => hit || fetch(req).then((res) => {
      if (res.ok) { const copy = res.clone(); caches.open(CACHE).then((c) => c.put(req, copy)); }
      return res;
    }))
  );
});