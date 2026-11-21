package info.rizal.rtorghostchain;

import android.app.Notification;
import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.app.PendingIntent;
import android.app.Service;
import android.content.Intent;
import android.content.pm.ServiceInfo;
import android.os.Build;
import android.os.IBinder;
import android.os.PowerManager;

/** Foreground service: keeps the RTOR server (and its always-on seed/leech) running, restarts it if it ever exits. */
public class RtorService extends Service {
    static final String CH = "rtor";
    volatile boolean run = true;
    PowerManager.WakeLock wl;

    @Override public void onCreate() {
        super.onCreate();
        NotificationManager nm = getSystemService(NotificationManager.class);
        nm.createNotificationChannel(new NotificationChannel(CH, "RTOR seed / leech", NotificationManager.IMPORTANCE_LOW));
        PendingIntent pi = PendingIntent.getActivity(this, 0, new Intent(this, MainActivity.class), PendingIntent.FLAG_IMMUTABLE);
        Notification n = new Notification.Builder(this, CH)
                .setSmallIcon(android.R.drawable.stat_sys_download)
                .setContentTitle("RTOR GHOSTCHAIN")
                .setContentText("Always-on seed + leech (>= 1 KB/s each way) · peers Neo, Pixel, Moto")
                .setOngoing(true).setContentIntent(pi).build();
        if (Build.VERSION.SDK_INT >= 34) startForeground(1, n, ServiceInfo.FOREGROUND_SERVICE_TYPE_SPECIAL_USE);
        else startForeground(1, n);
        wl = ((PowerManager) getSystemService(POWER_SERVICE)).newWakeLock(PowerManager.PARTIAL_WAKE_LOCK, "rtor:seedleech");
        wl.setReferenceCounted(false);
        wl.acquire();
        new Thread(() -> {
            while (run) {
                try { RtorCore.start(this); } catch (Exception ignored) {}
                try { Thread.sleep(15000); } catch (InterruptedException e) { return; }
            }
        }, "rtor-watchdog").start();
    }

    @Override public int onStartCommand(Intent i, int flags, int id) { return START_STICKY; }

    @Override public void onDestroy() {
        run = false;
        if (wl != null && wl.isHeld()) wl.release();
        super.onDestroy();
    }

    @Override public IBinder onBind(Intent i) { return null; }
}
