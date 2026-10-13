// Offline support for the installed app. Bump VERSION when shell files change.
var VERSION="nbw-v1";
var SHELL=["./","index.html","sky.js","manifest.webmanifest","icons/icon-192.png","icons/icon-512.png","icons/icon-180.png"];
self.addEventListener("install",function(e){
  e.waitUntil(caches.open(VERSION).then(function(c){return c.addAll(SHELL)}).then(function(){return self.skipWaiting()}));
});
self.addEventListener("activate",function(e){
  e.waitUntil(caches.keys().then(function(keys){return Promise.all(keys.filter(function(k){return k!==VERSION}).map(function(k){return caches.delete(k)}))}).then(function(){return self.clients.claim()}));
});
function save(req,res){if(res&&res.ok){var copy=res.clone();caches.open(VERSION).then(function(c){c.put(req,copy)})}return res}
self.addEventListener("fetch",function(e){
  var req=e.request,url=new URL(req.url);
  if(req.method!=="GET")return;
  // Pages and event data: network first so updates show up, cache when offline.
  if(req.mode==="navigate"||url.pathname.endsWith("/events.json")){
    e.respondWith(fetch(req).then(function(r){return save(req,r)}).catch(function(){return caches.match(req,{ignoreSearch:true}).then(function(r){return r||caches.match("index.html")})}));
    return;
  }
  // Everything else (scripts, icons, fonts): cache first, refresh in the background.
  if(url.origin===location.origin||/fonts\.(googleapis|gstatic)\.com$/.test(url.hostname)){
    e.respondWith(caches.match(req).then(function(hit){
      var net=fetch(req).then(function(r){return save(req,r)}).catch(function(){return hit});
      return hit||net;
    }));
  }
});
