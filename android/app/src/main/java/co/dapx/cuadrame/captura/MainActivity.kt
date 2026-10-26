package co.dapx.cuadrame.captura

import android.content.Intent
import android.graphics.Color
import android.graphics.Typeface
import android.os.Bundle
import android.provider.Settings
import android.text.InputType
import android.view.View
import android.widget.Button
import android.widget.EditText
import android.widget.LinearLayout
import android.widget.ScrollView
import android.widget.TextView
import androidx.appcompat.app.AppCompatActivity
import androidx.core.app.NotificationManagerCompat
import org.json.JSONArray
import org.json.JSONObject
import kotlin.concurrent.thread

/** Pantalla única: pega la clave, da el acceso a notificaciones y prueba que todo llegue a CuadraMe. */
class MainActivity : AppCompatActivity() {

    private lateinit var campoClave: EditText
    private lateinit var estado: TextView
    private lateinit var resultado: TextView
    private lateinit var historial: TextView

    private val naranja = Color.parseColor("#B9461A")
    private val tinta = Color.parseColor("#201B14")
    private val suave = Color.parseColor("#6B6258")

    private fun dp(v: Int) = (v * resources.displayMetrics.density).toInt()

    private fun texto(t: String, tam: Float = 15f, color: Int = tinta, negrita: Boolean = false, abajo: Int = 8) =
        TextView(this).apply {
            text = t
            textSize = tam
            setTextColor(color)
            if (negrita) setTypeface(typeface, Typeface.BOLD)
            setPadding(0, 0, 0, dp(abajo))
        }

    private fun boton(t: String, relleno: Boolean = true, alPulsar: () -> Unit) = Button(this).apply {
        text = t
        isAllCaps = false
        textSize = 15f
        setTextColor(if (relleno) Color.WHITE else naranja)
        setBackgroundColor(if (relleno) naranja else Color.TRANSPARENT)
        minHeight = dp(48)
        setOnClickListener { alPulsar() }
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        val col = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(dp(20), dp(28), dp(20), dp(28))
        }
        col.addView(texto("CuadraMe Captura", 26f, negrita = true, abajo = 4))
        col.addView(
            texto(
                "Registra solo los pagos que haces con Google Wallet, Nequi, Nu y tus bancos: lee el aviso que te llega " +
                    "y lo manda a CuadraMe, donde lo confirmas con un toque. Solo lee las apps de pago de la lista; " +
                    "nunca tus chats, correos ni redes.",
                14f, suave, abajo = 18,
            ),
        )

        col.addView(texto("1. Tu clave de conexión", 17f, negrita = true, abajo = 2))
        col.addView(texto("En CuadraMe: Más → Registro automático → Conectar tu celular. Cópiala y pégala aquí.", 13f, suave))
        campoClave = EditText(this).apply {
            hint = "Clave de CuadraMe"
            inputType = InputType.TYPE_CLASS_TEXT or InputType.TYPE_TEXT_VARIATION_PASSWORD
            setSingleLine()
            setText(Config.clave(this@MainActivity))
        }
        col.addView(campoClave)
        col.addView(boton("Guardar clave") {
            Config.guardarClave(this, campoClave.text.toString())
            refrescar()
            resultado.text = "Clave guardada. Ahora prueba la conexión (paso 3)."
        })

        col.addView(texto("2. Acceso a notificaciones", 17f, negrita = true, abajo = 2).apply { setPadding(0, dp(22), 0, dp(2)) })
        col.addView(texto("Android te lleva a una lista: busca «CuadraMe Captura» y actívala. Es un permiso que solo tú puedes dar.", 13f, suave))
        col.addView(boton("Abrir ajustes de Android", relleno = false) {
            startActivity(Intent(Settings.ACTION_NOTIFICATION_LISTENER_SETTINGS))
        })

        col.addView(texto("3. Probar", 17f, negrita = true, abajo = 2).apply { setPadding(0, dp(22), 0, dp(2)) })
        col.addView(boton("Probar conexión") { probarConexion() })
        col.addView(boton("Enviar un pago de prueba", relleno = false) { enviarPrueba() })
        resultado = texto("", 14f, color = naranja)
        col.addView(resultado)

        estado = texto("", 14f).apply { setPadding(0, dp(18), 0, dp(8)) }
        col.addView(estado)
        col.addView(texto("Lo último que se envió", 15f, negrita = true, abajo = 4))
        historial = texto("", 13f, suave)
        col.addView(historial)

        setContentView(ScrollView(this).apply {
            setBackgroundColor(Color.parseColor("#F7F4EE"))
            addView(col)
        })
    }

    override fun onResume() {
        super.onResume()
        refrescar()
        thread {
            Apps.refrescar(this)
            Cola.reintentar(this)
        }
    }

    private fun accesoActivo() =
        NotificationManagerCompat.getEnabledListenerPackages(this).contains(packageName)

    private fun refrescar() {
        val ok = "✓"
        val no = "✗"
        estado.text = buildString {
            appendLine("${if (Config.tieneClave(this@MainActivity)) ok else no} Clave guardada")
            appendLine("${if (accesoActivo()) ok else no} Acceso a notificaciones ${if (accesoActivo()) "activo" else "sin activar"}")
            val p = Cola.pendientes(this@MainActivity)
            append("${if (p == 0) ok else "…"} Pendientes de enviar: $p")
        }
        val h = Cola.historial(this)
        historial.text = if (h.isEmpty()) "Aún nada. Cuando pagues con tu celular, aparecerá aquí." else h.joinToString("\n\n")
    }

    private fun probarConexion() {
        if (!Config.tieneClave(this)) {
            resultado.text = "Primero pega y guarda tu clave."
            return
        }
        resultado.text = "Probando…"
        thread {
            val r = Red.get(this, "/movimientos/cuentas-rapido")
            val msg = when {
                r.codigo == 200 -> {
                    val n = try { JSONArray(r.cuerpo).length() } catch (_: Exception) { 0 }
                    "Conectado ✓. CuadraMe ve $n ${if (n == 1) "cuenta" else "cuentas"} tuyas."
                }
                r.codigo == 401 -> "La clave no es válida. Genera una nueva en CuadraMe y pégala de nuevo."
                r.codigo == 0 -> "No hay conexión con el servidor. Revisa tu internet."
                else -> "El servidor respondió ${r.codigo}."
            }
            runOnUiThread { resultado.text = msg; refrescar() }
        }
    }

    /** Manda un pago inventado con el mismo camino de una notificación real. Queda «por confirmar» en CuadraMe. */
    private fun enviarPrueba() {
        if (!Config.tieneClave(this)) {
            resultado.text = "Primero pega y guarda tu clave."
            return
        }
        resultado.text = "Enviando…"
        thread {
            val cuerpo = JSONObject()
                .put("paquete", "com.nequi.MobileApp")
                .put("titulo", "Nequi")
                .put("texto", "Pagaste \$1.000 en PRUEBA CUADRAME.")
                .put("publicado_ms", System.currentTimeMillis())
            val r = Red.post(this, "/movimientos/rapido-notificacion", cuerpo.toString())
            val msg = when {
                r.codigo == 200 -> "Listo: busca «Prueba Cuadrame» por \$1.000 en CuadraMe (Por confirmar). Bórralo cuando lo veas."
                r.codigo == 401 -> "La clave no es válida."
                r.codigo == 0 -> "No hay conexión con el servidor."
                else -> "El servidor respondió ${r.codigo}."
            }
            runOnUiThread { resultado.text = msg; refrescar() }
        }
    }

    @Suppress("unused")
    private fun oculto(v: View) { v.visibility = View.GONE }
}
