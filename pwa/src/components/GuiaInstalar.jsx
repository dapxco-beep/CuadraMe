import { CheckCircle2, Download } from 'lucide-react'
import Hoja from './Hoja'
import Icono from './Icono'
import { Boton } from './ui'
import { detectarDispositivo } from '../lib/primerUso'
import { instalar, useInstalable } from '../lib/instalarPwa'
import {
  AndroidChrome, AndroidConfirmar, AndroidMenu, IosAnadir, IosCompartir, IosSafari, PantallaInicioConIcono,
} from './IlustracionesGuia'

// Cada paso lleva el DIBUJO de la pantalla que verá la persona, con un círculo que pulsa donde debe tocar,
// para que lo reconozca sin tener que entender palabras como «PWA» o «instalar».
const PASOS_IOS = [
  { Dibujo: IosSafari, titulo: 'Abre CuadraMe en Safari', texto: 'Tiene que ser Safari, el navegador azul con una brújula. En Chrome no aparece la opción.' },
  { Dibujo: IosCompartir, titulo: 'Toca el botón Compartir', texto: 'Es un cuadrito con una flecha hacia arriba, abajo en el centro. Luego elige «Añadir a pantalla de inicio» (desliza el menú hacia arriba si no la ves).' },
  { Dibujo: IosAnadir, titulo: 'Toca «Añadir»', texto: 'Está arriba a la derecha. Puedes dejar el nombre «CuadraMe» como está.' },
  { Dibujo: PantallaInicioConIcono, titulo: '¡Listo! Ábrela desde el ícono', texto: 'Aparece junto a tus demás apps. Ábrela siempre desde ahí: así funciona como una app y te puede mandar avisos.' },
]

const PASOS_ANDROID = [
  { Dibujo: AndroidChrome, titulo: 'Abre CuadraMe en Chrome y toca los tres puntos', texto: 'Están arriba a la derecha de la pantalla.' },
  { Dibujo: AndroidMenu, titulo: 'Elige «Instalar app»', texto: 'A veces dice «Añadir a la pantalla de inicio». Es lo mismo.' },
  { Dibujo: AndroidConfirmar, titulo: 'Confirma con «Instalar»', texto: 'Chrome la instala como cualquier otra app. No descarga archivos ni necesita nada de terceros.' },
  { Dibujo: PantallaInicioConIcono, titulo: '¡Listo! Ábrela desde el ícono', texto: 'El ícono de CuadraMe aparece junto a tus demás apps.' },
]

function Lista({ pasos, etiqueta }) {
  return (
    <ol className="space-y-4" aria-label={etiqueta}>
      {pasos.map((p, i) => (
        <li key={p.titulo} className="flex items-start gap-4">
          <div className="w-[104px] shrink-0">
            <p.Dibujo />
          </div>
          <div className="min-w-0 pt-1">
            <span className="inline-flex w-7 h-7 rounded-full bg-accent text-paper-raised text-sm font-bold items-center justify-center" aria-hidden="true">
              {i + 1}
            </span>
            <p className="t-cuerpo font-semibold mt-1.5">
              <span className="sr-only">Paso {i + 1}: </span>
              {p.titulo}
            </p>
            <p className="t-apoyo mt-1">{p.texto}</p>
          </div>
        </li>
      ))}
    </ol>
  )
}

// ¿Ya se abrió desde el ícono de la pantalla de inicio (como app instalada)?
function yaInstalada() {
  try {
    return window.matchMedia?.('(display-mode: standalone)')?.matches || window.navigator?.standalone === true
  } catch {
    return false
  }
}

/**
 * Hoja «Ponla en tu celular». Muestra solo los pasos del dispositivo detectado; si no se sabe
 * (computador), muestra los dos y avisa que se hace desde el celular.
 */
export default function GuiaInstalar({ onCerrar, dispositivo = detectarDispositivo() }) {
  const instalable = useInstalable()
  const instalada = yaInstalada()
  return (
    <Hoja onCerrar={onCerrar} titulo="Ponla en tu celular" testId="guia-instalar">
      {({ cerrar }) => (
        <div>
          <p className="t-apoyo mb-4">
            Así CuadraMe se abre con un toque, sin escribir la dirección, y puede mandarte avisos. No ocupa espacio y no cuesta nada.
          </p>
          {instalada && (
            <p role="status" data-testid="ya-instalada" className="rounded-2xl bg-cuadra-soft p-3 mb-4 flex items-center gap-2 text-sm font-semibold">
              <Icono icono={CheckCircle2} tam="md" className="text-cuadra shrink-0" /> Ya la tienes instalada: estás usando la app.
            </p>
          )}
          {dispositivo === 'ios' && <Lista pasos={PASOS_IOS} etiqueta="Pasos para iPhone" />}
          {dispositivo === 'android' && instalable && (
            <div className="mb-4">
              <Boton bloque onClick={() => instalar().then((r) => r === 'accepted' && cerrar())} data-testid="instalar-un-toque">
                <Icono icono={Download} tam="md" /> Instalar CuadraMe
              </Boton>
              <p className="t-apoyo mt-2">Un toque y listo: Chrome la instala como una app más. No descarga archivos ni necesita nada de terceros.</p>
            </div>
          )}
          {dispositivo === 'android' && (
            <>
              {instalable && <p className="t-apoyo mb-3">Si prefieres hacerlo a mano:</p>}
              <Lista pasos={PASOS_ANDROID} etiqueta="Pasos para Android" />
            </>
          )}
          {dispositivo === 'otro' && (
            <div className="space-y-5">
              <p className="t-cuerpo rounded-2xl bg-accent-soft p-3">
                Estos pasos se hacen desde tu <b>celular</b>: abre CuadraMe allá con el mismo correo.
              </p>
              <div>
                <h3 className="t-h2 mb-2">iPhone</h3>
                <Lista pasos={PASOS_IOS} etiqueta="Pasos para iPhone" />
              </div>
              <div>
                <h3 className="t-h2 mb-2">Android</h3>
                <Lista pasos={PASOS_ANDROID} etiqueta="Pasos para Android" />
              </div>
            </div>
          )}
          <Boton variante="secundario" bloque className="mt-5" onClick={cerrar}>
            Entendido
          </Boton>
        </div>
      )}
    </Hoja>
  )
}
