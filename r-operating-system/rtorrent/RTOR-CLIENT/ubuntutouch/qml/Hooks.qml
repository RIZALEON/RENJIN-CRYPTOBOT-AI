import QtQuick 2.12
import Lomiri.Content 1.3
import Lomiri.Components 1.3
Item {
  function post(path, obj, done) {
    var x = new XMLHttpRequest(); x.open("POST", "http://127.0.0.1:4984" + path);
    x.setRequestHeader("Content-Type", "application/json");
    x.onreadystatechange = function(){ if (x.readyState === 4 && done) done(); };
    x.send(JSON.stringify(obj));
  }
  Connections { target: ContentHub
    onImportRequested: {
      var t = transfer, left = t.items.length;
      if (left === 0) { t.finalize(); return; }
      for (var i = 0; i < t.items.length; i++) {
        var u = String(t.items[i].url);
        if (u.indexOf("magnet:") === 0) post("/api/pending-open", {url: u}, function(){ if (--left === 0) t.finalize(); });
        else post("/api/import-local", {path: u}, function(){ if (--left === 0) t.finalize(); });
      }
    } }
  Connections { target: UriHandler
    onOpened: { for (var i = 0; i < uris.length; i++) post("/api/pending-open", {url: uris[i]}); } }
}
