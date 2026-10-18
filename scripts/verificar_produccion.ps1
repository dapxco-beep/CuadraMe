<#
.SYNOPSIS
  Revisa que produccion este sana. SOLO LECTURA, sin secretos, no cambia nada.

.DESCRIPTION
  1. GET /version y /health del backend (Railway).
  2. version.json de la PWA (Vercel).
  3. Compara que backend y PWA corran el MISMO commit (y, con -Esperado, que sea el que usted despliega).
  4. Con el CLI de Railway cuenta 500 / UndefinedColumn / Traceback en la ultima hora de logs del backend
     (si el CLI no esta enlazado en esta maquina, lo omite y lo dice).
  Sale con codigo 0 si todo bien, 1 si algo fallo. Explica en espanol que fallo.

.EXAMPLE
  powershell -File scripts\verificar_produccion.ps1
  powershell -File scripts\verificar_produccion.ps1 -Esperado 1d3884c
#>
param(
    [string]$Esperado = '',
    [string]$Ventana = '1h'
)

$ErrorActionPreference = 'Continue'
$backend = 'https://backend-production-aeab.up.railway.app'
$pwa = 'https://cuadrame.dapx.shop'
$raiz = Split-Path -Parent $PSScriptRoot
$problemas = @()

function Leer-Json($url) {
    try {
        return Invoke-RestMethod -Uri $url -TimeoutSec 25 -UseBasicParsing -Headers @{ 'Cache-Control' = 'no-cache' }
    } catch {
        return $null
    }
}

# 1) Backend
$ver = Leer-Json "$backend/version"
if ($ver) {
    Write-Host "Backend /version : commit $($ver.commit)  version $($ver.version)  arranque $($ver.arranque_en)"
} else {
    Write-Host 'Backend /version : NO RESPONDE'
    $problemas += "El backend no responde en $backend/version (caido, reiniciando o sin red)."
}
$salud = Leer-Json "$backend/health"
if ($salud -and $salud.ok -eq $true) {
    Write-Host 'Backend /health  : ok'
} else {
    Write-Host 'Backend /health  : FALLA'
    $problemas += 'El backend no contesta {"ok": true} en /health.'
}

# 2) PWA
$vw = Leer-Json "$pwa/version.json"
if ($vw) {
    Write-Host "PWA version.json : commit $($vw.commit)  version $($vw.version)  build $($vw.build)"
} else {
    Write-Host 'PWA version.json : NO RESPONDE'
    $problemas += "La PWA no entrega $pwa/version.json (despliegue de Vercel bloqueado o caido)."
}

# 3) Coinciden
if ($ver -and $vw) {
    $b = "$($ver.commit)"; $p = "$($vw.commit)"
    if ($b -eq 'dev' -or $b -eq '') { $problemas += 'El backend no informa su commit (falta GIT_COMMIT_SHA en Railway).' }
    elseif ($p -eq 'dev' -or $p -eq '') { $problemas += 'La PWA no informa su commit (falta --build-env COMMIT_SHA en Vercel).' }
    elseif (-not ($b.StartsWith($p) -or $p.StartsWith($b))) {
        $problemas += "Backend ($b) y PWA ($p) estan en commits distintos: un despliegue quedo a medias."
    } else {
        Write-Host "Coinciden        : backend y PWA en $b"
    }
    if ($Esperado) {
        $e = $Esperado.Substring(0, [Math]::Min(7, $Esperado.Length))
        if (-not "$b".StartsWith($e)) { $problemas += "El backend corre $b y se esperaba $e (el despliegue del backend no termino o fallo)." }
        if (-not "$p".StartsWith($e)) { $problemas += "La PWA corre $p y se esperaba $e (el despliegue de Vercel no termino, o quedo Blocked por el autor del commit)." }
    }
}

# 4) Logs de Railway (lectura)
function Carpeta-Enlazada {
    $cands = @((Join-Path $raiz 'backend'))
    $comun = (& git -C $raiz rev-parse --path-format=absolute --git-common-dir 2>$null)
    if ($comun) { $cands += (Join-Path (Split-Path -Parent ($comun | Select-Object -First 1)) 'backend') }
    foreach ($c in $cands) {
        if (-not (Test-Path $c)) { continue }
        Push-Location $c
        & railway status *> $null
        $ok = ($LASTEXITCODE -eq 0)
        Pop-Location
        if ($ok) { return $c }
    }
    return $null
}

if (-not (Get-Command railway -ErrorAction SilentlyContinue)) {
    Write-Host 'Logs Railway     : OMITIDO (no esta instalado el CLI "railway")'
} else {
    $dir = Carpeta-Enlazada
    if (-not $dir) {
        Write-Host 'Logs Railway     : OMITIDO (el CLI no esta enlazado; ejecute "railway link" en backend\)'
    } else {
        Push-Location $dir
        $logs = & railway logs --service backend --since $Ventana --lines 2000
        $cod = $LASTEXITCODE
        Pop-Location
        if ($cod -ne 0 -or -not $logs) {
            Write-Host 'Logs Railway     : OMITIDO (no pude leer los logs; revise "railway login")'
        } else {
            $texto = @($logs)
            $n500 = @($texto | Where-Object { $_ -match 'HTTP/\d(\.\d)?"\s+500|Internal Server Error|status[=: ]+500\b' }).Count
            $nCol = @($texto | Where-Object { $_ -match 'UndefinedColumn' }).Count
            $nTb = @($texto | Where-Object { $_ -match 'Traceback' }).Count
            Write-Host "Logs (ultima $Ventana) : $n500 respuestas 500, $nCol UndefinedColumn, $nTb Traceback ($($texto.Count) lineas)"
            if ($nCol -gt 0) { $problemas += "Hay $nCol errores UndefinedColumn: falta una migracion en la base (revise docs/OPERACION.md, trampa de migraciones)." }
            if ($n500 -gt 0) { $problemas += "Hay $n500 respuestas 500 en la ultima $Ventana (en la app se ven como 'Sin conexion'). Revise: railway logs --service backend --since $Ventana" }
            if ($nTb -gt 0 -and $n500 -eq 0 -and $nCol -eq 0) { $problemas += "Hay $nTb Traceback en los logs de la ultima $Ventana." }
        }
    }
}

Write-Host ''
if ($problemas.Count) {
    Write-Host '=== PRODUCCION: HAY PROBLEMAS ===' -ForegroundColor Red
    $problemas | ForEach-Object { Write-Host "- $_" -ForegroundColor Red }
    exit 1
}
Write-Host '=== PRODUCCION: todo bien ===' -ForegroundColor Green
exit 0
