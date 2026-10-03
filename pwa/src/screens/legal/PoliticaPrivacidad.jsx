import { useNavigate } from 'react-router-dom'
import { ArrowLeft } from 'lucide-react'

export default function PoliticaPrivacidad() {
  const navigate = useNavigate()

  return (
    <div className="flex-1 overflow-y-auto pb-10">
      <header className="px-6 pt-14 pb-2 flex items-center gap-3">
        <button onClick={() => navigate(-1)} className="w-9 h-9 flex items-center justify-center -ml-2" aria-label="Volver">
          <ArrowLeft size={20} />
        </button>
        <h1 className="text-xl font-bold">Política de Privacidad</h1>
      </header>

      <div className="px-6 mt-4 text-sm leading-relaxed text-ink space-y-5">
        <p className="text-xs text-ink-soft">Última actualización: 30 de septiembre de 2026</p>

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
            <li><b>Datos de correos bancarios (opcional):</b> si conectas tu Gmail, accedemos únicamente a los correos con la etiqueta que tú elijas (por defecto "gastos"), en modo de solo lectura, para sugerir movimientos. No leemos el resto de tu bandeja.</li>
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
            <li><b>Proveedores de infraestructura técnica</b> que almacenan y procesan los datos en nuestro nombre bajo condiciones de confidencialidad: Supabase (base de datos y autenticación), Railway (servidores), Vercel (hosting del frontend), Google (API de Gmail, solo si tú la conectas).</li>
            <li><b>Autoridades competentes</b>, únicamente cuando exista un requerimiento legal válido.</li>
          </ul>
          <p className="mt-2">
            Si en el futuro se compartieran datos agregados o anonimizados con fines de mejora del
            producto (ej. estadísticas de uso sin identificar personas), lo indicaremos aquí antes de
            hacerlo.
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
            aplicación: desconectando tu Gmail en cualquier momento (Correos → Desconectar), eliminando
            cuentas o movimientos individualmente, o solicitando la eliminación total de tu cuenta.
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
            <b>Nota:</b> este documento es un borrador preparado como base de trabajo, alineado a la
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
