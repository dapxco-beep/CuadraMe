import { useState } from 'react'
import { FileUp } from 'lucide-react'

/**
 * Zona para subir archivos: tocar para elegir (varios a la vez) o, en escritorio,
 * arrastrar y soltar. Solo avisa con onArchivos(File[]); no valida ni procesa nada.
 */
export default function ZonaSubida({
  onArchivos,
  disabled = false,
  titulo = 'Toca para subir tus extractos',
  ayuda = 'PDF, Excel o CSV · hasta 10 archivos a la vez',
  accept = 'application/pdf,.pdf,.csv,.txt,.xlsx,.xls,text/csv,application/vnd.ms-excel,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
  ariaLabel = 'Archivos a subir',
  icono: Icono = FileUp,
}) {
  const [encima, setEncima] = useState(false)

  function soltar(e) {
    e.preventDefault()
    setEncima(false)
    if (disabled) return
    const archivos = [...(e.dataTransfer?.files || [])]
    if (archivos.length) onArchivos(archivos)
  }

  return (
    <label
      onDragOver={(e) => {
        e.preventDefault()
        if (!disabled) setEncima(true)
      }}
      onDragLeave={() => setEncima(false)}
      onDrop={soltar}
      data-testid="zona-subida"
      className={`w-full flex flex-col items-center justify-center gap-2 rounded-2xl border-2 border-dashed py-10 px-4 text-center ${
        disabled ? 'opacity-60' : 'cursor-pointer'
      } ${encima ? 'border-accent bg-accent-soft' : 'border-line bg-paper-raised'}`}
    >
      <Icono size={28} className="text-accent" />
      <span className="text-sm font-medium">{titulo}</span>
      <span className="text-xs text-ink-soft">{ayuda}</span>
      <span className="text-xs text-ink-soft hidden md:block">o arrástralos y suéltalos aquí</span>
      <input
        type="file"
        multiple
        accept={accept}
        disabled={disabled}
        aria-label={ariaLabel}
        className="hidden"
        onChange={(e) => {
          const archivos = [...(e.target.files || [])]
          e.target.value = ''
          if (archivos.length) onArchivos(archivos)
        }}
      />
    </label>
  )
}
