// EatPrime · Service Worker
// Estratégia: cache-first com versionamento.
// IMPORTANTE: incremente CACHE_VERSION toda vez que você publicar uma mudança,
// senão o usuário fica preso numa versão antiga.

const CACHE_VERSION = "eatprime-v1.5.2";
const OFFLINE_URL = "./offline.html";
const CORE_ASSETS = [
  "./",
  "./index.html",
  "./offline.html",
  "./404.html",
  "./manifest.json",
  "./restaurantes_dados.json",
  "./icons/icon-192.png",
  "./icons/icon-512.png",
  "./icons/favicon.svg",
  "./icons/logo.svg",
];

// INSTALL — faz pré-cache dos assets essenciais
self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(CACHE_VERSION).then((cache) => {
      return cache.addAll(CORE_ASSETS).catch(() => {
        // Se algum falhar (ex: foto ainda não existe), segue em frente
      });
    })
  );
  self.skipWaiting();
});

// MESSAGE — recebe pedido do cliente pra pular fila de espera
self.addEventListener("message", (event) => {
  if (event.data && event.data.type === "SKIP_WAITING") {
    self.skipWaiting();
  }
});

// ACTIVATE — limpa caches antigos
self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys().then((chaves) =>
      Promise.all(
        chaves
          .filter((k) => k !== CACHE_VERSION)
          .map((k) => caches.delete(k))
      )
    )
  );
  self.clients.claim();
});

// FETCH — estratégia híbrida:
//   - JSON (dados que mudam): network-first, fallback pro cache quando offline
//   - Resto (HTML/CSS/JS/imagens): cache-first, com update em background
self.addEventListener("fetch", (event) => {
  const req = event.request;
  if (req.method !== "GET") return;
  if (!req.url.startsWith(self.location.origin)) return;

  const url = new URL(req.url);
  const isJSON = url.pathname.endsWith(".json");

  if (isJSON) {
    // Network-first: busca sempre do servidor. Se offline, devolve último cache.
    event.respondWith(
      fetch(req)
        .then((resp) => {
          if (resp && resp.status === 200) {
            const clone = resp.clone();
            caches.open(CACHE_VERSION).then((cache) => cache.put(req, clone));
          }
          return resp;
        })
        .catch(() => caches.match(req))
    );
    return;
  }

  // Cache-first pro resto
  event.respondWith(
    caches.match(req).then((cached) => {
      if (cached) return cached;
      return fetch(req)
        .then((resp) => {
          if (resp && resp.status === 200 && resp.type === "basic") {
            const clone = resp.clone();
            caches.open(CACHE_VERSION).then((cache) => cache.put(req, clone));
          }
          return resp;
        })
        .catch(() => {
          if (req.mode === "navigate") {
            return caches.match(OFFLINE_URL);
          }
          return cached;
        });
    })
  );
});
