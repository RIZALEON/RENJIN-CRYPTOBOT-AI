import QtQuick 2.12
import QtQuick.Window 2.2
import Morph.Web 0.1
Window {
  id: win; visible: true; title: "RTOR"; color: "#0b0a1f"; width: 720; height: 1280
  property string base: "http://127.0.0.1:4984"
  WebView {
    id: web; anchors.fill: parent; url: "about:blank"
    Component.onCompleted: retry.start()
  }
  Text {
    anchors.centerIn: parent; visible: web.url == "about:blank"
    color: "#39FF14"; font.family: "monospace"; font.pixelSize: 28
    text: "R:> RTOR GHOSTCHAIN\nstarting on 127.0.0.1:4984..."
    horizontalAlignment: Text.AlignHCenter
  }
  // the bundled Go client may still be starting: poll /api/status, then open the dashboard
  Timer { id: retry; interval: 500; repeat: true; onTriggered: {
      var x = new XMLHttpRequest(); x.open("GET", win.base + "/api/status");
      x.onreadystatechange = function(){
        if (x.readyState === 4 && x.status === 200 && retry.running) { retry.stop(); web.url = win.base + "/"; }
      };
      x.send();
  } }
  // Content Hub (open .rzl / crypto / RTOR / magnet files) and magnet: links.
  // Loaded separately so a missing Lomiri module never blocks the main view.
  Loader { id: hooks; source: "Hooks.qml"
    onStatusChanged: if (status === Loader.Error && source.toString().indexOf("Legacy") < 0) source = "HooksLegacy.qml" }
}
