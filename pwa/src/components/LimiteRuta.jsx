import { Component } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import ErrorAmable from '../brand/ErrorAmable'
import { reportar } from '../lib/reportarError'

// Límite de error POR PANTALLA. Antes un solo límite en main.jsx envolvía toda la app: si una pantalla
// fallaba al dibujarse, desaparecía todo, incluida la barra de navegación. Este vive DENTRO del shell
// (ShellApp deja afuera el menú), así que si una pantalla falla se ve este aviso y el menú sigue ahí.
// El límite global de main.jsx queda como última red.
function Caida({ onReintentar }) {
  const navigate = useNavigate()
  return (
    <div className="flex-1 flex flex-col items-center justify-center" data-testid="limite-ruta">
      <ErrorAmable
        titulo="Esta pantalla no pudo abrirse"
        texto="Algo falló al mostrarla. Tus datos están a salvo. Puedes reintentar o volver al inicio."
        accion="Reintentar"
        onAccion={onReintentar}
        reportar
        className="flex-none"
      />
      <button type="button" onClick={() => { onReintentar(); navigate('/') }} className="btn btn-suave mt-2 min-h-11">
        Volver al inicio
      </button>
    </div>
  )
}

class LimiteBase extends Component {
  state = { fallo: false }
  static getDerivedStateFromError() {
    return { fallo: true }
  }
  componentDidCatch(error, info) {
    reportar(error, { contexts: { react: { componentStack: info?.componentStack } } })
  }
  reintentar = () => this.setState({ fallo: false })
  render() {
    return this.state.fallo ? <Caida onReintentar={this.reintentar} /> : this.props.children
  }
}

// La `key` es la ruta: al navegar a otra pantalla el límite se reinicia solo.
export default function LimiteRuta({ children }) {
  const { pathname } = useLocation()
  return <LimiteBase key={pathname}>{children}</LimiteBase>
}
