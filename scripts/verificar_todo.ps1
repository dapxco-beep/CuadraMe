<#
.SYNOPSIS
  Verifica CuadraMe de punta a punta: pruebas del backend y de la PWA. Sale con codigo distinto de 0 si algo falla.

.DESCRIPTION
  Completo : pytest de todo backend/tests + vitest de toda la PWA (3-5 min).
  -Rapido  : solo backend/tests/casos_reales + los guardianes (contabilidad, migraciones congeladas, 500 con CORS).
             Tarda unos segundos; sirve antes de cada commit.

  Solo lee y prueba: no toca produccion, no usa secretos, no hace push.

.EXAMPLE
  powershell -File scripts\verificar_todo.ps1 -Rapido
  powershell -File scripts\verificar_todo.ps1
#>
param([switch]$Rapido)

$ErrorActionPreference = 'Continue'
$raiz = Split-Path -Parent $PSScriptRoot
$fallos = @()
$resumen = @()

function Buscar-Python {
    # 1) variable explicita, 2) venv de este repo, 3) venv del repo principal (un worktree no trae venv propio).
    $candidatos = @()
    if ($env:CUADRAME_PYTHON) { $candidatos += $env:CUADRAME_PYTHON }
    $candidatos += (Join-Path $raiz 'backend\venv\Scripts\python.exe')
    $comun = (& git -C $raiz rev-parse --path-format=absolute --git-common-dir 2>$null)
    if ($comun) {
        $principal = Split-Path -Parent ($comun | Select-Object -First 1)
        $candidatos += (Join-Path $principal 'backend\venv\Scripts\python.exe')
    }
    foreach ($c in $candidatos) { if ($c -and (Test-Path $c)) { return $c } }
    return $null
}

function Ultima-Linea($lineas, $patron) {
    $m = @($lineas | Where-Object { $_ -match $patron })
    if ($m.Count) { return ($m[-1] -replace '\x1b\[[0-9;]*m', '').Trim() }
    return $null
}

# ── Backend ──
$py = Buscar-Python
if (-not $py) {
    $fallos += 'Backend: no encuentro el venv de Python (backend\venv). Defina CUADRAME_PYTHON con la ruta de python.exe.'
    $resumen += 'BACKEND  FALLO  sin venv de Python'
} else {
    Push-Location (Join-Path $raiz 'backend')
    if ($Rapido) {
        $objetivos = @('tests/casos_reales', 'tests/test_guardian_contabilidad.py', 'tests/test_columnas_de_arranque.py', 'tests/test_errores_500_cors.py')
    } else {
        $objetivos = @('tests')
    }
    Write-Host ">> Backend: pytest $($objetivos -join ' ')" -ForegroundColor Cyan
    $salida = & $py -m pytest @objetivos -q -p no:warnings -p no:cacheprovider
    $codigo = $LASTEXITCODE
    Pop-Location
    $linea = Ultima-Linea $salida '(passed|failed|error)'
    if ($codigo -eq 0) {
        $resumen += "BACKEND  OK     $linea"
    } else {
        $salida | Select-Object -Last 40 | ForEach-Object { Write-Host $_ }
        $resumen += "BACKEND  FALLO  $linea"
        $fallos += 'Backend: fallaron pruebas (ver arriba).'
    }
}

# ── PWA ──
if ($Rapido) {
    $resumen += 'PWA      OMITIDA (modo -Rapido)'
} else {
    Push-Location (Join-Path $raiz 'pwa')
    if (-not (Test-Path 'node_modules')) {
        $resumen += 'PWA      FALLO  falta pwa\node_modules (npm ci)'
        $fallos += 'PWA: no hay node_modules. Ejecute "npm ci" dentro de pwa.'
    } else {
        Write-Host '>> PWA: npx vitest run' -ForegroundColor Cyan
        $salida = cmd /c 'npx vitest run 2>&1'
        $codigo = $LASTEXITCODE
        $linea = Ultima-Linea $salida '^\s*Tests\s'
        if ($codigo -eq 0) {
            $resumen += "PWA      OK     $linea"
        } else {
            $salida | Select-Object -Last 40 | ForEach-Object { Write-Host $_ }
            $resumen += "PWA      FALLO  $linea"
            $fallos += 'PWA: fallaron pruebas (ver arriba).'
        }
    }
    Pop-Location
}

Write-Host ''
Write-Host '=== RESUMEN ===' -ForegroundColor Cyan
$resumen | ForEach-Object { Write-Host $_ }
if ($fallos.Count) {
    Write-Host ''
    $fallos | ForEach-Object { Write-Host "FALLO: $_" -ForegroundColor Red }
    exit 1
}
Write-Host 'Todo en verde.' -ForegroundColor Green
exit 0
