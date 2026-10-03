import { api } from './api'

function urlBase64ToUint8Array(base64String) {
  const padding = '='.repeat((4 - (base64String.length % 4)) % 4)
  const base64 = (base64String + padding).replace(/-/g, '+').replace(/_/g, '/')
  const rawData = atob(base64)
  return Uint8Array.from([...rawData].map((c) => c.charCodeAt(0)))
}

export function pushSoportado() {
  return 'serviceWorker' in navigator && 'PushManager' in window
}

export async function estadoPermiso() {
  if (!pushSoportado()) return 'unsupported'
  return Notification.permission
}

export async function activarPush() {
  if (!pushSoportado()) throw new Error('Este navegador no soporta notificaciones')

  const registration = await navigator.serviceWorker.register('/sw.js')
  await navigator.serviceWorker.ready

  const permiso = await Notification.requestPermission()
  if (permiso !== 'granted') throw new Error('Permiso de notificaciones denegado')

  const { public_key } = await api.pushPublicKey()
  if (!public_key) throw new Error('Notificaciones no configuradas en el servidor')

  const subscription = await registration.pushManager.subscribe({
    userVisibleOnly: true,
    applicationServerKey: urlBase64ToUint8Array(public_key),
  })

  const json = subscription.toJSON()
  await api.pushSuscribir({
    endpoint: json.endpoint,
    p256dh: json.keys.p256dh,
    auth: json.keys.auth,
  })

  return true
}

export async function desactivarPush() {
  if (!pushSoportado()) return
  const registration = await navigator.serviceWorker.getRegistration()
  const subscription = await registration?.pushManager.getSubscription()
  if (subscription) {
    await api.pushDesuscribir(subscription.endpoint)
    await subscription.unsubscribe()
  }
}
