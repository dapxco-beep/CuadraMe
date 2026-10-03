import { useNavigate } from 'react-router-dom'
import { ArrowLeft } from 'lucide-react'

export default function TerminosCondiciones() {
  const navigate = useNavigate()

  return (
    <div className="flex-1 overflow-y-auto pb-10">
      <header className="px-6 pt-14 pb-2 flex items-center gap-3">
        <button onClick={() => navigate(-1)} className="w-9 h-9 flex items-center justify-center -ml-2" aria-label="Volver">
          <ArrowLeft size={20} />
        </button>
        <h1 className="text-xl font-bold">Términos y Condiciones</h1>
      </header>

      <div className="px-6 mt-4 text-sm leading-relaxed text-ink space-y-5">
        <p className="text-xs text-ink-soft">Versión 1.1 (borrador) · Última actualización: 3 de octubre de 2026</p>

        <section>
          <h2 className="font-semibold mb-1.5">1. Quiénes somos</h2>
          <p>
            CuadraMe es un producto desarrollado y operado por DAPX (en adelante, "DAPX", "nosotros"),
            actualmente constituido como persona natural en Colombia en proceso de formalización
            empresarial. Mientras se completa el registro de razón social y NIT ante Cámara de Comercio,
            DAPX opera bajo este nombre comercial. Contacto: dapxco@gmail.com.
          </p>
        </section>

        <section>
          <h2 className="font-semibold mb-1.5">2. Qué es CuadraMe</h2>
          <p>
            CuadraMe es una aplicación de finanzas personales que permite registrar, organizar y analizar
            tus movimientos financieros (ingresos, gastos, presupuestos, metas de ahorro, deudas). CuadraMe
            no es una entidad financiera, no está vigilada por la Superintendencia Financiera de Colombia,
            no custodia dinero, no realiza pagos ni transferencias, y no otorga créditos. Es exclusivamente
            una herramienta de organización y visualización de información que tú mismo ingresas o
            autorizas importar desde tus propias fuentes (correo, extractos en PDF).
          </p>
        </section>

        <section>
          <h2 className="font-semibold mb-1.5">3. Aceptación</h2>
          <p>
            Al crear una cuenta en CuadraMe aceptas estos Términos y Condiciones, la Política de
            Privacidad y la Autorización de Tratamiento de Datos Personales. Si no estás de acuerdo, no
            debes usar la aplicación.
          </p>
        </section>

        <section>
          <h2 className="font-semibold mb-1.5">4. Naturaleza de la información que registras</h2>
          <p>
            Toda la información financiera dentro de CuadraMe (saldos, movimientos, categorías, metas)
            es ingresada voluntariamente por ti o extraída automáticamente de fuentes que tú
            autorizas expresamente (tu cuenta de Gmail bajo el alcance de solo lectura, o extractos
            en PDF que tú subes). CuadraMe no se conecta directamente a bancos ni obtiene información
            financiera sin tu autorización explícita.
          </p>
          <p className="mt-2">
            Eres responsable de la exactitud de la información que registras manualmente. CuadraMe
            realiza sugerencias automáticas de categorización basadas en reglas y patrones de texto, y
            estas sugerencias pueden ser incorrectas — siempre puedes revisarlas y corregirlas.
          </p>
        </section>

        <section>
          <h2 className="font-semibold mb-1.5">5. Cuentas compartidas</h2>
          <p>
            CuadraMe permite compartir el acceso a una cuenta con otra persona (ej. pareja o familia).
            Al compartir una cuenta, la otra persona podrá ver y, según el rol otorgado, editar los
            movimientos de esa cuenta. Eres responsable de a quién le otorgas acceso y de revocarlo
            cuando ya no corresponda.
          </p>
        </section>

        <section>
          <h2 className="font-semibold mb-1.5">6. Automatización por terceros (Atajos, Tasker, Siri)</h2>
          <p>
            CuadraMe ofrece una clave personal (API key) para que, si tú lo decides, conectes
            aplicaciones de automatización de terceros (como Atajos de iOS o Tasker en Android) para
            registrar movimientos automáticamente. Esta clave es tu responsabilidad: no debes
            compartirla, y cualquier uso indebido derivado de su divulgación es tu responsabilidad. Puedes
            regenerarla en cualquier momento desde tu Perfil.
          </p>
        </section>

        <section>
          <h2 className="font-semibold mb-1.5">7. Planes y pagos</h2>
          <p>
            Actualmente todas las funciones de CuadraMe están disponibles sin costo. Si en el futuro se
            introduce un plan de pago, se te informará con anticipación y de forma clara antes de
            cualquier cobro, y estos Términos se actualizarán en consecuencia.
          </p>
        </section>

        <section>
          <h2 className="font-semibold mb-1.5">Funciones nuevas y su alcance (octubre de 2026)</h2>
          <p>
            Importación de archivos, lectura de correos y extractos, fotos de facturas y asistente de IA son ayudas que proponen información: la categoría, el monto o la respuesta pueden contener errores. Tú revisas y confirmas antes de guardar, y eres responsable de la información que registras.
          </p>
          <p>
            Tarjetas de crédito y transferencias: para los reportes, el pago de una tarjeta y los traslados entre tus propias cuentas no se cuentan como gasto ni ingreso, para no duplicar las compras ya registradas. Los saldos de tus cuentas sí reflejan todos los movimientos.
          </p>
          <p>
            Impuestos: el contador de 4x1000 y la marca de gastos posiblemente deducibles son estimaciones informativas. CuadraMe no presta asesoría tributaria, no garantiza que un gasto sea deducible ni calcula tu impuesto de renta; confirma con un contador y con la DIAN.
          </p>
          <p>
            Gastos compartidos: al registrar contactos de terceros declaras que tienes derecho a hacerlo para dividir gastos. Los saldos entre personas son un registro de apoyo; CuadraMe no cobra ni transfiere dinero.
          </p>
          <p>
            Cierre de mes y patrimonio: son resúmenes automáticos con base en lo que registraste; no son recomendaciones de inversión.
          </p>
          <p>
            Todas las funciones son hoy gratuitas; si esto cambia, te lo informaremos antes.
          </p>
        </section>

        <section>
          <h2 className="font-semibold mb-1.5">8. Limitación de responsabilidad</h2>
          <p>
            CuadraMe se entrega "tal cual" (as is). No garantizamos que la categorización automática,
            las proyecciones de flujo de caja, el cálculo de "salud financiera" u otras funciones de
            análisis sean exactos o adecuados para tomar decisiones financieras sin tu propio criterio.
            CuadraMe no sustituye asesoría financiera profesional. DAPX no será responsable por
            decisiones financieras tomadas con base en la información o sugerencias de la aplicación,
            ni por pérdidas derivadas de errores de registro, fallas técnicas, o interrupciones del
            servicio.
          </p>
        </section>

        <section>
          <h2 className="font-semibold mb-1.5">9. Disponibilidad del servicio</h2>
          <p>
            CuadraMe se ofrece en fase de desarrollo activo. Pueden ocurrir interrupciones,
            mantenimientos o cambios en las funcionalidades sin aviso previo. Haremos un esfuerzo
            razonable por mantener el servicio disponible y por preservar tu información, pero no
            garantizamos disponibilidad ininterrumpida.
          </p>
        </section>

        <section>
          <h2 className="font-semibold mb-1.5">10. Eliminación de cuenta y datos</h2>
          <p>
            Puedes solicitar la eliminación de tu cuenta y de todos tus datos personales en cualquier
            momento escribiendo a dapxco@gmail.com. Procesaremos la solicitud dentro de los plazos
            establecidos por la Ley 1581 de 2012.
          </p>
        </section>

        <section>
          <h2 className="font-semibold mb-1.5">11. Cambios a estos Términos</h2>
          <p>
            Podemos actualizar estos Términos y Condiciones. Si el cambio es sustancial, te lo
            notificaremos dentro de la aplicación antes de que entre en vigencia.
          </p>
        </section>

        <section>
          <h2 className="font-semibold mb-1.5">12. Ley aplicable</h2>
          <p>
            Estos Términos se rigen por las leyes de la República de Colombia. Cualquier controversia
            se someterá a la jurisdicción de los jueces colombianos.
          </p>
        </section>

        <div className="rounded-2xl bg-accent-soft p-4 mt-6">
          <p className="text-xs text-ink">
            <b>Nota:</b> este documento es un borrador preparado como base de trabajo. Antes de operar
            con usuarios reales, debe ser revisado y validado por un abogado colombiano especializado
            en protección de datos y derecho digital/fintech, especialmente en lo referente a: (1)
            responsabilidad por categorización automática y proyecciones financieras, (2)
            actualización con NIT/razón social una vez constituida la empresa, y (3) cualquier
            eventual cobro futuro.
          </p>
        </div>
      </div>
    </div>
  )
}
