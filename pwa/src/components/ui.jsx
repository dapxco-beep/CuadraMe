import { Link } from 'react-router-dom'
import { useId } from 'react'
import { AlertCircle } from 'lucide-react'
import Icono from './Icono'
import InputMonto from './InputMonto'

// Piezas básicas del sistema de diseño. Solo componen las clases de index.css
// (.btn, .chip, .tarjeta, .campo-*) para que hover, foco y deshabilitado sean iguales en toda la app.

const junta = (...c) => c.filter(Boolean).join(' ')

// <Boton> es un <button>; con `to` es un <Link>. variante: primario | secundario | suave | fantasma | peligro
export function Boton({ variante = 'primario', tam, bloque, icono, cargando, to, className, children, disabled, ...resto }) {
  const clase = junta('btn', `btn-${variante}`, tam === 'sm' && 'btn-sm', bloque && 'btn-bloque', className)
  const contenido = (
    <>
      {icono && <Icono icono={icono} tam="sm" />}
      {children}
    </>
  )
  if (to) {
    return (
      <Link to={to} className={clase} {...resto}>
        {contenido}
      </Link>
    )
  }
  return (
    <button type="button" className={clase} disabled={disabled || cargando} aria-busy={cargando || undefined} {...resto}>
      {contenido}
    </button>
  )
}

// Chip de filtro/opción: `activo` marca aria-pressed (o aria-checked si es parte de un radiogroup)
export function Chip({ activo, icono, className, children, rol, ...resto }) {
  const aria = rol === 'radio' ? { role: 'radio', 'aria-checked': !!activo } : { 'aria-pressed': !!activo }
  return (
    <button type="button" className={junta('chip', className)} {...aria} {...resto}>
      {icono && <Icono icono={icono} tam="sm" />}
      {children}
    </button>
  )
}

// Tarjeta: una sola superficie. variante: plana | suave | lista (filas separadas por líneas)
export function Tarjeta({ variante = 'plana', as: Etiqueta = 'div', className, children, ...resto }) {
  const base = { plana: 'tarjeta', suave: 'tarjeta-suave', lista: 'tarjeta-lista' }[variante] || 'tarjeta'
  return (
    <Etiqueta className={junta(base, className)} {...resto}>
      {children}
    </Etiqueta>
  )
}

// Campo de formulario: etiqueta VISIBLE arriba, ayuda y error pegados al campo.
// Pasa el <input> como hijo con `props` (id, aria-describedby, aria-invalid) mediante render-prop,
// o usa `CampoTexto` para el caso normal.
export function Campo({ etiqueta, error, ayuda, children, className }) {
  const id = useId()
  const idAyuda = ayuda ? `${id}-ayuda` : undefined
  const idError = error ? `${id}-error` : undefined
  const describedby = [idAyuda, idError].filter(Boolean).join(' ') || undefined
  return (
    <div className={className}>
      <label htmlFor={id} className="campo-etiqueta">
        {etiqueta}
      </label>
      {children({ id, 'aria-describedby': describedby, 'aria-invalid': error ? true : undefined, className: 'campo-entrada' })}
      {ayuda && !error && (
        <p id={idAyuda} className="campo-ayuda">
          {ayuda}
        </p>
      )}
      {error && (
        <p id={idError} role="alert" className="campo-error">
          <Icono icono={AlertCircle} tam="sm" />
          <span>{error}</span>
        </p>
      )}
    </div>
  )
}

// Campo de monto: etiqueta visible + miles en vivo (valor canónico, ver lib/monto.js).
export function CampoMonto({ etiqueta, error, ayuda, className, entero = false, ...input }) {
  return (
    <Campo etiqueta={etiqueta} error={error} ayuda={ayuda} className={className}>
      {(props) => <InputMonto {...props} entero={entero} {...input} />}
    </Campo>
  )
}

export function CampoTexto({ etiqueta, error, ayuda, className, ...input }) {
  return (
    <Campo etiqueta={etiqueta} error={error} ayuda={ayuda} className={className}>
      {(props) => <input {...props} {...input} />}
    </Campo>
  )
}
