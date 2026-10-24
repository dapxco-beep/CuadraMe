import { useVolver } from '../../lib/useVolver'
import { ArrowLeft } from 'lucide-react'

export default function AutorizacionDatos() {
  const volver = useVolver('/perfil')

  return (
    <div className="flex-1 overflow-y-auto pb-10">
      <header className="px-6 pantalla-top pb-2 flex items-center gap-3">
        <button onClick={volver} className="w-11 h-11 flex items-center justify-center -ml-2" aria-label="Volver">
          <ArrowLeft size={20} />
        </button>
        <h1 className="text-xl font-bold">Autorización de datos</h1>
      </header>

      <div className="px-6 mt-4 text-sm leading-relaxed text-ink space-y-5">
        <p className="text-xs text-ink-soft">Versión 1.2 (borrador) · Última actualización: 3 de octubre de 2026</p>

        <section>
          <p>
            De acuerdo con la Ley 1581 de 2012, el Decreto 1377 de 2013 y demás normas que las
            complementen o modifiquen, al aceptar este documento autorizo de manera previa, expresa e
            informada a DAPX (dapxco@gmail.com), como responsable del tratamiento, para:
          </p>
        </section>

        <section>
          <h2 className="font-semibold mb-1.5">1. Recolectar y tratar mis datos personales</h2>
          <p>
            Incluyendo mi nombre, correo electrónico, y la información financiera que yo mismo ingrese
            en la aplicación (cuentas, movimientos, montos, categorías, metas, deudas), con la
            finalidad exclusiva de prestar el servicio de organización y análisis financiero personal
            que ofrece CuadraMe.
          </p>
        </section>

        <section>
          <h2 className="font-semibold mb-1.5">2. Acceso opcional a mi cuenta de Gmail</h2>
          <p>
            Solo si yo activo esta función de forma explícita desde la aplicación, autorizo a CuadraMe
            a acceder, en modo de solo lectura, a los correos de mi Gmail con la etiqueta que
            configure (por defecto "gastos") y a las notificaciones bancarias y extractos en PDF que
            detecte por remitente y palabras clave, con el único fin de sugerir movimientos
            financieros. Entiendo que:
          </p>
          <ul className="list-disc pl-5 space-y-1.5 mt-1.5">
            <li>CuadraMe no envía, borra ni modifica mis correos.</li>
            <li>Puedo revocar este acceso en cualquier momento desde la sección "Correos" de la aplicación.</li>
            <li>Al revocarlo, CuadraMe deja de tener acceso a mi cuenta de Gmail de inmediato.</li>
          </ul>
        </section>

        <section>
          <h2 className="font-semibold mb-1.5">3. Procesamiento de extractos bancarios que yo suba</h2>
          <p>
            Solo si yo subo voluntariamente un extracto bancario en PDF, autorizo su procesamiento
            (incluyendo, cuando sea necesario, el uso de servicios de terceros para extracción de texto
            asistida) con el único fin de identificar los movimientos contenidos en ese documento y
            compararlos con mi historial registrado en la aplicación.
          </p>
        </section>

        <section>
          <h2 className="font-semibold mb-1.5">4. Envío de notificaciones</h2>
          <p>
            Solo si yo activo las notificaciones push desde la aplicación, autorizo el envío de
            alertas relacionadas con mis presupuestos, recordatorios de pagos recurrentes y resúmenes
            periódicos de mi actividad financiera.
          </p>
        </section>

        <section>
          <h2 className="font-semibold mb-1.5">5. Transferencia a encargados del tratamiento</h2>
          <p>
            Autorizo que mis datos sean almacenados y procesados por los proveedores de infraestructura
            técnica que DAPX utiliza para operar CuadraMe (actualmente Supabase, Railway, Vercel, Resend para correos y copias de seguridad, y Sentry para errores técnicos),
            quienes actúan como encargados del tratamiento bajo instrucciones de DAPX y sujetos a
            condiciones de confidencialidad.
          </p>
        </section>

        <section>
          <h2 className="font-semibold mb-1.5">Autorizaciones adicionales (octubre de 2026)</h2>
          <p>
            Autorizo la lectura de adjuntos y extractos en mi Gmail (si conecto Gmail), incluida la detección de notificaciones bancarias sin etiqueta y de extractos en PDF; el PDF no se almacena.
          </p>
          <p>
            Autorizo, si decido guardarla, el almacenamiento cifrado de la clave de mis extractos en PDF, que puedo borrar cuando quiera.
          </p>
          <p>
            Autorizo el procesamiento de fotos de facturas que yo suba (no se almacenan) y el envío a un proveedor de IA (OpenRouter y sus modelos, posiblemente fuera de Colombia) de los datos mínimos necesarios para responder mis consultas: mi pregunta, un resumen de mis movimientos, cuentas, presupuestos, metas y deudas, o el contenido del documento. Nunca contraseñas, PIN ni claves.
          </p>
          <p>
            Declaro que los datos de terceros que registre en gastos compartidos (nombres de contactos) los trato con su conocimiento y solo para dividir gastos.
          </p>
          <p>
            Entiendo que el PIN y la biometría se verifican localmente en mi dispositivo, y que los datos de patrimonio, impuestos y cierres mensuales se guardan en mi cuenta como información de apoyo, no asesoría.
          </p>
        </section>

        <section>
          <h2 className="font-semibold mb-1.5">6. Carácter de la autorización</h2>
          <p>
            Esta autorización es voluntaria. Puedo revocarla en cualquier momento y/o solicitar la
            supresión de mis datos, salvo que exista un deber legal o contractual que requiera su
            conservación, escribiendo a dapxco@gmail.com o gestionándolo directamente desde la
            aplicación (desconectar Gmail, eliminar movimientos o cuentas, o solicitar la eliminación
            completa de mi cuenta).
          </p>
        </section>

        <section>
          <h2 className="font-semibold mb-1.5">7. Declaro que</h2>
          <ul className="list-disc pl-5 space-y-1.5">
            <li>He leído y entendido esta autorización, la Política de Privacidad y los Términos y Condiciones de CuadraMe.</li>
            <li>Soy mayor de edad.</li>
            <li>La información que ingreso a la aplicación es mía o de personas que me han autorizado a registrarla (ej. una cuenta familiar compartida), y asumo la responsabilidad de contar con esa autorización cuando aplique.</li>
          </ul>
        </section>

        <div className="rounded-2xl bg-accent-soft p-4 mt-6">
          <p className="text-xs text-ink">
            <b>Nota:</b> este documento es un borrador preparado como base de trabajo. Antes de
            operar con usuarios reales, debe ser revisado por un abogado colombiano especializado en
            protección de datos personales, particularmente en cuanto al alcance exacto de la
            autorización para el acceso a Gmail (scope de solo lectura) frente a los requisitos de la
            política de datos de usuario limitado de Google, y su articulación con el registro ante el
            RNBD si aplica.
          </p>
        </div>
      </div>
    </div>
  )
}
