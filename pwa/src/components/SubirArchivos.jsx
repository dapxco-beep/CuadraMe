import { useEffect, useState } from 'react'
import { useCuentas } from '../lib/CuentasContext'
import { nombreMes } from '../lib/sincronizacion'
import Hoja from './Hoja'
import CambiarCuentaExtracto from './CambiarCuentaExtracto'
import SubidaMultiple from './SubidaMultiple'
import ZonaSubida from './ZonaSubida'
import ImportarArchivo from '../screens/ImportarArchivo'

/**
 * Una sola zona para PDF, Excel y CSV (varios a la vez): la extensión decide el lector. Con
 * archivos elegidos entra la cola con revisión consolidada; con `revision` abre la revisión de
 * un extracto ya procesado (viene de un correo, un enlace o una notificación).
 *   inicial: { historialId, cuentaId, mes, manual, n }  (n cambia cada vez que se pide abrir otra cosa)
 */
export default function SubirArchivos({ inicial = {}, onImportado }) {
  const { cuentas, recargar: recargarCuentas } = useCuentas()
  const [cambiandoCuenta, setCambiandoCuenta] = useState(null) // { historialId, titulo, cuentaId } desde la revisión
  const [archivos, setArchivos] = useState(null) // File[] | null
  const [revision, setRevision] = useState(null) // { historialId, cuentaId } | null
  const [manual, setManual] = useState(false)
  const [version, setVersion] = useState(0) // remonta la subida al volver a empezar

  // Lo que pidió quien llegó por una ruta vieja o por un botón de otro bloque.
  useEffect(() => {
    if (inicial.historialId) {
      setArchivos(null)
      setRevision({ historialId: inicial.historialId, cuentaId: inicial.cuentaId || '' })
      setVersion((v) => v + 1)
    }
    if (inicial.manual) setManual(true)
  }, [inicial.n]) // eslint-disable-line react-hooks/exhaustive-deps

  const cuentaPedida = cuentas.find((c) => c.id === inicial.cuentaId)
  const volver = () => {
    setArchivos(null)
    setRevision(null)
    setVersion((v) => v + 1)
  }

  return (
    <div>
      {inicial.mes && !archivos && !revision && (
        <p role="status" className="rounded-2xl bg-accent-soft text-sm font-medium px-4 py-3 mb-3">
          Sube el extracto de <span className="capitalize">{nombreMes(inicial.mes)}</span>
          {cuentaPedida ? ` de ${cuentaPedida.nombre}` : ''}.
        </p>
      )}

      {!archivos && !revision && (
        <>
          <ZonaSubida
            onArchivos={setArchivos}
            titulo="Toca para subir tus archivos"
            ayuda="PDF, Excel o CSV · varios a la vez"
            ariaLabel="Archivos a subir"
          />
          <button onClick={() => setManual(true)} className="mt-3 text-xs font-semibold text-accent underline min-h-[32px]">
            Excel o CSV raro: elegir las columnas a mano
          </button>
        </>
      )}

      {(archivos || revision) && (
        <SubidaMultiple
          key={version}
          archivosIniciales={archivos || []}
          cuentaInicial={inicial.cuentaId || ''}
          revisionInicial={revision}
          onCancelar={volver}
          onImportado={onImportado}
          onManual={() => setManual(true)}
          onCambiarCuenta={setCambiandoCuenta}
        />
      )}

      {cambiandoCuenta && (
        <CambiarCuentaExtracto
          historialId={cambiandoCuenta.historialId}
          titulo={cambiandoCuenta.titulo}
          cuentaActualId={cambiandoCuenta.cuentaId}
          cuentas={cuentas}
          onCerrar={() => setCambiandoCuenta(null)}
          onListo={() => {
            // Se reabre la misma revisión: ahora dice la cuenta nueva.
            recargarCuentas?.()
            setCambiandoCuenta(null)
            setVersion((v) => v + 1)
            onImportado?.([])
          }}
        />
      )}

      {manual && (
        <Hoja onCerrar={() => setManual(false)} titulo="Elegir columnas a mano" clasePanel="p-0 pb-6" capa="z-50">
          {({ cerrar }) => (
            <>
              <h2 className="px-5 pt-5 text-lg font-semibold">Elegir columnas a mano</h2>
              <ImportarArchivo
                embebido
                cuentaInicial={inicial.cuentaId || ''}
                onTerminar={() => {
                  onImportado?.([])
                  cerrar()
                }}
              />
            </>
          )}
        </Hoja>
      )}
    </div>
  )
}
