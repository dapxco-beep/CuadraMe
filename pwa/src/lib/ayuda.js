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
  traer: 'Traer extractos',
  entender: 'Entender mis números',
  compartir: 'Compartir plata con otros',
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
      'Descárgalo como **PDF** (no como foto ni captura de pantalla) y súbelo en «Traer extractos».',
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
    accion: { texto: 'Traer extractos', to: '/sincronizacion' },
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
  {
    id: 'gasto-tarjeta',
    tema: 'entender',
    pregunta: '¿Cómo registro un gasto con mi tarjeta de crédito?',
    respuesta: [
      'Anota el gasto como cualquier otro y elige tu tarjeta como la cuenta. Así queda lo que debes en la tarjeta.',
      'Cuando le pagues a la tarjeta, no lo anotes como gasto: mira la pregunta de «pagar la tarjeta».',
    ],
    palabras: 'tarjeta credito gasto compra visa deuda cupo',
    accion: { texto: 'Ver mis cuentas', to: '/cuentas' },
  },
  {
    id: 'pagar-tarjeta',
    tema: 'entender',
    pregunta: '¿Cómo registro el pago de mi tarjeta sin que cuente como gasto?',
    respuesta: [
      'Usa **Pasar plata**: elige la cuenta con la que pagas y, como destino, tu tarjeta. Así baja lo que debes y no cuenta como un gasto nuevo, porque ese gasto ya lo anotaste cuando compraste.',
    ],
    palabras: 'pagar tarjeta pago tarjeta abono no cuente gasto doble',
    accion: { texto: 'Ver mis cuentas', to: '/cuentas' },
  },
  {
    id: 'dividir-casa-vaca',
    tema: 'compartir',
    pregunta: '¿Cuál es la diferencia entre Dividir, Parche y Vaca?',
    respuesta: [
      '- **Dividir**: una cuenta que ya se pagó (una cena, un viaje). Repartes y ves quién te debe.',
      '- **Parche**: gastos que se repiten con las mismas personas (la casa, la pareja). Cada quien con su cuenta y un libro común.',
      '- **Vaca**: poner plata entre varios para algo puntual (un regalo, una inscripción) y ver quién ya puso.',
    ],
    palabras: 'dividir parche vaca colecta amigos diferencia casa pareja regalo',
    accion: { texto: 'Plata con otros', to: '/otros' },
  },
  {
    id: 'amigo-sin-cuenta',
    tema: 'compartir',
    pregunta: '¿Mi amigo necesita tener CuadraMe?',
    respuesta: [
      '**Para dividir un gasto, no**: lo agregas con su nombre (y su celular si quieres cobrarle por WhatsApp).',
      '**Para una vaca, no**: abre el enlace que le mandas y marca «Ya pagué».',
      '**Para un parche, sí**: cada persona entra con su cuenta de CuadraMe.',
    ],
    palabras: 'amigo invitar sin cuenta enlace whatsapp registrar necesita',
    accion: { texto: 'Plata con otros', to: '/otros' },
  },
  {
    id: 'cobrar-amigos',
    tema: 'compartir',
    pregunta: '¿Cómo le cobro a quien me debe?',
    respuesta: [
      'Lo que te deben queda en **Dividir gastos**. Ahí tocas «Cobrar por WhatsApp» y se abre el mensaje listo para enviar.',
      'CuadraMe no mueve plata: solo lleva la cuenta. El pago lo hacen entre ustedes por su banco.',
    ],
    palabras: 'cobrar deben deuda amigo whatsapp recordar prestar',
    accion: { texto: 'Plata con otros', to: '/otros' },
  },
  {
    id: 'que-ve-el-otro',
    tema: 'compartir',
    pregunta: '¿Qué ve la otra persona de mis cuentas?',
    respuesta: [
      'Solo las cuentas que tú le compartes, y tú eliges si solo las ve o si también puede anotar. Nada más.',
      'Las puedes dejar de compartir cuando quieras desde Perfil, en «Dar acceso a mis cuentas».',
    ],
    palabras: 'compartir cuentas pareja familia acceso ver privacidad',
    accion: { texto: 'Ir a mi perfil', to: '/perfil' },
  },
  {
    id: 'corregir-movimiento',
    tema: 'entender',
    pregunta: '¿Cómo corrijo o borro un movimiento?',
    respuesta: [
      'Entra a **Movimientos** y toca el que quieres cambiar: ahí lo puedes editar, cambiarle la categoría o borrarlo.',
      'Si lo acabas de guardar, en el aviso de abajo aparece **Deshacer**.',
    ],
    palabras: 'corregir editar borrar eliminar movimiento error categoria cambiar',
    accion: { texto: 'Ir a Movimientos', to: '/movimientos' },
  },
  {
    id: 'salir-de-parche',
    tema: 'compartir',
    pregunta: '¿Puedo salir de un parche?',
    respuesta: [
      'Sí. Entra al parche y toca **Salir**. Ya no verás nada de ese parche; lo que aportaste se conserva para los demás.',
    ],
    palabras: 'salir parche grupo abandonar casa',
    accion: { texto: 'Plata con otros', to: '/otros' },
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
