package co.dapx.cuadrame.captura

import android.content.Context
import java.net.HttpURLConnection
import java.net.URL

/** Resultado de una llamada al servidor. `codigo` = 0 cuando ni siquiera hubo conexión. */
data class Respuesta(val codigo: Int, val cuerpo: String)

/** HTTP mínimo con la librería estándar de Android: sin librerías de terceros. */
object Red {
    private const val TIMEOUT_MS = 15_000

    fun get(ctx: Context, ruta: String): Respuesta = llamar(ctx, "GET", ruta, null)

    fun post(ctx: Context, ruta: String, json: String): Respuesta = llamar(ctx, "POST", ruta, json)

    private fun llamar(ctx: Context, metodo: String, ruta: String, json: String?): Respuesta {
        return try {
            val c = URL(Config.servidor(ctx) + ruta).openConnection() as HttpURLConnection
            c.requestMethod = metodo
            c.connectTimeout = TIMEOUT_MS
            c.readTimeout = TIMEOUT_MS
            c.setRequestProperty("X-Api-Key", Config.clave(ctx))
            c.setRequestProperty("Accept", "application/json")
            if (json != null) {
                c.doOutput = true
                c.setRequestProperty("Content-Type", "application/json; charset=utf-8")
                c.outputStream.use { it.write(json.toByteArray(Charsets.UTF_8)) }
            }
            val codigo = c.responseCode
            val flujo = if (codigo in 200..299) c.inputStream else c.errorStream
            val cuerpo = flujo?.bufferedReader(Charsets.UTF_8)?.use { it.readText() }.orEmpty()
            c.disconnect()
            Respuesta(codigo, cuerpo)
        } catch (e: Exception) {
            Respuesta(0, e.javaClass.simpleName)
        }
    }
}
