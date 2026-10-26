package co.dapx.cuadrame.captura

import android.app.Notification
import android.service.notification.NotificationListenerService
import android.service.notification.StatusBarNotification
import org.json.JSONObject

/**
 * Lee las notificaciones de las apps de pago (Wallet, Nequi, bancos) y las manda a CuadraMe.
 * Solo se activa cuando le das «Acceso a notificaciones» a esta app en los ajustes de Android.
 */
class NotificacionService : NotificationListenerService() {

    override fun onNotificationPosted(sbn: StatusBarNotification) {
        val ctx = applicationContext
        if (sbn.packageName == ctx.packageName) return // nunca las propias
        if (!Config.tieneClave(ctx)) return
        if (!Apps.permitida(ctx, sbn.packageName)) return // cualquier otra app: ni se lee

        val n = sbn.notification ?: return
        if (n.flags and Notification.FLAG_GROUP_SUMMARY != 0) return // el resumen de un grupo repite las notificaciones
        val extras = n.extras ?: return
        val titulo = extras.getCharSequence(Notification.EXTRA_TITLE)?.toString().orEmpty()
        val texto = (extras.getCharSequence(Notification.EXTRA_BIG_TEXT) ?: extras.getCharSequence(Notification.EXTRA_TEXT))
            ?.toString().orEmpty()
        if (titulo.isBlank() && texto.isBlank()) return

        Cola.enviar(
            ctx,
            JSONObject()
                .put("paquete", sbn.packageName)
                .put("titulo", titulo.take(300))
                .put("texto", texto.take(2000))
                .put("publicado_ms", sbn.postTime),
        )
    }
}
