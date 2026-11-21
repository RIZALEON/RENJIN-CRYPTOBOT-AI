package info.rizal.rtorghostchain;

import android.content.Context;
import android.content.res.AssetManager;
import java.io.File;
import java.io.FileOutputStream;
import java.io.InputStream;
import java.io.OutputStream;
import java.net.HttpURLConnection;
import java.net.URL;

/**
 * Starts the bundled rtor-ghostchain server (same Go client as the Pixel / Ubuntu Touch build, 0.2.2):
 * UI on 127.0.0.1:4984 (loopback only), LAN peer port 4985 (peers in order Neo, Pixel, Moto), always-on seed + leech
 * of every library file at >= 1 KB/s each way measured from real byte counters, public RTRACKR download fallback,
 * and the RE-SEED panel that reads the live RGHOSTCHAIN. Only one instance ever holds 4984. No keys, no signing.
 */
final class RtorCore {
    static final String HOME = "http://127.0.0.1:4984/";
    static Process server;

    static synchronized void start(Context ctx) throws Exception {
        if (alive()) return;
        File pkg = new File(ctx.getFilesDir(), "pkg"), rzl = new File(pkg, "rzl"), data = new File(ctx.getFilesDir(), "data");
        rzl.mkdirs(); data.mkdirs();
        AssetManager am = ctx.getAssets();
        for (String n : am.list("rzl")) copy(am, "rzl/" + n, new File(rzl, n));
        File bin = new File(ctx.getApplicationInfo().nativeLibraryDir, "librtorghostchain.so");
        // SPACE-RID.json: app-specific external dir (adb push target) first, then internal data dir.
        File ext = ctx.getExternalFilesDir(null);
        File space = ext != null ? new File(ext, "SPACE-RID.json") : null;
        if (space == null || !space.exists()) space = new File(data, "SPACE-RID.json");
        // peers.json: app-specific external dir overrides the built-in list (Neo, Pixel, Moto)
        File peers = ext != null ? new File(ext, "peers.json") : null;
        if (peers != null && peers.exists()) copyFile(peers, new File(data, "peers.json"));
        ProcessBuilder pb = new ProcessBuilder(bin.getAbsolutePath(), "serve", "--pkg", pkg.getAbsolutePath(),
                "--data", data.getAbsolutePath(), "--addr", "127.0.0.1:4984", "--space", space.getAbsolutePath());
        pb.environment().put("SSL_CERT_DIR", "/system/etc/security/cacerts");
        pb.environment().put("RTOR_DEVICE", "rtor-android-" + android.os.Build.MODEL.replace(' ', '-'));
        pb.environment().put("RTOR_PEER_LISTEN", "0.0.0.0:4985");
        pb.redirectErrorStream(true);
        pb.redirectOutput(new File(data, "client.log"));
        server = pb.start();
        for (int i = 0; i < 50 && !alive(); i++) Thread.sleep(200);
    }

    static boolean alive() {
        try {
            HttpURLConnection c = (HttpURLConnection) new URL(HOME + "api/status").openConnection();
            c.setConnectTimeout(300); c.setReadTimeout(1500);
            int code = c.getResponseCode(); c.disconnect();
            return code == 200;
        } catch (Exception e) { return false; }
    }

    static void copy(AssetManager am, String from, File to) throws Exception {
        try (InputStream in = am.open(from)) { write(in, to); }
    }

    static void copyFile(File from, File to) throws Exception {
        try (InputStream in = new java.io.FileInputStream(from)) { write(in, to); }
    }

    static void write(InputStream in, File to) throws Exception {
        File tmp = new File(to.getPath() + ".tmp");
        try (OutputStream out = new FileOutputStream(tmp)) {
            byte[] buf = new byte[1 << 16]; int n;
            while ((n = in.read(buf)) > 0) out.write(buf, 0, n);
        }
        if (!tmp.renameTo(to)) throw new Exception("rename " + to);
    }
}
