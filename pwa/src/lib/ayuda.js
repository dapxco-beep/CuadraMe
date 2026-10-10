// Contenido del Centro de ayuda. Para agregar o cambiar una pregunta basta editar este archivo:
// no hay que tocar ninguna pantalla.
//
// Cada pregunta:
//   id        identificador corto y único (sirve de ancla y de clave)
//   tema      una de las claves de TEMAS (agrupa las preguntas)
//   pregunta  tal como la diría una persona, sin términos técnicos
//   respuesta lista de párrafos en lenguaje llano; «**así**» pone negrita; una línea que empieza
//             con «- » se muestra como viñeta
//   palabras  sinónimos que la gente escribe en el buscador y que no están en la pregunta
//   accion    (opcional) { texto, to } lleva directo a la pantalla donde se resuelve; { texto, guia: 'instalar' } abre la guía visual
//
// Reglas de estilo: tú, frases cortas, sin «token», «API», «endpoint» ni códigos de error.

export const TEMAS = {
  empezar: 'Para empezar',
  traer: 'Traer movimientos',
  entender: 'Entender mis números',
  privacidad: 'Privacidad y seguridad',
}

export const PREGUNTAS = [
  {
    id: 'instalar-app',
    tema: 'empezar',
    pregunta: '¿Cómo pongo CuadraMe en mi celular?',
    respuesta: [
      '**iPhone:** abre CuadraMe en **Safari** (no en Chrome), toca el botón **Compartir** y elige **Añadir a pantalla de inicio**.',
      '**Android:** abre CuadraMe en **Chrome**, toca los tres puntos de arriba y elige **Instalar app**.',
      'Después ábrela siempre desde el ícono nuevo. Así funciona como una app más y puede mandarte avisos.',
    ],
    palabras: 'instalar descargar icono pantalla inicio app celular movil telefono safari chrome',
    accion: { texto: 'Ver los pasos con dibujos', guia: 'instalar' },
  },
  {
    id: 'avisos',
    tema: 'empezar',
    pregunta: '¿Por qué no me llegan los avisos?',
    respuesta: [
      'Revisa tres cosas, en este orden:',
      '- Que hayas activado los avisos en **Perfil**.',
      '- Que tu celular permita avisos de CuadraMe (en Ajustes del celular).',
      '- En iPhone, que la app esté puesta en la pantalla de inicio: sin eso, el iPhone no deja que una página web te avise.',
    ],
    palabras: 'notificaciones alertas push recordatorio avisos no llegan sonido',
    accion: { texto: 'Ir a Perfil', to: '/perfil' },
  },
  {
    id: 'donde-extracto',
    tema: 'traer',
    pregunta: '¿Dónde saco mi extracto?',
    respuesta: [
      'El extracto es el resumen mensual de tu cuenta o tarjeta, en PDF. Casi todos los bancos lo dan gratis.',
      '- **En la app o la página de tu banco:** busca «Extractos», «Estados de cuenta» o «Certificados».',
      '- **En tu correo:** muchos bancos lo envían cada mes. Si conectas tu Gmail, CuadraMe lo encuentra solo.',
      'Descárgalo como **PDF** (no como foto ni captura de pantalla) y súbelo en «Traer movimientos».',
    ],
    palabras: 'extracto pdf banco estado de cuenta descargar resumen mensual subir conciliar',
    accion: { texto: 'Subir un extracto', to: '/sincronizacion' },
  },
  {
    id: 'clave-pdf',
    tema: 'traer',
    pregunta: '¿Qué es la clave del PDF?',
    respuesta: [
      'Los bancos protegen sus extractos con una contraseña para que nadie más los abra. Es la «clave del PDF».',
      'Casi siempre es **tu número de cédula** (a veces con otro dato, como los últimos dígitos de la tarjeta). Tu banco dice cuál en el correo donde te manda el extracto.',
      'Guárdala una sola vez en CuadraMe y la usará con todos tus extractos. Queda guardada cifrada y solo la usamos para abrir tus PDF.',
    ],
    palabras: 'clave contrasena password pdf cedula abrir protegido bloqueado',
    accion: { texto: 'Guardar mi clave del PDF', to: '/sincronizacion' },
  },
  {
    id: 'pago-dos-veces',
    tema: 'entender',
    pregunta: '¿Por qué un pago aparece dos veces?',
    respuesta: [
      'Pasa cuando el mismo gasto llega por dos caminos: por ejemplo, lo anotaste tú y después tu banco lo mandó por correo o en el extracto.',
      'CuadraMe intenta unirlos por fecha, hora y monto. Si no lo logra, verás los dos.',
      '- Abre el movimiento repetido y toca **Eliminar**.',
      '- Si llegó como «por confirmar», tócalo y elige **Descartar**.',
      'Cuando subes un extracto, CuadraMe te muestra lo que ya tenías registrado para que no lo cuentes dos veces.',
    ],
    palabras: 'duplicado repetido doble dos veces cobro repetido eliminar',
    accion: { texto: 'Ver mis movimientos', to: '/movimientos' },
  },
  {
    id: 'traslado',
    tema: 'entender',
    pregunta: '¿Qué es un traslado?',
    respuesta: [
      'Es plata que pasas de una cuenta tuya a otra tuya: de tu banco a Nequi, o de ahorros a la tarjeta.',
      'No es un gasto ni un ingreso, porque tu plata sigue siendo tuya. Por eso no cuenta en tus informes ni en tus presupuestos; solo cambia el saldo de cada cuenta.',
      'Si le transfieres a otra persona, eso sí es un gasto. Si CuadraMe lo marcó como traslado y no lo es, ábrelo y dile que es un gasto real.',
    ],
    palabras: 'transferencia traslado entre mis cuentas mover plata nequi propia',
    accion: { texto: 'Ver mis movimientos', to: '/movimientos' },
  },
  {
    id: 'saldo-no-coincide',
    tema: 'entender',
    pregunta: 'Mi saldo no coincide con el de mi banco. ¿Qué hago?',
    respuesta: [
      'El saldo de CuadraMe es lo que pusiste al crear la cuenta más lo que has registrado desde entonces. Si falta registrar algo, no va a coincidir.',
      '- **Rápido:** en «Cuentas» toca **Ajustar saldo** y escribe lo que dice tu banco hoy.',
      '- **A fondo:** sube el extracto y toca **Revisar extracto**. Te muestra qué movimientos del banco no están en CuadraMe.',
    ],
    palabras: 'saldo diferente no cuadra descuadrado ajustar corregir plata',
    accion: { texto: 'Ajustar saldo', to: '/cuentas' },
  },
  {
    id: 'por-confirmar',
    tema: 'entender',
    pregunta: '¿Qué significa «por confirmar»?',
    respuesta: [
      'Son movimientos que llegaron solos (de tu correo, de Apple Pay o de un atajo) y que CuadraMe quiere que revises antes de dejarlos definitivos.',
      'Cuando abres la app te pregunta «¿Son tuyos?». Puedes **confirmar**, **editar** o **descartar** cada uno.',
    ],
    palabras: 'confirmar revisar pendiente bandeja son tuyos automatico llegaron solos',
    accion: { texto: 'Traer movimientos', to: '/sincronizacion' },
  },
  {
    id: 'gmail-seguro',
    tema: 'privacidad',
    pregunta: '¿Es seguro conectar mi Gmail?',
    respuesta: [
      'Sí. Esto es lo que pasa, sin letra pequeña:',
      '- **Qué leemos:** solo los correos de bancos y billeteras conocidos (avisos de compras, transferencias y extractos).',
      '- **Qué no hacemos:** no leemos tus correos personales ni de trabajo, no enviamos nada, no borramos ni cambiamos ningún correo y no guardamos tu contraseña de Google.',
      '- **Tú mandas:** el permiso es de solo lectura y lo puedes quitar cuando quieras, desde CuadraMe o desde tu cuenta de Google.',
      'Si Google te dice que «no ha verificado esta app», es porque CuadraMe aún está en pruebas con invitación. Toca **Avanzado** y luego **Ir a CuadraMe**.',
    ],
    palabras: 'gmail correo seguro permiso privacidad leer google confianza conectar desconectar',
    accion: { texto: 'Conectar mi Gmail', to: '/sincronizacion' },
  },
  {
    id: 'atajo-apple-pay',
    tema: 'traer',
    pregunta: '¿Cómo registro mis pagos con Apple Pay sin escribir?',
    respuesta: [
      'En iPhone puedes instalar un «atajo»: un mini programa de Apple que avisa a CuadraMe cada vez que pagas con tu tarjeta en el celular.',
      'La guía te lo explica paso a paso. Toma unos 3 minutos y se hace una sola vez.',
      'Cada pago queda «por confirmar» para que lo revises cuando abras la app.',
    ],
    palabras: 'apple pay atajo shortcuts iphone wallet automatico siri tarjeta contactless',
    accion: { texto: 'Instalar el atajo', to: '/conectar-dispositivo' },
  },
  {
    id: 'borrar-datos',
    tema: 'privacidad',
    pregunta: '¿Cómo borro mis datos?',
    respuesta: [
      'Puedes borrar todo cuando quieras: **Perfil → Privacidad y datos → Eliminar mi cuenta y mis datos**.',
      'Se borran para siempre tus cuentas, movimientos, presupuestos y metas. No se puede deshacer, así que si quieres una copia, primero toca **Descargar mis datos (Excel)**.',
      'Si solo quieres que CuadraMe deje de leer tu correo, desconecta Gmail y listo: tus movimientos se quedan.',
    ],
    palabras: 'borrar eliminar cuenta datos privacidad descargar exportar salir darme de baja',
    accion: { texto: 'Ir a Privacidad y datos', to: '/perfil' },
  },
  {
    id: 'cuadrar',
    tema: 'entender',
    pregunta: '¿Qué significa «tus cuentas cuadran»?',
    respuesta: [
      'Significa que lo que tienes en tus cuentas alcanza para lo que ya sabes que vas a pagar este mes: tus gastos fijos que faltan y lo que apartas para tus metas.',
      'Si dice «te faltan $X por cuadrar», es lo que haría falta para llegar tranquilo a fin de mes.',
    ],
    palabras: 'cuadran cuadrar puedes gastar hoy disponible alcanza falta',
    accion: { texto: 'Ver mi presupuesto', to: '/presupuesto' },
  },
]

// ── Búsqueda ────────────────────────────────────────────────────────────────

// «extracto» encuentra «Extracto», «extractos» y «¿Dónde saco mi EXTRACTO?»; sin tildes ni signos.
export function normalizar(texto) {
  return String(texto || '')
    .normalize('NFD')
    .replace(/\p{Diacritic}/gu, '')
    .toLowerCase()
    .replace(/[¿?¡!.,;:«»"()]/g, ' ')
    .replace(/\s+/g, ' ')
    .trim()
}

// Quita la «s» final para que «extractos» y «extracto» se parezcan.
const raiz = (p) => (p.length > 3 ? p.replace(/(es|s)$/, '') : p)

const textoPlano = (p) => normalizar([p.pregunta, p.palabras, ...(p.respuesta || [])].join(' '))

/** Preguntas que contienen TODAS las palabras buscadas, las que coinciden en el título primero. */
export function buscarPreguntas(consulta, lista = PREGUNTAS) {
  const palabras = normalizar(consulta).split(' ').filter(Boolean).map(raiz)
  if (palabras.length === 0) return lista
  return lista
    .map((p) => {
      const enTitulo = normalizar(`${p.pregunta} ${p.palabras}`)
      const todo = textoPlano(p)
      if (!palabras.every((w) => todo.includes(w))) return null
      return { p, peso: palabras.every((w) => enTitulo.includes(w)) ? 0 : 1 }
    })
    .filter(Boolean)
    .sort((a, b) => a.peso - b.peso)
    .map((r) => r.p)
}

/** Agrupa por tema respetando el orden de TEMAS. */
export function agruparPorTema(lista) {
  return Object.entries(TEMAS)
    .map(([id, titulo]) => ({ id, titulo, preguntas: lista.filter((p) => p.tema === id) }))
    .filter((g) => g.preguntas.length > 0)
}
