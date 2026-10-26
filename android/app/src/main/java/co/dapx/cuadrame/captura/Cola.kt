package co.dapx.cuadrame.captura

import android.content.Context
import org.json.JSONArray
import org.json.JSONObject
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale
import java.util.concurrent.Executors

/**
 * Envía cada notificación al servidor y, si no hay internet, la guarda para reintentar.
 * El servidor ignora lo que no es un movimiento y NO duplica una notificación repetida, así que reintentar es seguro.
 */
object Cola {
    private val hilo = Executors.newSingleThreadExecutor()
    private const val ARCHIVO = "cola.json"
    private const val MAX_PENDIENTES = 100
    private const val MAX_HISTORIAL = 20
    private const val CLAVE_HISTORIAL = "historial"

    fun enviar(ctx: Context, notificacion: JSONObject) {
        hilo.execute {
            val app = ctx.applicationContext
            Apps.refrescar(app)
            val pendientes = leer(app)
            pendientes.put(notificacion)
            vaciar(app, pendientes)
        }
    }

    /** Reintenta lo pendiente (al abrir la app o con cada notificación nueva). */
    fun reintentar(ctx: Context) {
        hilo.execute { vaciar(ctx.applicationContext, leer(ctx.applicationContext)) }
    }

    private fun vaciar(ctx: Context, lista: JSONArray) {
        val quedan = JSONArray()
        for (i in 0 until lista.length()) {
            val n = lista.getJSONObject(i)
            val r = Red.post(ctx, "/movimientos/rapido-notificacion", n.toString())
            when {
                r.codigo in 200..299 -> anotar(ctx, n, resumen(r.cuerpo))
                r.codigo == 0 || r.codigo >= 500 || r.codigo == 429 -> if (quedan.length() < MAX_PENDIENTES) quedan.put(n)
                r.codigo == 401 -> {
                    anotar(ctx, n, "Clave rechazada: revisa la clave en esta app")
                    // no se reintenta con una clave mala; la persona debe corregirla
                }
                else -> anotar(ctx, n, "El servidor respondió ${r.codigo}")
            }
        }
        guardar(ctx, quedan)
    }

    private fun resumen(cuerpo: String): String = try {
        val j = JSONObject(cuerpo)
        when {
            j.optBoolean("registrado") -> "Registrado: " + j.optString("mensaje").take(90)
            j.optBoolean("duplicado") -> "Ya estaba registrado"
            else -> "Ignorada (no era un movimiento)"
        }
    } catch (_: Exception) {
        "Enviada"
    }

    // ── archivos y registro de lo último enviado (para mostrarlo en la pantalla) ──
    private fun leer(ctx: Context): JSONArray = try {
        val f = ctx.getFileStreamPath(ARCHIVO)
        if (f.exists()) JSONArray(f.readText()) else JSONArray()
    } catch (_: Exception) {
        JSONArray()
    }

    private fun guardar(ctx: Context, lista: JSONArray) {
        ctx.openFileOutput(ARCHIVO, Context.MODE_PRIVATE).use { it.write(lista.toString().toByteArray()) }
    }

    fun pendientes(ctx: Context): Int = leer(ctx).length()

    private fun anotar(ctx: Context, n: JSONObject, estado: String) {
        val hora = SimpleDateFormat("d MMM HH:mm", Locale("es", "CO")).format(Date())
        val linea = "$hora · ${n.optString("paquete").substringAfterLast('.')} · $estado"
        val previo = Config.get(ctx, CLAVE_HISTORIAL).split("\n").filter { it.isNotBlank() }
        Config.put(ctx, CLAVE_HISTORIAL, (listOf(linea) + previo).take(MAX_HISTORIAL).joinToString("\n"))
    }

    fun historial(ctx: Context): List<String> = Config.get(ctx, CLAVE_HISTORIAL).split("\n").filter { it.isNotBlank() }
}
