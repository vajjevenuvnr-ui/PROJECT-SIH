// Kshetra farmer page service worker (scope /f/).
// 1) Offline: network first; when offline, serve the last saved copy of the page, its assets and data.
// 2) Extreme-weather alerts: show Web Push notifications; tapping opens the SOS view.
const CACHE = "pc-farmer-v2";

self.addEventListener("install", () => self.skipWaiting());
self.addEventListener("activate", (event) =>
  event.waitUntil(
    caches
      .keys()
      .then((keys) => Promise.all(keys.filter((k) => k.startsWith("pc-farmer-") && k !== CACHE).map((k) => caches.delete(k))))
      .then(() => self.clients.claim()),
  ),
);

self.addEventListener("fetch", (event) => {
  const req = event.request;
  if (req.method !== "GET") return;
  const url = new URL(req.url);
  if (url.origin !== self.location.origin) return;
  if (url.pathname.startsWith("/_next/webpack-hmr") || url.pathname.includes("hot-update")) return;

  const cacheable =
    (req.mode === "navigate" && url.pathname.startsWith("/f/")) ||
    url.pathname.startsWith("/api/public/") ||
    url.pathname.startsWith("/_next/static/") ||
    url.pathname.startsWith("/brand/") ||
    url.pathname.endsWith("manifest.webmanifest");
  if (!cacheable) return;

  event.respondWith(
    fetch(req)
      .then((res) => {
        if (res.ok) {
          const copy = res.clone();
          caches.open(CACHE).then((c) => c.put(req, copy));
        }
        return res;
      })
      .catch(() => caches.match(req, { ignoreVary: true }).then((hit) => hit || Response.error())),
  );
});

self.addEventListener("push", (event) => {
  let d = {};
  try {
    d = event.data ? event.data.json() : {};
  } catch {
    d = { title: "Kshetra", body: event.data ? event.data.text() : "" };
  }
  event.waitUntil(
    self.registration.showNotification(d.title || "Kshetra", {
      body: d.body || "",
      tag: d.tag || "pc-alert",
      renotify: true,
      requireInteraction: d.level === "orange" || d.level === "red",
      vibrate: [500, 200, 500, 200, 1000],
      icon: "/brand/icon-192.png",
      badge: "/brand/icon-192.png",
      lang: d.lang || "te",
      data: { url: d.url || "/f/" },
    }),
  );
});

self.addEventListener("notificationclick", (event) => {
  event.notification.close();
  const target = new URL(event.notification.data?.url || "/f/", self.location.origin).href;
  event.waitUntil(
    self.clients.matchAll({ type: "window", includeUncontrolled: true }).then((list) => {
      for (const c of list) {
        if (c.url.split("?")[0] === target.split("?")[0] && "focus" in c) {
          c.navigate(target);
          return c.focus();
        }
      }
      return self.clients.openWindow(target);
    }),
  );
});
