/* 玄機閣·量宅 Service Worker：装好后离线可用（罗盘需在线外的传感器，不受影响） */
const CACHE = "xuanjige-v2";
const ASSETS = ["./", "./index.html", "../fengshui.js", "./xingsha.js", "./icon.svg",
                "./ar.html", "./vendor/three.min.js",
                "./vendor/tf.min.js", "./vendor/coco-ssd.min.js"];

self.addEventListener("install", e => {
  e.waitUntil(caches.open(CACHE).then(c => c.addAll(ASSETS)).then(() => self.skipWaiting()));
});
self.addEventListener("activate", e => {
  e.waitUntil(
    caches.keys().then(keys => Promise.all(keys.filter(k => k !== CACHE).map(k => caches.delete(k))))
      .then(() => self.clients.claim())
  );
});
self.addEventListener("fetch", e => {
  e.respondWith(
    caches.match(e.request).then(hit => hit ||
      fetch(e.request).then(res => {
        const copy = res.clone();
        caches.open(CACHE).then(c => c.put(e.request, copy));
        return res;
      }).catch(() => caches.match("./index.html"))
    )
  );
});
