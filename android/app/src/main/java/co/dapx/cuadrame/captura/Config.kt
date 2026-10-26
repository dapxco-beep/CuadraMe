package co.dapx.cuadrame.captura

import android.content.Context

/** Ajustes guardados en este teléfono: dirección del servidor y la clave de conexión de CuadraMe. */
object Config {
    const val SERVIDOR_POR_DEFECTO = "https://backend-production-aeab.up.railway.app"
    private const val PREFS = "cuadrame_captura"

    private fun prefs(ctx: Context) = ctx.getSharedPreferences(PREFS, Context.MODE_PRIVATE)

    fun servidor(ctx: Context): String =
        prefs(ctx).getString("servidor", SERVIDOR_POR_DEFECTO)!!.trim().trimEnd('/')

    fun clave(ctx: Context): String = prefs(ctx).getString("clave", "")!!.trim()

    fun tieneClave(ctx: Context) = clave(ctx).isNotEmpty()

    fun guardarClave(ctx: Context, clave: String) {
        prefs(ctx).edit().putString("clave", clave.trim()).apply()
    }

    fun get(ctx: Context, k: String, def: String = ""): String = prefs(ctx).getString(k, def) ?: def
    fun put(ctx: Context, k: String, v: String) = prefs(ctx).edit().putString(k, v).apply()
    fun getLong(ctx: Context, k: String, def: Long = 0L): Long = prefs(ctx).getLong(k, def)
    fun putLong(ctx: Context, k: String, v: Long) = prefs(ctx).edit().putLong(k, v).apply()
}
