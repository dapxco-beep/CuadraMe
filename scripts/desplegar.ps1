<#
.SYNOPSIS
  Despliega CuadraMe a produccion (backend en Railway, PWA en Vercel) por CLI. NO hace git push.

.DESCRIPTION
  Con -SoloVerificar: corre verificar_todo y verificar_produccion y termina (no despliega nada ni pide confirmacion).
  Sin ese parametro:
    1. Exige escribir DESPLEGAR.
    2. Corre verificar_todo (completo); si algo falla, se detiene.
    3. Crea un commit vacio con el autor del equipo (Vercel deja "Blocked" los commits de otros autores).
    4. Fija GIT_COMMIT_SHA en Railway y sube el backend (railway up).
    5. Despliega la PWA (vercel deploy --prod) con COMMIT_SHA.
    6. Espera y termina con verificar_produccion exigiendo que ambos corran ese commit.
  No lee ni imprime secretos: usa las sesiones ya iniciadas de los CLI (railway login, vercel login).

.PARAMETER SoloVerificar  Solo verifica; no despliega.
.PARAMETER Rapido         Con -SoloVerificar, usa la verificacion rapida (casos_reales + guardianes).
.PARAMETER Confirmacion   Alternativa a escribirlo: -Confirmacion DESPLEGAR (para automatizar).
.PARAMETER PermitirRama   Deja desplegar desde una rama distinta de main.
#>
param(
    [switch]$SoloVerificar,
    [switch]$Rapido,
    [string]$Confirmacion = '',
    [switch]$PermitirRama
)

$ErrorActionPreference = 'Continue'
$raiz = Split-Path -Parent $PSScriptRoot
$scripts = $PSScriptRoot

function Parar($mensaje) {
    Write-Host ''
    Write-Host "DETENIDO: $mensaje" -ForegroundColor Red
    Write-Host 'Si algo quedo a medias, vea docs\OPERACION.md (seccion "Si algo sale mal").' -ForegroundColor Yellow
    exit 1
}

# ── Solo verificar ──
if ($SoloVerificar) {
    Write-Host '== Modo -SoloVerificar: no se despliega nada ==' -ForegroundColor Cyan
    if ($Rapido) { & (Join-Path $scripts 'verificar_todo.ps1') -Rapido } else { & (Join-Path $scripts 'verificar_todo.ps1') }
    $a = $LASTEXITCODE
    & (Join-Path $scripts 'verificar_produccion.ps1')
    $b = $LASTEXITCODE
    if ($a -ne 0 -or $b -ne 0) { exit 1 }
    exit 0
}

# ── Antes de empezar ──
foreach ($cli in 'git', 'railway', 'vercel') {
    if (-not (Get-Command $cli -ErrorAction SilentlyContinue)) { Parar "No esta instalado el CLI '$cli'." }
}
$rama = (& git -C $raiz rev-parse --abbrev-ref HEAD).Trim()
if ($rama -ne 'main' -and -not $PermitirRama) { Parar "Esta en la rama '$rama', no en main. Despliegue desde main (o use -PermitirRama si es a proposito)." }
$sucio = @(& git -C $raiz status --porcelain --untracked-files=no)
if ($sucio.Count) { Parar 'Hay cambios sin commitear en archivos versionados. Haga commit antes de desplegar (lo desplegado debe ser lo probado).' }

Write-Host "Se va a desplegar a PRODUCCION la rama '$rama' en $((& git -C $raiz rev-parse --short HEAD).Trim())." -ForegroundColor Yellow
Write-Host 'Backend: Railway (cuadrame backend)  |  PWA: Vercel (cuadrame.dapx.shop). No se hace git push.'
if ($Confirmacion -eq '') {
    $Confirmacion = Read-Host 'Escriba DESPLEGAR (en mayusculas) para continuar'
}
if ($Confirmacion -cne 'DESPLEGAR') { Parar 'No se escribio DESPLEGAR. No se hizo nada.' }

# ── 1. Verificar todo ──
Write-Host "`n== 1/6 Verificar todo ==" -ForegroundColor Cyan
& (Join-Path $scripts 'verificar_todo.ps1')
if ($LASTEXITCODE -ne 0) { Parar 'Las pruebas fallaron. No se desplego nada.' }

# ── 2. Commit vacio con el autor del equipo ──
Write-Host "`n== 2/6 Commit de despliegue (autor del equipo) ==" -ForegroundColor Cyan
$fecha = Get-Date -Format 'yyyy-MM-dd HH:mm'
& git -C $raiz -c user.name=DAPX -c user.email=dapxco@gmail.com commit --allow-empty -m "Despliegue a produccion $fecha"
if ($LASTEXITCODE -ne 0) { Parar 'No pude crear el commit de despliegue.' }
$sha = (& git -C $raiz rev-parse HEAD).Trim()
$corto = $sha.Substring(0, 7)
Write-Host "Commit a desplegar: $corto"

# ── 3. Backend ──
Write-Host "`n== 3/6 Backend (Railway) ==" -ForegroundColor Cyan
Push-Location (Join-Path $raiz 'backend')
& railway variables --set "GIT_COMMIT_SHA=$sha" --service backend
if ($LASTEXITCODE -ne 0) { Pop-Location; Parar 'No pude fijar GIT_COMMIT_SHA en Railway (railway login / railway link).' }
& railway up --service backend --detach
$cod = $LASTEXITCODE
Pop-Location
if ($cod -ne 0) { Parar 'railway up fallo. El backend sigue en la version anterior.' }

# ── 4. PWA ──
Write-Host "`n== 4/6 PWA (Vercel) ==" -ForegroundColor Cyan
Push-Location (Join-Path $raiz 'pwa')
& vercel deploy --prod --yes --build-env "COMMIT_SHA=$corto"
if ($LASTEXITCODE -ne 0) {
    Write-Host 'Vercel fallo (a veces da "Not authorized" transitorio); reintento una vez...' -ForegroundColor Yellow
    Start-Sleep -Seconds 10
    & vercel deploy --prod --yes --build-env "COMMIT_SHA=$corto"
}
$cod = $LASTEXITCODE
Pop-Location
if ($cod -ne 0) { Parar 'vercel deploy fallo. El backend YA se subio: la PWA sigue en la version anterior.' }

# ── 5-6. Esperar y verificar produccion ──
Write-Host "`n== 5/6 Esperando que Railway termine de construir ==" -ForegroundColor Cyan
$ok = $false
for ($i = 1; $i -le 12; $i++) {
    Start-Sleep -Seconds 30
    Write-Host "-- Intento $i de 12 --"
    & (Join-Path $scripts 'verificar_produccion.ps1') -Esperado $corto
    if ($LASTEXITCODE -eq 0) { $ok = $true; break }
}
Write-Host "`n== 6/6 Resultado ==" -ForegroundColor Cyan
if (-not $ok) { Parar "Produccion no quedo en $corto despues de 6 minutos. Revise los avisos de arriba." }
Write-Host "Desplegado y verificado: $corto. Recuerde: este script NO hizo push; haga git push solo si usted lo decide." -ForegroundColor Green
exit 0
