import { textoError } from '../lib/textoError'
import { useEffect, useRef, useState } from 'react'
import { useLocation } from 'react-router-dom'
import { FileUp, LifeBuoy, ShieldCheck, Trash2, X } from 'lucide-react'
import { api } from '../lib/api'
import { useDialogos } from '../lib/DialogosContext'
import { VERSION_APP, resumenDispositivo } from '../lib/opinion'
import Hoja from './Hoja'
import Icono from './Icono'
import { Boton, Chip, CampoTexto } from './ui'

export const TEXTO_ENLACE_BANCO = 'Mi banco o billetera no aparece / mi extracto no se lee'
export const MAX_MB = 5
export const EXTENSIONES = ['pdf', 'xls', 'xlsx', 'csv']
export const FORMATOS = [
  { id: 'pdf', etiqueta: 'PDF' },
  { id: 'excel', etiqueta: 'Excel' },
  { id: 'csv', etiqueta: 'CSV' },
  { id: 'correo', etiqueta: 'Correo' },
]

/** Revisa el archivo antes de subirlo. Devuelve el texto del problema o '' si está bien. */
export function problemaDeArchivo(archivo) {
  if (!archivo) return ''
  const ext = String(archivo.name || '').split('.').pop().toLowerCase()
  if (!EXTENSIONES.includes(ext)) return 'Solo recibimos PDF, Excel (xls, xlsx) o CSV. Elige otro archivo o sigue sin archivo.'
  if (archivo.size > MAX_MB * 1024 * 1024) return `El archivo pesa más de ${MAX_MB} MB. Elige uno más pequeño o sigue sin archivo.`
  if (archivo.size === 0) return 'El archivo está vacío. Elige otro o sigue sin archivo.'
  return ''
}

/**
 * «Mi banco o billetera no aparece / mi extracto no se lee»: formulario corto que llega al buzón de opinión
 * como un comentario de tipo «banco». El archivo de muestra es opcional y va a un almacenamiento privado.
 */
export default function BancoNoEsta({ onClose, bancoInicial = '' }) {
  const { avisar } = useDialogos() || {}
  const { pathname } = useLocation()
  const [banco, setBanco] = useState(bancoInicial)
  const [formato, setFormato] = useState('pdf')
  const [archivo, setArchivo] = useState(null)
  const [almacen, setAlmacen] = useState(null) // null = consultando, true/false
  const [enviando, setEnviando] = useState(false)
  const [error, setError] = useState('')
  const [hecho, setHecho] = useState(null) // { id, subido, nombre }
  const entrada = useRef(null)

  useEffect(() => {
    let vigente = true
    Promise.resolve(api.almacenMuestras?.())
      .then((r) => vigente && setAlmacen(!!r?.disponible))
      .catch(() => vigente && setAlmacen(false))
    return () => {
      vigente = false
    }
  }, [])

  function elegirArchivo(e) {
    const f = e.target.files?.[0] || null
    const problema = problemaDeArchivo(f)
    if (problema) {
      setArchivo(null)
      setError(problema)
      if (entrada.current) entrada.current.value = ''
      return
    }
    setError('')
    setArchivo(f)
  }

  async function enviar(e) {
    e.preventDefault()
    setError('')
    if (!banco.trim()) return setError('Escribe el nombre de tu banco o billetera. Por ejemplo «Banco Agrario».')
    setEnviando(true)
    let id
    try {
      const r = await api.enviarComentario({
        tipo: 'banco',
        banco: banco.trim(),
        tipo_archivo: formato,
        mensaje: '',
        pantalla: pathname,
        version_app: VERSION_APP || null,
        dispositivo: resumenDispositivo() || null,
        puede_contactar: true,
      })
      id = r.id
    } catch (err) {
      setEnviando(false)
      return setError(textoError(err, 'enviar tu aviso'))
    }
    let subido = false
    if (archivo && almacen) {
      try {
        await api.subirMuestraBanco(id, archivo)
        subido = true
      } catch (err) {
        avisar?.(`Recibimos el nombre de tu banco, pero no pudimos subir el archivo. ${err.message || ''}`.trim(), 'info')
      }
    }
    setEnviando(false)
    setHecho({ id, subido, nombre: archivo?.name || '' })
  }

  async function borrar() {
    try {
      await api.borrarMuestraBanco(hecho.id)
      setHecho((h) => ({ ...h, subido: false }))
      avisar?.('Listo: borramos tu archivo.', 'info')
    } catch (err) {
      avisar?.(err.message || 'No pudimos borrar el archivo. Intenta de nuevo en un momento.')
    }
  }

  return (
    <Hoja onCerrar={onClose} ariaLabel="Mi banco o billetera no aparece">
      <div className="flex items-start justify-between gap-3 mb-3">
        <h2 className="text-lg font-semibold">Mi banco no aparece</h2>
        <button onClick={onClose} className="w-11 h-11 -mt-1 rounded-full bg-paper-raised border border-line flex items-center justify-center shrink-0" aria-label="Cerrar">
          <X size={16} />
        </button>
      </div>

      {hecho ? (
        <div role="status" data-testid="banco-gracias">
          <p className="text-sm font-semibold">¡Gracias! Ya tenemos el nombre de tu banco.</p>
          <p className="text-sm text-ink-soft mt-1">
            Lo miramos para que CuadraMe lo entienda. Puedes ver cómo va en «Tu opinión cuenta».
          </p>
          {hecho.subido && (
            <div className="mt-3 flex items-center justify-between gap-3 rounded-xl bg-paper border border-line px-3 py-2">
              <span className="text-xs text-ink-soft truncate">Archivo enviado: {hecho.nombre}</span>
              <Boton variante="suave" tam="sm" icono={Trash2} onClick={borrar} aria-label={`Borrar el archivo ${hecho.nombre}`}>
                Borrar
              </Boton>
            </div>
          )}
          {!hecho.subido && archivo && (
            <p className="text-xs text-ink-soft mt-3">El archivo no se guardó. Con el nombre de tu banco ya podemos empezar.</p>
          )}
          <Boton bloque className="mt-4" onClick={onClose}>Listo</Boton>
        </div>
      ) : (
        <form onSubmit={enviar} noValidate>
          <p className="text-sm text-ink-soft mb-4">
            Cuéntanos cuál es y lo agregamos. Solo toma un minuto.
          </p>

          <CampoTexto
            etiqueta="¿Cómo se llama tu banco o billetera?"
            value={banco}
            onChange={(e) => setBanco(e.target.value)}
            maxLength={80}
            placeholder="Ej. Banco Agrario"
            className="mb-4"
          />

          <p id="formato-banco" className="campo-etiqueta">¿Cómo te llegan tus movimientos?</p>
          <div role="radiogroup" aria-labelledby="formato-banco" className="grid grid-cols-4 gap-2 mb-4">
            {FORMATOS.map((f) => (
              <Chip key={f.id} rol="radio" activo={formato === f.id} onClick={() => setFormato(f.id)} className="justify-center">
                {f.etiqueta}
              </Chip>
            ))}
          </div>

          {almacen === false ? (
            <p className="text-xs text-ink-soft rounded-xl bg-accent-soft p-3 mb-4" role="note">
              Por ahora no podemos recibir archivos. Guardaremos solo el nombre de tu banco y te escribimos si necesitamos algo más.
            </p>
          ) : (
            <div className="rounded-2xl border border-line bg-paper-raised p-3.5 mb-4" data-testid="muestra-banco">
              <p className="text-sm font-semibold flex items-center gap-2">
                <Icono icono={FileUp} tam="sm" className="text-accent" /> Un archivo de muestra (opcional)
              </p>
              <p className="text-xs text-ink-soft mt-1 flex gap-2">
                <Icono icono={ShieldCheck} tam="sm" className="text-accent shrink-0" />
                <span>
                  Puedes borrar los datos personales antes. Solo se usa para que CuadraMe lo entienda; nadie más lo ve y lo puedes
                  borrar cuando quieras.
                </span>
              </p>
              <label className="block mt-3">
                <span className="campo-etiqueta">PDF, Excel o CSV (máximo {MAX_MB} MB)</span>
                <input
                  ref={entrada}
                  type="file"
                  accept=".pdf,.xls,.xlsx,.csv"
                  onChange={elegirArchivo}
                  className="block w-full text-sm min-h-11"
                />
              </label>
              {archivo && (
                <p className="text-xs text-ink-soft mt-1 truncate">Elegiste: {archivo.name}</p>
              )}
              <p className="text-xs text-ink-soft mt-2">¿Prefieres no subir nada? Toca «Enviar» sin elegir un archivo.</p>
            </div>
          )}

          {error && <p role="alert" className="text-sm text-danger mb-3">{error}</p>}

          <Boton type="submit" bloque cargando={enviando}>
            {enviando ? 'Enviando...' : 'Enviar'}
          </Boton>
        </form>
      )}
    </Hoja>
  )
}

/** Enlace discreto que abre el formulario. `bancoInicial` rellena el nombre si ya se sabe. */
export function EnlaceBancoNoEsta({ bancoInicial = '', className = '' }) {
  const [abierto, setAbierto] = useState(false)
  return (
    <>
      <button
        type="button"
        onClick={() => setAbierto(true)}
        className={`flex items-center gap-2 text-sm font-semibold text-accent min-h-11 text-left ${className}`}
      >
        <Icono icono={LifeBuoy} tam="sm" className="shrink-0" /> {TEXTO_ENLACE_BANCO}
      </button>
      {abierto && <BancoNoEsta bancoInicial={bancoInicial} onClose={() => setAbierto(false)} />}
    </>
  )
}
