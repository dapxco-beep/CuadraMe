import { Check, Compass, Download, EllipsisVertical, Share, SquarePlus } from 'lucide-react'
import Hoja from './Hoja'
import Icono from './Icono'
import { Boton } from './ui'
import { detectarDispositivo } from '../lib/primerUso'
import { instalar, useInstalable } from '../lib/instalarPwa'

// Pasos con dibujo: cada uno muestra el MISMO ícono que la persona verá en su pantalla,
// para que lo reconozca sin tener que entender palabras como «PWA» o «instalar».
const PASOS_IOS = [
  { icono: Compass, titulo: 'Abre CuadraMe en Safari', texto: 'Tiene que ser Safari, el navegador azul con una brújula. En Chrome no aparece la opción.' },
  { icono: Share, titulo: 'Toca el botón Compartir', texto: 'Es un cuadrito con una flecha hacia arriba, abajo en el centro de la pantalla.' },
  { icono: SquarePlus, titulo: 'Elige «Añadir a pantalla de inicio»', texto: 'Desliza el menú hacia arriba si no lo ves.' },
  { icono: Check, titulo: 'Toca «Añadir» y listo', texto: 'Aparece el ícono de CuadraMe en tu pantalla. Ábrela siempre desde ahí.' },
]

const PASOS_ANDROID = [
  { icono: EllipsisVertical, titulo: 'Abre CuadraMe en Chrome y toca los tres puntos', texto: 'Están arriba a la derecha de la pantalla.' },
  { icono: Download, titulo: 'Elige «Instalar app»', texto: 'A veces dice «Añadir a la pantalla de inicio». Es lo mismo.' },
  { icono: Check, titulo: 'Confirma con «Instalar»', texto: 'El ícono de CuadraMe aparece junto a tus demás apps.' },
]

function Lista({ pasos, etiqueta }) {
  return (
    <ol className="space-y-3" aria-label={etiqueta}>
      {pasos.map((p, i) => (
        <li key={p.titulo} className="flex items-start gap-3">
          <span className="w-11 h-11 rounded-2xl bg-accent-soft text-accent flex items-center justify-center shrink-0">
            <Icono icono={p.icono} tam="lg" />
          </span>
          <div className="min-w-0 pt-0.5">
            <p className="t-cuerpo font-semibold">
              <span className="text-ink-soft">{i + 1}. </span>
              {p.titulo}
            </p>
            <p className="t-apoyo mt-0.5">{p.texto}</p>
          </div>
        </li>
      ))}
    </ol>
  )
}

/**
 * Hoja «Ponla en tu celular». Muestra solo los pasos del dispositivo detectado; si no se sabe
 * (computador), muestra los dos y avisa que se hace desde el celular.
 */
export default function GuiaInstalar({ onCerrar, dispositivo = detectarDispositivo() }) {
  const instalable = useInstalable()
  return (
    <Hoja onCerrar={onCerrar} titulo="Ponla en tu celular" testId="guia-instalar">
      {({ cerrar }) => (
        <div>
          <p className="t-apoyo mb-4">
            Así CuadraMe se abre con un toque, sin escribir la dirección, y puede mandarte avisos. No ocupa espacio y no cuesta nada.
          </p>
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
