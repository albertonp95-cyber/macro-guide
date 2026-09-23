# Publicacion semanal, desatendida.
#
#   1. genera el snapshot del ultimo dia con datos
#   2. regenera SOLO esa pagina publica (redactada y verificada)
#   3. rehace el indice con todo lo que hay en site/
#   4. si algo cambio, commit y push; Pages despliega solo
#
# NO TOCA LA TERMINAL BLOOMBERG. El snapshot lee la cache de disco y nunca
# llama a la Desktop API: la extraccion sigue siendo un paso manual y
# deliberado (ver snapshot/bloomberg.py). Consecuencia a tener presente: las
# dos series OAS se van quedando viejas hasta que alguien corra la descarga a
# mano con la terminal abierta. El propio documento marca los datos con mas de
# 40 dias, asi que se ve.
#
# PARA EN SECO si algo falla. Publicar una pagina a medias es peor que no
# publicar: la anterior sigue siendo correcta y no se toca.
#
#   Ejecutar a mano:  powershell -ExecutionPolicy Bypass -File publicar_semanal.ps1
#   Ensayo sin push:  ... -File publicar_semanal.ps1 -SinPush

param([switch]$SinPush)

$ErrorActionPreference = "Stop"
$raiz = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $raiz

$logDir = Join-Path $raiz "logs"
if (-not (Test-Path $logDir)) { New-Item -ItemType Directory $logDir | Out-Null }
$log = Join-Path $logDir ("publicacion-" + (Get-Date -Format "yyyy-MM-dd") + ".log")

function Reg($msg) {
  $linea = "[{0}] {1}" -f (Get-Date -Format "yyyy-MM-dd HH:mm:ss"), $msg
  Add-Content -Path $log -Value $linea -Encoding utf8
  # Write-Host y no Write-Output: dentro de una funcion, lo que va al flujo de
  # salida se convierte en su valor de retorno, asi que las lineas de progreso
  # acababan capturadas por `Corre` y nunca se veian en consola.
  Write-Host $linea
}

function Corre($desc, $exe, $argumentos) {
  Reg "-> $desc"
  $salida = & $exe @argumentos 2>&1
  $salida | ForEach-Object { Add-Content -Path $log -Value ("     " + $_) -Encoding utf8 }
  if ($LASTEXITCODE -ne 0) {
    Reg "FALLO ($desc): codigo $LASTEXITCODE. No se publica nada."
    exit 1
  }
  return $salida
}

# La salida de python trae acentos y el signo ×; sin esto, la consola la
# decodifica con la pagina de codigos OEM y el log queda ilegible justo cuando
# hay que leerlo, que es cuando algo ha fallado.
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$env:PYTHONIOENCODING = "utf-8"
# Sin terminal que conteste: si git pidiera credenciales, mejor que falle en el
# acto y quede en el log que colgarse hasta el timeout de la tarea programada.
$env:GIT_TERMINAL_PROMPT = "0"
Reg "===== publicacion semanal ====="

# 1 y 2. El snapshot del ultimo dia con datos. `build_snapshot` retrocede al
# ultimo dia habil con dato, asi que correr en sabado publica el viernes.
Corre "snapshot" "python" @("run_snapshot.py") | Out-Null

$ultimo = (Get-ChildItem (Join-Path $raiz "output") -Filter "snapshot-????-??-??.html" |
           Sort-Object Name | Select-Object -Last 1).Name -replace 'snapshot-|\.html',''
if (-not $ultimo) { Reg "FALLO: no hay snapshot en output/."; exit 1 }
Reg "   fecha publicada: $ultimo"

# 3. La copia publica. Si la verificacion encuentra una fuga, sale != 0 y el
#    script para aqui: no llega a escribir ni a empujar.
Corre "copia publica" "python" @("publicar_sitio.py", "--fecha", $ultimo) | Out-Null

# 4. Solo si hay cambios reales en site/.
$cambios = & git status --porcelain -- site
if (-not $cambios) { Reg "sin cambios en site/: no hay nada que publicar."; exit 0 }

if ($SinPush) { Reg "ensayo: hay cambios, pero -SinPush impide el push."; exit 0 }

Corre "git add"    "git" @("add", "site") | Out-Null
Corre "git commit" "git" @("commit", "-q", "-m", "Snapshot publicado: $ultimo") | Out-Null
Corre "git push"   "git" @("push", "-q", "origin", "main") | Out-Null
Reg "publicado: https://albertonp95-cyber.github.io/macro-guide/snapshot-$ultimo.html"
Reg "===== fin ====="
