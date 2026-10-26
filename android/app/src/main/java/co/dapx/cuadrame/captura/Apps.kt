package co.dapx.cuadrame.captura

import android.content.Context
import org.json.JSONObject

/**
 * Las apps cuyas notificaciones se leen. La lista oficial vive en el servidor (así se agrega un banco sin reinstalar);
 * aquí hay una copia de respaldo por si todavía no hubo conexión. Las notificaciones de cualquier otra app
 * (chats, correos, redes) NUNCA se leen ni se envían.
 */
object Apps {
    private val RESPALDO = setOf(
        "com.google.android.apps.walletnfcrel",
        "com.google.android.apps.nbu.paisa.user",
        "com.nequi.MobileApp",
        "com.nu.production",
        "co.com.nu.android",
        "com.todo1.mobile",
        "com.bancolombia.alamano",
        "com.davivienda.daviplataapp",
        "com.davivienda.mobile",
    )
    private const val CLAVE_LISTA = "apps_lista"
    private const val CLAVE_FECHA = "apps_fecha"
    private const val UN_DIA_MS = 24L * 60 * 60 * 1000

    fun permitida(ctx: Context, paquete: String): Boolean = paquetes(ctx).contains(paquete)

    fun paquetes(ctx: Context): Set<String> {
        val guardada = Config.get(ctx, CLAVE_LISTA)
        return if (guardada.isBlank()) RESPALDO else guardada.split(",").filter { it.isNotBlank() }.toSet()
    }

    /** Pide la lista al servidor como máximo una vez al día (o cuando `forzar`). Llamar desde un hilo de fondo. */
    fun refrescar(ctx: Context, forzar: Boolean = false) {
        val ahora = System.currentTimeMillis()
        if (!forzar && ahora - Config.getLong(ctx, CLAVE_FECHA) < UN_DIA_MS) return
        val r = Red.get(ctx, "/movimientos/notificaciones-apps")
        if (r.codigo != 200) return
        try {
            val arr = JSONObject(r.cuerpo).getJSONArray("paquetes")
            val lista = (0 until arr.length()).map { arr.getJSONObject(it).getString("paquete") }
            if (lista.isNotEmpty()) {
                Config.put(ctx, CLAVE_LISTA, lista.joinToString(","))
                Config.putLong(ctx, CLAVE_FECHA, ahora)
            }
        } catch (_: Exception) {
            // si la respuesta no se entiende, se sigue con la lista que ya había
        }
    }
}
