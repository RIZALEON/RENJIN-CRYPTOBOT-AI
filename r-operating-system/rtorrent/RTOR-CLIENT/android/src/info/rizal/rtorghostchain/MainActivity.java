package info.rizal.rtorghostchain;

import android.app.Activity;
import android.content.Intent;
import android.database.Cursor;
import android.net.Uri;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.provider.OpenableColumns;
import android.webkit.ValueCallback;
import android.webkit.WebChromeClient;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import java.io.InputStream;
import java.io.OutputStream;
import java.net.HttpURLConnection;
import java.net.URL;
import java.net.URLEncoder;

/**
 * RTOR (Renjin Torrent) for Android: a WebView over the same local client the Linux build runs
 * (lib/<abi>/librtorghostchain.so = the static rtor-ghostchain server) on 127.0.0.1:4984.
 * Opens .rzl, crypto files (public JSON/PEM), .rtor, .torrent, .magnet and magnet: links; seeds and leeches one file at a time.
 * 0.2.2: server runs in RtorService (foreground, start-at-boot) with LAN peers and always-on seed/leech.
 * No JS bridge, no keys, no signing. Re-seed clears only when the sealed RGHOSTKEY block 6 is on the RGHOSTCHAIN.
 */
public class MainActivity extends Activity {
    static final String HOME = RtorCore.HOME;
    static final int PICK = 41;
    WebView web;
    ValueCallback<Uri[]> pickCb;
    final Handler ui = new Handler(Looper.getMainLooper());

    @Override protected void onCreate(Bundle b) {
        super.onCreate(b);
        web = new WebView(this);
        WebSettings s = web.getSettings();
        s.setJavaScriptEnabled(true);
        s.setDomStorageEnabled(true);
        s.setAllowFileAccess(false);
        s.setAllowContentAccess(false);
        web.setWebViewClient(new WebViewClient());
        web.setWebChromeClient(new WebChromeClient() {
            @Override public boolean onShowFileChooser(WebView v, ValueCallback<Uri[]> cb, FileChooserParams p) {
                if (pickCb != null) pickCb.onReceiveValue(null);
                pickCb = cb;
                Intent i = new Intent(Intent.ACTION_OPEN_DOCUMENT);
                i.addCategory(Intent.CATEGORY_OPENABLE);
                i.setType("*/*");
                i.putExtra(Intent.EXTRA_ALLOW_MULTIPLE, true);
                try { startActivityForResult(i, PICK); } catch (Exception e) { pickCb = null; return false; }
                return true;
            }
        });
        page("<body style='background:#0b0726;color:#39FF14;font-family:monospace;padding:24px'>R:&gt; starting RTOR…</body>");
        setContentView(web);
        final Intent first = getIntent();
        new Thread(() -> { boot(); handle(first); }).start();
    }

    @Override protected void onNewIntent(Intent i) {
        super.onNewIntent(i);
        setIntent(i);
        new Thread(() -> handle(i)).start();
    }

    @Override protected void onActivityResult(int req, int res, Intent data) {
        if (req == PICK && pickCb != null) {
            Uri[] r = null;
            if (res == RESULT_OK && data != null) {
                if (data.getClipData() != null) {
                    r = new Uri[data.getClipData().getItemCount()];
                    for (int k = 0; k < r.length; k++) r[k] = data.getClipData().getItemAt(k).getUri();
                } else if (data.getData() != null) r = new Uri[]{data.getData()};
            }
            pickCb.onReceiveValue(r);
            pickCb = null;
        }
    }

    void page(String html) { web.loadDataWithBaseURL(null, html, "text/html", "utf-8", null); }

    void boot() {
        try {
            if (android.os.Build.VERSION.SDK_INT >= 33 && checkSelfPermission("android.permission.POST_NOTIFICATIONS") != 0)
                ui.post(() -> requestPermissions(new String[]{"android.permission.POST_NOTIFICATIONS"}, 7));
            startForegroundService(new Intent(this, RtorService.class)); // always-on server + seed/leech, survives the UI
            RtorCore.start(this); // connect immediately (no-op if the service already has 4984)
        } catch (Exception e) {
            final String m = String.valueOf(e).replace("<", "&lt;");
            ui.post(() -> page("<body style='background:#0b0726;color:#ff5c7a;font-family:monospace;padding:24px'>RTOR client failed to start: " + m + "</body>"));
        }
    }

    void handle(Intent in) {
        String target = HOME;
        try {
            if (in != null) {
                String act = in.getAction();
                Uri u = null;
                if (Intent.ACTION_VIEW.equals(act)) u = in.getData();
                else if (Intent.ACTION_SEND.equals(act)) {
                    u = in.getParcelableExtra(Intent.EXTRA_STREAM);
                    String t = in.getStringExtra(Intent.EXTRA_TEXT);
                    if (u == null && t != null && t.trim().toLowerCase().startsWith("magnet:?")) target = HOME + "?magnet=" + URLEncoder.encode(t.trim(), "UTF-8");
                }
                if (u != null && "magnet".equalsIgnoreCase(u.getScheme())) {
                    target = HOME + "?magnet=" + URLEncoder.encode(u.toString(), "UTF-8");
                } else if (u != null) {
                    target = HOME + "?imported=" + URLEncoder.encode(importUri(u), "UTF-8");
                }
            }
        } catch (Exception e) {
            try { target = HOME + "?imported=" + URLEncoder.encode("open failed: " + e, "UTF-8"); } catch (Exception ignored) {}
        }
        final String t = target;
        ui.post(() -> web.loadUrl(t));
    }

    String importUri(Uri u) throws Exception {
        String name = "file";
        try (Cursor c = getContentResolver().query(u, new String[]{OpenableColumns.DISPLAY_NAME}, null, null, null)) {
            if (c != null && c.moveToFirst() && c.getString(0) != null) name = c.getString(0);
        } catch (Exception e) {
            if (u.getLastPathSegment() != null) name = u.getLastPathSegment();
        }
        HttpURLConnection c = (HttpURLConnection) new URL(HOME + "api/import").openConnection();
        c.setRequestMethod("POST");
        c.setDoOutput(true);
        c.setChunkedStreamingMode(1 << 16);
        c.setRequestProperty("X-Filename", URLEncoder.encode(name, "UTF-8"));
        c.setRequestProperty("X-Source", "android-open");
        try (InputStream in = getContentResolver().openInputStream(u); OutputStream out = c.getOutputStream()) {
            byte[] buf = new byte[1 << 16]; int n;
            while ((n = in.read(buf)) > 0) out.write(buf, 0, n);
        }
        int code = c.getResponseCode();
        InputStream rs = code < 400 ? c.getInputStream() : c.getErrorStream();
        StringBuilder sb = new StringBuilder();
        if (rs != null) { byte[] buf = new byte[4096]; int n; while ((n = rs.read(buf)) > 0) sb.append(new String(buf, 0, n, "UTF-8")); rs.close(); }
        c.disconnect();
        String body = sb.toString();
        if (code == 200) return "OK  opened " + name + " into the RTOR library";
        int i = body.indexOf("\"refused\"");
        return "REFUSED  " + name + (i >= 0 ? body.substring(i).replaceAll("[{}\"\\n]", " ").trim() : " (http " + code + ")");
    }

    @Override public void onBackPressed() { if (web.canGoBack()) web.goBack(); else super.onBackPressed(); }
}
