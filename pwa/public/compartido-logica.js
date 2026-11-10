// Reglas del «Compartir con CuadraMe» (Android/Chrome). Lógica pura: la usa el service worker
// (importScripts) y las pruebas. Mismos tipos y topes que la subida normal (lib/subidaMultiple.js).
;(function (raiz) {
  var EXT_TABULAR = ['csv', 'txt', 'xlsx', 'xls']
  var MAX_ARCHIVOS = 10
  var MAX_BYTES_PDF = 15 * 1024 * 1024
  var MAX_BYTES_TABULAR = 5 * 1024 * 1024
  var VIGENCIA_MS = 60 * 60 * 1000 // lo compartido y no usado se descarta a la hora

  function tipoDe(nombre) {
    var ext = String(nombre || '').toLowerCase().split('.').pop()
    if (ext === 'pdf') return 'pdf'
    return EXT_TABULAR.indexOf(ext) >= 0 ? 'tabular' : null
  }

  // Devuelve { aceptados, rechazados } (los dos con { name, size }); no se fía del tipo MIME, solo de la extensión.
  function filtrar(archivos) {
    var aceptados = []
    var rechazados = 0
    for (var i = 0; i < archivos.length; i++) {
      var f = archivos[i]
      var tipo = tipoDe(f && f.name)
      var tope = tipo === 'pdf' ? MAX_BYTES_PDF : MAX_BYTES_TABULAR
      if (!tipo || !(f.size > 0) || f.size > tope || aceptados.length >= MAX_ARCHIVOS) rechazados++
      else aceptados.push(f)
    }
    return { aceptados: aceptados, rechazados: rechazados }
  }

  // Solo se acepta si la petición viene de nuestro propio origen (o sin Origin, como hace el sistema al compartir).
  function origenPermitido(origenPeticion, origenPropio) {
    return !origenPeticion || origenPeticion === 'null' ? true : origenPeticion === origenPropio
  }

  function vigente(guardadoEn, ahora) {
    return typeof guardadoEn === 'number' && ahora - guardadoEn >= 0 && ahora - guardadoEn <= VIGENCIA_MS
  }

  var api = { tipoDe: tipoDe, filtrar: filtrar, origenPermitido: origenPermitido, vigente: vigente, MAX_ARCHIVOS: MAX_ARCHIVOS, VIGENCIA_MS: VIGENCIA_MS }
  raiz.CompartidoLogica = api
})(typeof self !== 'undefined' ? self : globalThis)
