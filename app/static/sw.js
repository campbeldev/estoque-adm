/* Service worker do PWA — mantém os arquivos estáticos do sistema em cache.
 * Quando um arquivo estático mudar, aumente o número em CACHE para os
 * navegadores baixarem a versão nova.
 */
var CACHE = "estoque-v7";

var ESTATICOS = [
  "/static/vendor/bootstrap.min.css",
  "/static/vendor/bootstrap.bundle.min.js",
  "/static/css/app.css",
  "/static/js/autocomplete.js",
  "/static/img/logo.png",
  "/static/img/campbel2.png",
  "/static/img/favicon.png",
  "/static/img/icon-192.png",
  "/static/img/icon-512.png",
  "/static/manifest.webmanifest",
];

self.addEventListener("install", function (evento) {
  evento.waitUntil(
    caches
      .open(CACHE)
      .then(function (cache) {
        return cache.addAll(ESTATICOS);
      })
      .then(function () {
        return self.skipWaiting();
      })
  );
});

self.addEventListener("activate", function (evento) {
  evento.waitUntil(
    caches
      .keys()
      .then(function (chaves) {
        return Promise.all(
          chaves
            .filter(function (chave) {
              return chave !== CACHE;
            })
            .map(function (chave) {
              return caches.delete(chave);
            })
        );
      })
      .then(function () {
        return self.clients.claim();
      })
  );
});

self.addEventListener("fetch", function (evento) {
  var url = new URL(evento.request.url);
  if (evento.request.method !== "GET" || url.origin !== self.location.origin) {
    return;
  }

  if (url.pathname.startsWith("/static/")) {
    // Arquivos estáticos: cache primeiro (o sistema abre até sem servidor)
    evento.respondWith(
      caches.match(evento.request).then(function (resposta) {
        return (
          resposta ||
          fetch(evento.request).then(function (nova) {
            var copia = nova.clone();
            caches.open(CACHE).then(function (cache) {
              cache.put(evento.request, copia);
            });
            return nova;
          })
        );
      })
    );
  } else {
    // Páginas: rede primeiro (dados sempre atualizados); sem rede, usa cache
    evento.respondWith(
      fetch(evento.request).catch(function () {
        return caches.match(evento.request).then(function (resposta) {
          return resposta || caches.match("/");
        });
      })
    );
  }
});
