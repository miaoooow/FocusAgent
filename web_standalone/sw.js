const CACHE_NAME = "focus-web-4.2.0";
const ASSETS = [
  "./",
  "./index.html",
  "./styles.css",
  "./app.js",
  "./manifest.webmanifest",
  "./media/relax.png",
  "./media/focus.png",
  "./media/confused.png",
  "./media/happy.png",
  "./media/sounds/The Nature Sounds SocietyJapan - 雨落森林.ogg",
  "./media/sounds/The Nature Sounds SocietyJapan - 林间溪流.ogg",
  "./media/sounds/Echoes of Nature - 卵石海岸.ogg",
  "./media/sounds/The Nature Sounds SocietyJapan - 溪流与鸟鸣.ogg",
];

self.addEventListener("install", (event) => {
  event.waitUntil(caches.open(CACHE_NAME).then((cache) => cache.addAll(ASSETS)));
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(keys.filter((key) => key !== CACHE_NAME).map((key) => caches.delete(key)))
    )
  );
  self.clients.claim();
});

self.addEventListener("fetch", (event) => {
  if (event.request.method !== "GET") return;
  const requestUrl = new URL(event.request.url);
  const shouldRefresh =
    event.request.mode === "navigate" ||
    requestUrl.pathname.endsWith("/app.js") ||
    requestUrl.pathname.endsWith("/styles.css") ||
    requestUrl.pathname.endsWith("/manifest.webmanifest");
  if (shouldRefresh) {
    const fallbackAsset = event.request.mode === "navigate"
      ? "./index.html"
      : requestUrl.pathname.endsWith("/app.js")
        ? "./app.js"
        : requestUrl.pathname.endsWith("/styles.css")
          ? "./styles.css"
          : "./manifest.webmanifest";
    event.respondWith(
      fetch(event.request)
        .then((response) => {
          const copy = response.clone();
          caches.open(CACHE_NAME).then((cache) => cache.put(event.request, copy));
          return response;
        })
        .catch(() => caches.match(event.request).then((cached) => cached || caches.match(fallbackAsset)))
    );
    return;
  }
  event.respondWith(
    caches.match(event.request).then((cached) =>
      cached || fetch(event.request).then((response) => {
        const copy = response.clone();
        caches.open(CACHE_NAME).then((cache) => cache.put(event.request, copy));
        return response;
      })
    )
  );
});
