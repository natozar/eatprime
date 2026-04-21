// EatPrime · Service Worker
// Estratégia: cache-first com versionamento.
// IMPORTANTE: incremente CACHE_VERSION toda vez que você publicar uma mudança,
// senão o usuário fica preso numa versão antiga.

const CACHE_VERSION = "eatprime-v1.0.3";
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

// FETCH — cache-first, com fallback pra rede e cache do que vier da rede
self.addEventListener("fetch", (event) => {
  const req = event.request;
  // Só GET
  if (req.method !== "GET") return;
  // Pula chamadas cross-origin (fontes Google, etc) — browser gerencia
  if (!req.url.startsWith(self.location.origin)) return;

  event.respondWith(
    caches.match(req).then((cached) => {
      if (cached) return cached;
      return fetch(req)
        .then((resp) => {
          // Guarda cópia no cache só se for resposta boa
          if (resp && resp.status === 200 && resp.type === "basic") {
            const clone = resp.clone();
            caches.open(CACHE_VERSION).then((cache) => cache.put(req, clone));
          }
          return resp;
        })
        .catch(() => {
          // Offline: se for navegação HTML, devolve a página de offline
          if (req.mode === "navigate") {
            return caches.match(OFFLINE_URL);
          }
          return cached;
        });
    })
  );
});
