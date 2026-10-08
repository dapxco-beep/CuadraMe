// Contenido de «Aprende»: microlecciones de 1 minuto y glosario. Para agregar o cambiar algo basta
// editar este archivo: ninguna pantalla se toca.
//
// LECCIONES: { id, titulo, resumen, cuerpo[], ejemplo, accion?, palabras }
//   id        identificador corto y único (es el ancla: /aprende?l=<id>). Los consejos del servidor
//             (backend/app/consejos.py, LECCIONES) apuntan a estos ids.
//   resumen   una frase que se ve con la lección cerrada
//   cuerpo    párrafos en lenguaje llano; «**así**» pone negrita; una línea que empieza con «- » es viñeta
//   ejemplo   un caso en pesos colombianos (COP) con cuentas hechas a mano
//   accion    (opcional) { texto, to } lleva a la pantalla donde se aplica
//   palabras  sinónimos que la gente escribe en el buscador
//
// GLOSARIO: { id, termino, definicion, palabras, leccion? }
//   <Ayudita termino="cupo"> abre la definición del término cuyo id coincida.
//
// Reglas de estilo: tú, frases cortas, sin jerga. Es orientación EDUCATIVA, no asesoría financiera:
// nada de recomendar productos, inversiones ni prometer rendimientos.

export const AVISO_EDUCATIVO = 'Orientación educativa, no es asesoría financiera.'

export const LECCIONES = [
  {
    id: 'presupuesto-50-30-20',
    titulo: 'Presupuesto 50/30/20, a tu medida',
    resumen: 'Una forma simple de repartir lo que ganas.',
    cuerpo: [
      'La regla sugiere repartir tu ingreso así: **50 %** para necesidades (arriendo, servicios, mercado, transporte), **30 %** para gustos y **20 %** para ahorro o pagar deudas.',
      'Es un punto de partida, no una ley. En Colombia, con arriendo y transporte, las necesidades suelen pasar del 50 %. Si es tu caso, prueba **60/25/15** o lo que te sea realista, pero ponle siempre un número al ahorro.',
      'Lo importante: que cada peso tenga un destino **antes** de que llegue el fin de mes.',
    ],
    ejemplo: 'Si te entran $3.000.000: $1.500.000 a necesidades, $900.000 a gustos y $600.000 a ahorro o deudas. Con la versión 60/25/15 serían $1.800.000, $750.000 y $450.000.',
    accion: { texto: 'Crear mi presupuesto', to: '/presupuesto' },
    palabras: 'presupuesto repartir ingreso necesidades gustos ahorro regla porcentaje',
  },
  {
    id: 'fondo-de-emergencia',
    titulo: 'Fondo de emergencia',
    resumen: 'Un colchón para imprevistos, sin endeudarte.',
    cuerpo: [
      'Es plata guardada **solo** para sorpresas: quedarte sin trabajo, una urgencia médica, dañar el celular o la nevera.',
      'Una guía común es juntar entre **3 y 6 meses de tus gastos** básicos. No tienes que lograrlo de una: el primer escalón es **un mes**.',
      'Guárdalo donde puedas sacarlo rápido y donde no lo veas a diario para gastarlo (por ejemplo, una cuenta de ahorros aparte).',
    ],
    ejemplo: 'Si tus gastos del mes son $2.000.000: 3 meses son $6.000.000 y 6 meses son $12.000.000. Si ahorras $200.000 al mes, el primer mes de colchón te toma 10 meses. Empezar es lo que cuenta.',
    accion: { texto: 'Crear una meta', to: '/metas' },
    palabras: 'emergencia colchon imprevistos ahorro reserva meses gastos',
  },
  {
    id: 'tarjeta-de-credito',
    titulo: 'Cómo funciona tu tarjeta de crédito',
    resumen: 'Cupo, corte, fecha de pago y cuotas, sin enredos.',
    cuerpo: [
      'Con la tarjeta el banco te **presta** plata. Estas son sus piezas:',
      '- **Cupo:** lo máximo que puedes deber.',
      '- **Fecha de corte:** el día en que el banco «cierra la cuenta» y arma tu extracto con lo que compraste.',
      '- **Fecha de pago:** el último día para pagar ese extracto. Si pagas el **total** antes de esa fecha, no pagas intereses por esas compras.',
      '- **Cuotas:** repartir una compra en varios meses. Pregunta siempre si son **con o sin interés**.',
      'Lo que compras **después del corte** entra al extracto siguiente: tienes más días para pagarlo.',
    ],
    ejemplo: 'Cupo de $3.000.000, corte el día 10 y pago el 25. Compras $600.000 el día 9: lo pagas el 25 (16 días después). Si compras lo mismo el día 11, pasa al extracto del mes siguiente y lo pagas el 25 del otro mes (unos 45 días). En ambos casos usas el 20 % del cupo.',
    accion: { texto: 'Ver mis tarjetas', to: '/cuentas' },
    palabras: 'tarjeta credito cupo corte pago fecha cuotas extracto minimo total intereses',
  },
  {
    id: 'debito-vs-credito',
    titulo: 'Débito vs crédito',
    resumen: 'Plata tuya contra plata prestada.',
    cuerpo: [
      'Con la **tarjeta débito** pagas con plata que **ya tienes**: el saldo de tu cuenta baja al instante.',
      'Con la **tarjeta de crédito** pagas con plata **del banco**: tu cuenta no se mueve, pero **debes** esa plata y tienes que devolverla en tu fecha de pago.',
      'Por eso en CuadraMe el saldo de una cuenta de ahorros es lo que **tienes**, y el de una tarjeta es lo que **debes**.',
      'Y ojo: cuando pagas la tarjeta desde tu cuenta, **no es un gasto nuevo**; es devolver lo que ya habías comprado.',
    ],
    ejemplo: 'Compras unos zapatos de $200.000. Con débito, tu cuenta pasa de $1.000.000 a $800.000 hoy. Con crédito, tu cuenta sigue en $1.000.000 y la tarjeta muestra una deuda de $200.000 que pagarás después.',
    accion: { texto: 'Ver mis cuentas', to: '/cuentas' },
    palabras: 'debito credito diferencia tarjeta saldo disponible deuda prestado',
  },
  {
    id: 'interes-ea-vs-nominal',
    titulo: 'Tasa efectiva anual vs nominal',
    resumen: 'Por qué dos tasas «iguales» no cuestan lo mismo.',
    cuerpo: [
      'La tasa **nominal** es la que se anuncia; la **efectiva anual (E.A.)** es la que de verdad pagas (o ganas) en un año, porque el interés se suma al saldo mes a mes.',
      'Para comparar productos usa siempre la **E.A.**: es la única que pone a todos en la misma regla.',
      'Cuando una tasa viene «mensual», no la multipliques por 12: se compone. Un 2 % mensual no es 24 % al año, es cerca de **26,8 % E.A.**',
    ],
    ejemplo: 'Si le debes $1.000.000 a una tarjeta que cobra 2 % mensual y no pagas nada, al mes debes $1.020.000; en un año, cerca de $1.268.000 (no $1.240.000). Y si una cuenta te paga 8 % E.A., $1.000.000 se vuelven $1.080.000 en un año.',
    accion: { texto: 'Ver mis deudas', to: '/deudas' },
    palabras: 'tasa efectiva anual ea nominal interes mensual compuesto usura comparar',
  },
  {
    id: 'traslado',
    titulo: '¿Qué es un traslado?',
    resumen: 'Mover plata entre tus cuentas no es gastar.',
    cuerpo: [
      'Un **traslado** es pasar plata de una cuenta tuya a otra tuya: del Bancolombia al Nequi, o de tu cuenta a tu tarjeta para pagarla.',
      'No es gasto ni ingreso: tu plata total es la misma, solo cambió de bolsillo. Si se contara como gasto, tus informes dirían que gastaste el doble.',
      'CuadraMe detecta traslados cuando ve una salida y una entrada del mismo valor en tus cuentas. Si se equivoca, puedes marcar el movimiento como traslado (o como gasto real) desde su detalle.',
    ],
    ejemplo: 'Pasas $300.000 de tu cuenta de ahorros al Nequi. Ahorros baja $300.000 y Nequi sube $300.000: en total sigues teniendo lo mismo, y tus gastos del mes no cambian.',
    accion: { texto: 'Ver mis movimientos', to: '/movimientos' },
    palabras: 'traslado transferencia entre cuentas nequi bre-b mover plata gasto doble',
  },
  {
    id: 'deudas-avalancha-bola-de-nieve',
    titulo: 'Deudas: avalancha vs bola de nieve',
    resumen: 'Dos formas de decidir cuál pagar primero.',
    cuerpo: [
      'En las dos, **pagas el mínimo de todas** y pones el dinero extra en una sola deuda.',
      '- **Avalancha:** el extra va a la deuda con la **tasa más alta**. Es la que menos intereses te cuesta en total.',
      '- **Bola de nieve:** el extra va a la deuda **más pequeña**. Cuesta un poco más en intereses, pero cierras deudas rápido y eso motiva.',
      'La mejor es la que **sí vas a mantener** hasta terminar. Cuando termines una, su cuota se suma al extra para atacar la siguiente.',
    ],
    ejemplo: 'Debes $5.000.000 al 30 % E.A. y $800.000 al 18 % E.A., y te sobran $200.000 al mes. Avalancha: el extra va a la de $5.000.000. Bola de nieve: va a la de $800.000, que cierras en pocos meses.',
    accion: { texto: 'Comparar métodos', to: '/deudas' },
    palabras: 'deudas avalancha bola nieve pagar primero tasa saldo prestamo credito',
  },
  {
    id: 'gastos-hormiga',
    titulo: 'Gastos hormiga',
    resumen: 'Compras pequeñas que juntas pesan.',
    cuerpo: [
      'Son gastos pequeños y frecuentes —el tinto, el domicilio, la suscripción olvidada— que uno casi no siente, pero que sumados al mes y al año son grandes.',
      'No se trata de quitarte todos los gustos: se trata de **elegirlos** en lugar de que se te escapen. Mira cuáles te hacen feliz de verdad y cuáles son por inercia.',
      'Revisa tus suscripciones: lo que no usas hace meses es la plata más fácil de recuperar.',
    ],
    ejemplo: 'Un café de $6.000 cada día hábil (20 días) son $120.000 al mes, o $1.440.000 al año.',
    accion: { texto: 'Ver en qué gasto', to: '/informe' },
    palabras: 'hormiga cafe domicilio suscripcion pequeños gastos fugas',
  },
  {
    id: 'inflacion-y-ahorro',
    titulo: 'Inflación y ahorro',
    resumen: 'Por qué la plata quieta pierde poder de compra.',
    cuerpo: [
      'La **inflación** es cuánto suben los precios con el tiempo. Con el mismo billete, cada año compras un poco menos.',
      'Por eso, cuando guardas plata, conviene mirar la tasa que te pagan (en **E.A.**) y compararla con la inflación: si rinde menos, tu ahorro pierde poder de compra aunque el número no baje.',
      'Esto es solo para que entiendas el efecto; CuadraMe no recomienda productos ni inversiones. Para decidir dónde poner tu plata, compara tasas y condiciones con calma o consulta a un asesor autorizado.',
    ],
    ejemplo: 'Con una inflación de 5 % anual, $1.000.000 de hoy compran lo que $952.000 compran dentro de un año. Si tu ahorro rinde 3 % E.A., en términos reales perdiste un poco.',
    palabras: 'inflacion precios poder adquisitivo ahorro rendimiento tasa ipc',
  },
  {
    id: 'seguridad-fraudes',
    titulo: 'Protégete de fraudes (Nequi, Bre-B y más)',
    resumen: 'Las transferencias inmediatas no se devuelven.',
    cuerpo: [
      '**Nadie del banco, de Nequi o de CuadraMe te pide tu clave, el código que llega por mensaje ni te manda a «reversar» plata.** Si alguien lo hace, es fraude.',
      'Las transferencias por Nequi, Bre-B y similares son **inmediatas**: una vez enviadas, casi no se pueden devolver. Antes de confirmar, lee el **nombre y los datos** del destinatario.',
      '- Desconfía de la prisa («¡hazlo ya o pierdes la cuenta!»), de premios y de ofertas muy buenas.',
      '- No abras enlaces de mensajes o correos que dicen ser de tu banco: entra tú a la app oficial.',
      '- Si te equivocaste o sospechas, **llama a tu banco de inmediato**, por el número que aparece en tu tarjeta o en su página oficial.',
    ],
    ejemplo: 'Te escriben «soy del banco, te llegó un código, dímelo para cancelar un cobro de $1.800.000». Cuelga: ese código es la llave de tu cuenta y quien lo pide quiere vaciarla.',
    palabras: 'fraude estafa seguridad nequi bre-b clave codigo otp phishing suplantacion transferencia',
  },
  {
    id: 'revisar-extractos',
    titulo: 'Revisa tu extracto cada mes',
    resumen: 'Cinco minutos para detectar cobros raros.',
    cuerpo: [
      'El extracto es el resumen mensual de tu cuenta o tarjeta. Léelo con estas preguntas:',
      '- ¿Reconozco **todos** los cobros?',
      '- ¿Qué **intereses, cuota de manejo o 4x1000** me cobraron?',
      '- ¿Hay suscripciones que ya no uso?',
      '- ¿El total coincide con lo que tengo registrado?',
      'Si un cobro no te suena, llama al banco pronto: reclamar rápido ayuda. Subir tu extracto a CuadraMe además cruza todo con tus movimientos y te muestra lo que falta.',
    ],
    ejemplo: 'Ves un cobro de $29.900 de un servicio que no recuerdas: puede ser una suscripción olvidada. Cancelarla ahorra $358.800 al año.',
    accion: { texto: 'Subir un extracto', to: '/sincronizacion' },
    palabras: 'extracto revisar cobros cuota manejo intereses 4x1000 gmf reclamo conciliar',
  },
]

export const GLOSARIO = [
  { id: 'cupo', termino: 'Cupo', definicion: 'Lo máximo que el banco te deja deber con una tarjeta de crédito. Si tu cupo es $3.000.000 y debes $600.000, te quedan $2.400.000 disponibles.', palabras: 'limite tarjeta credito disponible', leccion: 'tarjeta-de-credito' },
  { id: 'fecha-de-corte', termino: 'Fecha de corte', definicion: 'El día del mes en que el banco cierra tu extracto y suma lo que compraste. Lo que compras después entra en el extracto siguiente.', palabras: 'corte cierre extracto tarjeta', leccion: 'tarjeta-de-credito' },
  { id: 'fecha-de-pago', termino: 'Fecha límite de pago', definicion: 'El último día para pagar tu extracto. Si pagas el total hasta ese día no pagas intereses por esas compras; después empiezan a cobrarte.', palabras: 'pago vencimiento limite plazo mora', leccion: 'tarjeta-de-credito' },
  { id: 'pago-minimo', termino: 'Pago mínimo', definicion: 'Lo menos que debes pagar para no caer en mora. Ojo: lo que no pagas sigue generando intereses, así que el mínimo sale caro si se vuelve costumbre.', palabras: 'minimo tarjeta mora intereses', leccion: 'tarjeta-de-credito' },
  { id: 'pago-total', termino: 'Pago total (para no pagar intereses)', definicion: 'Lo que debes pagar del extracto, completo y a tiempo, para que el banco no te cobre intereses por las compras de ese periodo.', palabras: 'total evitar intereses extracto', leccion: 'tarjeta-de-credito' },
  { id: 'intereses', termino: 'Intereses', definicion: 'El precio de usar plata prestada. Si le debes $1.000.000 a una tarjeta que cobra 2 % mensual, son unos $20.000 de interés cada mes.', palabras: 'interes costo prestamo cobro', leccion: 'interes-ea-vs-nominal' },
  { id: 'cuotas', termino: 'Cuotas', definicion: 'Repartir una compra con tarjeta en varios pagos mensuales. Pregunta si son con interés o sin interés: cambia mucho cuánto pagas en total.', palabras: 'cuota diferido plazos meses compra', leccion: 'tarjeta-de-credito' },
  { id: 'utilizacion', termino: 'Utilización del cupo', definicion: 'Qué parte de tu cupo estás usando. Mantenerla por debajo del 30 % da margen y suele verse bien en tu historial crediticio.', palabras: 'uso cupo porcentaje 30 historial', leccion: 'tarjeta-de-credito' },
  { id: 'debito', termino: 'Tarjeta débito', definicion: 'Paga con plata que ya tienes: el saldo de tu cuenta baja en el momento de la compra.', palabras: 'debito cuenta ahorros saldo', leccion: 'debito-vs-credito' },
  { id: 'credito', termino: 'Tarjeta de crédito', definicion: 'Paga con plata que te presta el banco: tu cuenta no se mueve, pero quedas debiendo hasta que pagues el extracto.', palabras: 'credito tarjeta deuda prestado', leccion: 'debito-vs-credito' },
  { id: 'saldo-disponible', termino: 'Saldo disponible', definicion: 'La plata tuya que tienes en una cuenta y puedes usar ya. En una tarjeta de crédito no aplica: ahí lo que ves es lo que debes.', palabras: 'saldo cuenta ahorros disponible tengo', leccion: 'debito-vs-credito' },
  { id: 'lo-que-debes', termino: 'Lo que debes (tarjeta)', definicion: 'El total que le debes al banco por tus compras con la tarjeta. No es un gasto nuevo: ya lo contaste cuando compraste.', palabras: 'deuda tarjeta saldo negativo debes', leccion: 'debito-vs-credito' },
  { id: 'ea', termino: 'Tasa efectiva anual (E.A.)', definicion: 'Lo que de verdad pagas o ganas en un año con el interés compuesto. Es la tasa correcta para comparar productos.', palabras: 'ea efectiva anual tasa comparar', leccion: 'interes-ea-vs-nominal' },
  { id: 'nominal', termino: 'Tasa nominal', definicion: 'La tasa «de vitrina», sin sumar el efecto de que el interés se suma al saldo cada mes. Siempre es menor que la efectiva.', palabras: 'nominal tasa anunciada mensual vencida', leccion: 'interes-ea-vs-nominal' },
  { id: 'traslado', termino: 'Traslado', definicion: 'Mover plata entre tus propias cuentas. No es gasto ni ingreso, solo cambió de bolsillo.', palabras: 'transferencia entre cuentas mover', leccion: 'traslado' },
  { id: 'pago-de-tarjeta', termino: 'Pago de tarjeta', definicion: 'Cuando pagas tu tarjeta desde una cuenta. No es un gasto nuevo: es devolver lo que ya compraste, por eso no suma a tus gastos del mes.', palabras: 'abono tarjeta pagar extracto', leccion: 'debito-vs-credito' },
  { id: 'gasto-hormiga', termino: 'Gasto hormiga', definicion: 'Compra pequeña y frecuente que casi no se siente, pero que sumada pesa: un café diario de $6.000 son $120.000 al mes.', palabras: 'hormiga cafe pequeño frecuente', leccion: 'gastos-hormiga' },
  { id: 'fondo-de-emergencia', termino: 'Fondo de emergencia', definicion: 'Plata guardada solo para imprevistos. Una guía común es entre 3 y 6 meses de tus gastos básicos.', palabras: 'emergencia colchon reserva imprevistos', leccion: 'fondo-de-emergencia' },
  { id: 'limite-presupuesto', termino: 'Límite del presupuesto', definicion: 'El tope que te pones para gastar en una categoría durante un periodo. CuadraMe te avisa cuando te acercas.', palabras: 'presupuesto limite tope categoria', leccion: 'presupuesto-50-30-20' },
  { id: 'sobrante', termino: 'Sobrante arrastrado', definicion: 'Lo que no gastaste de un presupuesto en el periodo anterior y se suma al nuevo: es un colchón extra, no una obligación.', palabras: 'sobrante arrastre rollover resto', leccion: 'presupuesto-50-30-20' },
  { id: 'proyeccion', termino: 'Proyección de gasto', definicion: 'Una estimación de cuánto habrás gastado al terminar el mes si sigues al ritmo de hoy. No es una promesa: cambia con lo que hagas.', palabras: 'proyeccion ritmo estimado fin de mes', leccion: 'presupuesto-50-30-20' },
  { id: 'avalancha', termino: 'Método avalancha', definicion: 'Pagar primero la deuda con la tasa más alta. Es la que menos intereses te cuesta en total.', palabras: 'avalancha tasa alta deudas', leccion: 'deudas-avalancha-bola-de-nieve' },
  { id: 'bola-de-nieve', termino: 'Método bola de nieve', definicion: 'Pagar primero la deuda más pequeña para cerrarla pronto y ganar motivación; después sigues con la siguiente.', palabras: 'bola nieve snowball deuda pequeña', leccion: 'deudas-avalancha-bola-de-nieve' },
  { id: 'inflacion', termino: 'Inflación', definicion: 'El aumento general de los precios. Con una inflación de 5 %, $1.000.000 de hoy compran lo de $952.000 dentro de un año.', palabras: 'inflacion precios ipc poder adquisitivo', leccion: 'inflacion-y-ahorro' },
  { id: 'extracto', termino: 'Extracto', definicion: 'El resumen mensual de una cuenta o tarjeta: lo que entró, lo que salió y lo que debes. Casi siempre llega en PDF.', palabras: 'extracto estado cuenta pdf resumen', leccion: 'revisar-extractos' },
  { id: 'conciliar', termino: 'Conciliar', definicion: 'Comparar lo que registraste con lo que dice tu extracto para ver qué falta o qué sobra.', palabras: 'conciliar cruzar comparar extracto', leccion: 'revisar-extractos' },
  { id: 'cuota-de-manejo', termino: 'Cuota de manejo', definicion: 'Lo que el banco te cobra por mantener tu tarjeta o cuenta. A veces se puede negociar o eliminar si la usas lo suficiente.', palabras: 'manejo cobro tarjeta comision', leccion: 'revisar-extractos' },
  { id: '4x1000', termino: '4x1000 (GMF)', definicion: 'Impuesto de $4 por cada $1.000 que retiras o transfieres de una cuenta. Hay exenciones para una cuenta de ahorros por persona hasta cierto monto.', palabras: 'gmf cuatro por mil impuesto movimientos financieros', leccion: 'revisar-extractos' },
  { id: 'bre-b', termino: 'Bre-B', definicion: 'Sistema de pagos inmediatos del Banco de la República: envías plata a una «llave» (celular, correo…) en segundos. Como es inmediato, casi no se puede devolver.', palabras: 'bre-b breb llave transferencia inmediata', leccion: 'seguridad-fraudes' },
  { id: 'mora', termino: 'Mora', definicion: 'Estar atrasado en un pago. Trae intereses extra, afecta tu historial crediticio y puede terminar en cobro jurídico.', palabras: 'mora atraso retraso cobranza', leccion: 'tarjeta-de-credito' },
  { id: 'historial-crediticio', termino: 'Historial crediticio', definicion: 'El registro de cómo pagas tus deudas. Pagar a tiempo y usar poco de tu cupo ayuda a que te aprueben créditos con mejores condiciones.', palabras: 'historial crediticio datacredito score reporte', leccion: 'tarjeta-de-credito' },
]

// ── Búsqueda: sin mayúsculas ni acentos, todas las palabras deben aparecer ──
export function normalizar(texto) {
  return String(texto || '')
    .normalize('NFD')
    .replace(/\p{Diacritic}/gu, '')
    .toLowerCase()
    .replace(/[¿?¡!.,;:«»"()]/g, ' ')
    .replace(/\s+/g, ' ')
    .trim()
}

const raiz = (p) => (p.length > 3 ? p.replace(/(es|s)$/, '') : p)

function buscar(consulta, lista, titulo, resto) {
  const palabras = normalizar(consulta).split(' ').filter(Boolean).map(raiz)
  if (palabras.length === 0) return lista
  return lista
    .map((x) => {
      const enTitulo = normalizar(`${titulo(x)} ${x.palabras}`)
      const todo = normalizar(`${titulo(x)} ${x.palabras} ${resto(x)}`)
      if (!palabras.every((w) => todo.includes(w))) return null
      return { x, peso: palabras.every((w) => enTitulo.includes(w)) ? 0 : 1 }
    })
    .filter(Boolean)
    .sort((a, b) => a.peso - b.peso)
    .map((r) => r.x)
}

export const buscarGlosario = (consulta, lista = GLOSARIO) =>
  buscar(consulta, lista, (t) => t.termino, (t) => t.definicion)

export const buscarLecciones = (consulta, lista = LECCIONES) =>
  buscar(consulta, lista, (l) => l.titulo, (l) => `${l.resumen} ${l.cuerpo.join(' ')}`)

export const terminoPorId = (id) => GLOSARIO.find((t) => t.id === id) || null
export const leccionPorId = (id) => LECCIONES.find((l) => l.id === id) || null
