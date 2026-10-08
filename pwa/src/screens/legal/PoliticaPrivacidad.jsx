import { useVolver } from '../../lib/useVolver'
import { ArrowLeft } from 'lucide-react'

export default function PoliticaPrivacidad() {
  const volver = useVolver('/perfil')

  return (
    <div className="flex-1 overflow-y-auto pb-10">
      <header className="px-6 pantalla-top pb-2 flex items-center gap-3">
        <button onClick={volver} className="w-11 h-11 flex items-center justify-center -ml-2" aria-label="Volver">
          <ArrowLeft size={20} />
        </button>
        <h1 className="text-xl font-bold">Política de Privacidad</h1>
      </header>

      <div className="px-6 mt-4 text-sm leading-relaxed text-ink space-y-5">
        <p className="text-xs text-ink-soft">Versión 1.1 (borrador) · Última actualización: 3 de octubre de 2026</p>

        <section>
          <h2 className="font-semibold mb-1.5">1. Responsable del tratamiento</h2>
          <p>
            DAPX, nombre comercial bajo el cual opera actualmente una persona natural en proceso de
            formalización empresarial en Colombia, es responsable del tratamiento de tus datos
            personales conforme a la Ley 1581 de 2012 y el Decreto 1377 de 2013. Contacto:
            dapxco@gmail.com.
          </p>
        </section>

        <section>
          <h2 className="font-semibold mb-1.5">2. Qué datos recopilamos</h2>
          <ul className="list-disc pl-5 space-y-1.5">
            <li><b>Datos de registro:</b> nombre y correo electrónico (o los que tu cuenta de Google comparta si inicias sesión así).</li>
            <li><b>Datos financieros que tú ingresas:</b> nombres de cuentas, saldos, movimientos, categorías, presupuestos, metas de ahorro, deudas.</li>
            <li><b>Datos de correos bancarios (opcional):</b> si conectas tu Gmail, leemos, en modo de solo lectura, los correos con la etiqueta que tú elijas (por defecto "gastos") y, además, buscamos notificaciones de bancos y extractos en PDF por remitente y palabras clave. No enviamos, borramos ni modificamos correos. De los correos que detectamos como movimientos guardamos remitente, asunto, un fragmento del texto y los datos extraídos (monto, comercio, fecha); del resto no guardamos nada.</li>
            <li><b>Extractos bancarios en PDF (opcional):</b> si subes un extracto, se procesa para extraer movimientos y se compara contra tu historial. El texto extraído no se comparte con terceros salvo lo indicado en la sección 5.</li>
            <li><b>Datos técnicos:</b> dirección IP, tipo de dispositivo, y datos de uso básicos para operar y dar soporte al servicio.</li>
          </ul>
        </section>

        <section>
          <h2 className="font-semibold mb-1.5">3. Para qué usamos tus datos</h2>
          <ul className="list-disc pl-5 space-y-1.5">
            <li>Operar las funciones de la aplicación (registrar y mostrar tus movimientos, calcular presupuestos, proyecciones y reportes).</li>
            <li>Sugerir categorías automáticamente, con base en tus propias reglas y patrones de comercios conocidos en Colombia.</li>
            <li>Enviarte notificaciones que tú actives (alertas de presupuesto, resumen semanal, recordatorios de pagos recurrentes).</li>
            <li>Dar soporte cuando lo solicites.</li>
            <li>Mejorar el producto — nunca vendemos tus datos financieros a terceros con fines comerciales o publicitarios.</li>
          </ul>
        </section>

        <section>
          <h2 className="font-semibold mb-1.5">4. Base legal del tratamiento</h2>
          <p>
            Tratamos tus datos con base en tu autorización previa, expresa e informada, otorgada al
            aceptar esta política y, para el acceso a Gmail o la lectura de extractos, mediante una
            autorización adicional y específica en el momento en que activas esas funciones.
          </p>
        </section>

        <section>
          <h2 className="font-semibold mb-1.5">5. Con quién compartimos tus datos</h2>
          <p>No vendemos ni arrendamos tus datos personales. Los compartimos únicamente con:</p>
          <ul className="list-disc pl-5 space-y-1.5 mt-1.5">
            <li><b>Proveedores de infraestructura técnica</b> que almacenan y procesan los datos en nuestro nombre bajo condiciones de confidencialidad: Supabase (base de datos y autenticación), Railway (servidores), Vercel (hosting del frontend), Google (API de Gmail, solo si tú la conectas), OpenRouter (inteligencia artificial, solo si usas el asistente o subes fotos de facturas), Resend (envío de correos: el resumen semanal y el cierre de mes si los activas, y las copias de seguridad internas) y Sentry (registro de errores técnicos, configurado para no recibir datos personales).</li>
            <li><b>Servicios de notificaciones push</b> del navegador o del teléfono (Apple, Google o Mozilla), solo si activas las notificaciones: reciben el aviso cifrado, no tus movimientos.</li>
            <li><b>Autoridades competentes</b>, únicamente cuando exista un requerimiento legal válido.</li>
          </ul>
          <p className="mt-2">
            Si en el futuro se compartieran datos agregados o anonimizados con fines de mejora del
            producto (ej. estadísticas de uso sin identificar personas), lo indicaremos aquí antes de
            hacerlo.
          </p>
        </section>

        <section>
          <h2 className="font-semibold mb-1.5">Novedades de tratamiento (octubre de 2026)</h2>
          <p>
            Correo y extractos: si conectas Gmail (permiso de solo lectura), CuadraMe lee los correos de la etiqueta que elijas y detecta, además, notificaciones bancarias sin etiqueta y extractos en PDF adjuntos. De los extractos guardamos solo metadatos (banco, periodo, nombre del archivo); el PDF se descarga, se procesa y no se almacena.
          </p>
          <p>
            Clave del PDF: si decides guardar la clave con la que se abren tus extractos (normalmente tu cédula), se guarda cifrada y nunca se incluye en copias de seguridad ni en correos. Puedes borrarla cuando quieras.
          </p>
          <p>
            Fotos de facturas: la imagen se procesa para sugerirte el movimiento y no se almacena; solo se guarda lo que confirmes.
          </p>
          <p>
            Asistente de IA: cuando usas funciones de IA (preguntas, lectura de facturas o de extractos) se envía a nuestro proveedor de IA (OpenRouter y los modelos que opere) únicamente lo necesario para responder: tu pregunta y un resumen de tus movimientos, cuentas, presupuestos, metas y deudas recientes, o el texto/imagen del documento. No enviamos tu contraseña, PIN ni claves. El proveedor puede estar fuera de Colombia (transferencia internacional).
          </p>
          <p>
            Gastos compartidos: puedes registrar nombres de amigos o contactos y lo que se les debe. Esos datos son de terceros que no usan CuadraMe: úsalos solo con su conocimiento y para dividir gastos. Puedes borrarlos en cualquier momento.
          </p>
          <p>
            PIN y biometría: el PIN y la huella/rostro se verifican en tu dispositivo; no los recibimos ni los guardamos en nuestros servidores.
          </p>
          <p>
            Patrimonio, impuestos y cierre de mes: los activos, valores y deudas que registres, las marcas de gastos posiblemente deducibles (con su nota de soporte, solo texto) y los informes mensuales que generamos se guardan en tu cuenta. Son información de apoyo y no constituyen asesoría tributaria ni financiera. El cierre de mes llega por notificación y, solo si lo activas, por correo electrónico (Resend).
          </p>
          <p>
            Resumen semanal por correo: viene apagado. Si lo activas en Perfil, guardamos tu correo de la cuenta para escribirte cada domingo con lo que gastaste esa semana, las categorías donde más se fue la plata, presupuestos casi agotados y pagos de tarjeta próximos. Lo apagas en el mismo lugar y dejamos de escribirte.
          </p>
          <p>
            Copias de seguridad: cada día se genera una copia de la base de datos de CuadraMe y se envía por correo (Resend) al administrador del servicio, para poder restaurar el servicio si algo falla. Incluye los datos de tu cuenta, pero nunca la clave de tus PDF ni contraseñas. Si eliminas tu cuenta, tus datos desaparecen de la base de datos de inmediato, pero las copias ya generadas se van reemplazando y pueden conservar tus datos por un tiempo limitado.
          </p>
          <p>
            Ubicación de los datos: los proveedores de infraestructura pueden procesar tus datos en servidores fuera de Colombia (transferencia internacional). Los escogemos por sus medidas de seguridad y por actuar como encargados bajo nuestras instrucciones.
          </p>
          <p>
            Importación de archivos: los CSV/Excel que subas se leen en el momento para proponerte movimientos; el archivo no se almacena.
          </p>
        </section>

        <section>
          <h2 className="font-semibold mb-1.5">6. Cómo protegemos tus datos</h2>
          <p>
            Las contraseñas se gestionan mediante Supabase Auth con estándares de cifrado de la
            industria. Las claves de acceso a Gmail (refresh tokens) se almacenan cifradas. La
            comunicación entre la aplicación y nuestros servidores viaja cifrada (HTTPS). No obstante,
            ningún sistema es 100% infalible; ante cualquier incidente de seguridad que comprometa tus
            datos, te notificaremos conforme a la ley.
          </p>
        </section>

        <section>
          <h2 className="font-semibold mb-1.5">7. Tus derechos (Habeas Data)</h2>
          <p>Como titular de tus datos personales, en cualquier momento puedes:</p>
          <ul className="list-disc pl-5 space-y-1.5 mt-1.5">
            <li>Conocer, actualizar y rectificar tus datos.</li>
            <li>Solicitar prueba de la autorización otorgada.</li>
            <li>Ser informado sobre el uso que se le ha dado a tus datos.</li>
            <li>Revocar la autorización y/o solicitar la eliminación de tus datos, cuando no exista un deber legal o contractual que impida su supresión.</li>
            <li>Acceder de forma gratuita a tus datos.</li>
            <li>Presentar quejas ante la Superintendencia de Industria y Comercio (SIC) por infracciones a la ley de protección de datos.</li>
          </ul>
          <p className="mt-2">
            Puedes ejercer estos derechos escribiendo a dapxco@gmail.com, o directamente desde la
            aplicación, en Perfil → Privacidad y datos: ver y revocar cada autorización, descargar tus
            datos y eliminar tu cuenta. También puedes desconectar tu Gmail en cualquier momento o
            eliminar cuentas y movimientos individualmente.
          </p>
        </section>

        <section>
          <h2 className="font-semibold mb-1.5">8. Retención de datos</h2>
          <p>
            Conservamos tus datos mientras tu cuenta esté activa. Si solicitas la eliminación de tu
            cuenta, eliminaremos tus datos personales de nuestros sistemas dentro de un plazo
            razonable, salvo la información que debamos conservar por obligación legal.
          </p>
        </section>

        <section>
          <h2 className="font-semibold mb-1.5">9. Menores de edad</h2>
          <p>
            CuadraMe no está dirigida a menores de 18 años. No recopilamos conscientemente datos de
            menores de edad.
          </p>
        </section>

        <section>
          <h2 className="font-semibold mb-1.5">10. Cambios a esta política</h2>
          <p>
            Si hacemos cambios sustanciales a esta política, te lo notificaremos dentro de la
            aplicación antes de que entren en vigencia.
          </p>
        </section>

        <div className="rounded-2xl bg-accent-soft p-4 mt-6">
          <p className="text-xs text-ink">
            <b>BORRADOR PARA REVISIÓN DE ABOGADO.</b> Este documento es un borrador preparado como base de trabajo, alineado a la
            Ley 1581 de 2012 y el Decreto 1377 de 2013. Antes de operar con usuarios reales, debe ser
            revisado por un abogado colombiano especializado en protección de datos, en particular:
            (1) el registro de la base de datos ante el Registro Nacional de Bases de Datos (RNBD) de
            la SIC si se supera el umbral de responsable obligado a inscribirse, (2) la vigencia y
            alcance exacto del acceso de solo lectura a Gmail frente a las políticas de Google, y (3)
            actualización con NIT una vez constituida la empresa.
          </p>
        </div>
      </div>
    </div>
  )
}
