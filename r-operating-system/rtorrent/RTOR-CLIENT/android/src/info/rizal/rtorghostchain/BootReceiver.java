package info.rizal.rtorghostchain;

import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;

/** Start-at-boot (and after an app update): brings the RTOR foreground service up with no tap. */
public class BootReceiver extends BroadcastReceiver {
    @Override public void onReceive(Context c, Intent i) {
        try { c.startForegroundService(new Intent(c, RtorService.class)); } catch (Exception ignored) {}
    }
}
