/* Service worker mínimo — deixa o site instalável (PWA) e cacheia a shell.
 * Só intercepta requisições do próprio site; vídeo/TMDB/busca (cross-origin)
 * passam direto pela rede.
 */
const CACHE = "ponyflix-v1";
const SHELL = [
  "./", "./index.html", "./style.css", "./app.js", "./episodios.js",
  "./animes.html", "./animes.js", "./manifest.json",
  "./assets/icon-192.png", "./assets/icon-512.png",
];

self.addEventListener("install", (e) => {
  e.waitUntil(
    caches.open(CACHE).then((c) => c.addAll(SHELL)).then(() => self.skipWaiting())
  );
});

self.addEventListener("activate", (e) => {
  e.waitUntil(
    caches.keys()
      .then((ks) => Promise.all(ks.filter((k) => k !== CACHE).map((k) => caches.delete(k))))
      .then(() => self.clients.claim())
  );
});

self.addEventListener("fetch", (e) => {
  const url = new URL(e.request.url);
  if (e.request.method !== "GET" || url.origin !== location.origin) return; // deixa passar
  e.respondWith(
    caches.match(e.request).then((hit) =>
      hit || fetch(e.request).then((res) => {
        const copy = res.clone();
        caches.open(CACHE).then((c) => c.put(e.request, copy));
        return res;
      })
    )
  );
});
