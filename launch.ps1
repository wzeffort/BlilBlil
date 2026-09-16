$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
$env:PYTHONUTF8 = '1'
$env:TEMP = Join-Path $PSScriptRoot '.setup\tmp'
$env:TMP = $env:TEMP
$env:SE_CACHE_PATH = Join-Path $PSScriptRoot '.setup\selenium'
$env:SE_AVOID_STATS = 'true'
$env:PATH = (Join-Path $PSScriptRoot 'ffmpeg') + ';' + $env:PATH
New-Item -ItemType Directory -Force $env:TEMP, $env:SE_CACHE_PATH, (Join-Path $PSScriptRoot 'logs') | Out-Null
$process = Start-Process -FilePath (Join-Path $PSScriptRoot '.venv\Scripts\pythonw.exe') -ArgumentList 'main.py' -WorkingDirectory $PSScriptRoot -WindowStyle Hidden -RedirectStandardOutput (Join-Path $PSScriptRoot 'logs\app.stdout.log') -RedirectStandardError (Join-Path $PSScriptRoot 'logs\app.stderr.log') -PassThru
$process.Id | Set-Content -LiteralPath (Join-Path $PSScriptRoot 'logs\app.pid')
