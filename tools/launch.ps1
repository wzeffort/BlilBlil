param([switch]$CheckOnly)

$ErrorActionPreference = 'Stop'
$projectDir = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $projectDir

try {
    # Selenium Manager needs this even when launched from an unusual parent environment.
    if (-not $env:PROCESSOR_ARCHITECTURE) {
        $env:PROCESSOR_ARCHITECTURE = [System.Runtime.InteropServices.RuntimeInformation]::OSArchitecture.ToString().Replace('X64', 'AMD64')
    }
    $env:PYTHONIOENCODING = 'utf-8'
    $candidates = @(
        (Join-Path $projectDir '.venv\Scripts\python.exe'),
        (Join-Path $projectDir 'venv\Scripts\python.exe')
    )
    if ($env:CONDA_PREFIX) {
        $candidates += Join-Path $env:CONDA_PREFIX 'python.exe'
    }
    $condaList = Join-Path $env:USERPROFILE '.conda\environments.txt'
    if (Test-Path -LiteralPath $condaList) {
        $environments = @(Get-Content -LiteralPath $condaList | Where-Object { $_.Trim() })
        # Prefer the existing project environment, without hard-coding a drive or username.
        $environments = $environments | Sort-Object { if ((Split-Path $_ -Leaf) -eq 'mv') { 0 } else { 1 } }
        foreach ($environment in $environments) {
            $candidates += Join-Path $environment.Trim() 'python.exe'
        }
    }
    $pythonCommand = Get-Command python.exe -ErrorAction SilentlyContinue
    if ($pythonCommand -and $pythonCommand.Source -notlike '*\WindowsApps\*') {
        $candidates += $pythonCommand.Source
    }
    $pyCommand = Get-Command py.exe -ErrorAction SilentlyContinue
    if ($pyCommand) {
        try {
            $pyPath = & $pyCommand.Source -3 -c 'import sys; print(sys.executable)' 2>$null
            if ($LASTEXITCODE -eq 0 -and $pyPath) { $candidates += $pyPath.Trim() }
        } catch { }
    }

    $selectedPython = $null
    foreach ($candidate in ($candidates | Select-Object -Unique)) {
        if (-not (Test-Path -LiteralPath $candidate -PathType Leaf)) { continue }
        try {
            & $candidate -c 'import sys; assert sys.version_info >= (3,10); import tkinter, requests, bs4, yt_dlp, selenium, sv_ttk; import main' 2>$null
        } catch { continue }
        if ($LASTEXITCODE -eq 0) {
            $selectedPython = $candidate
            break
        }
    }
    if (-not $selectedPython) {
        throw 'No ready Python 3.10+ environment found. Install Python, then run: python -m pip install -r requirements.txt'
    }
    Write-Host "Python: $selectedPython"
    if ($CheckOnly) {
        Write-Host 'Environment check passed.'
        exit 0
    }

    $windowlessPython = Join-Path (Split-Path $selectedPython -Parent) 'pythonw.exe'
    if (-not (Test-Path -LiteralPath $windowlessPython)) { $windowlessPython = $selectedPython }
    $logDir = Join-Path $env:LOCALAPPDATA 'BlilBlil\logs'
    New-Item -ItemType Directory -Path $logDir -Force | Out-Null
    $logName = (Get-Date -Format 'yyyyMMdd-HHmmss') + '-' + [guid]::NewGuid().ToString('N')
    $errorLog = Join-Path $logDir ($logName + '.error.log')
    $outputLog = Join-Path $logDir ($logName + '.output.log')
    $appProcess = Start-Process -FilePath $windowlessPython -ArgumentList 'main.py' -WorkingDirectory $projectDir -WindowStyle Hidden -RedirectStandardError $errorLog -RedirectStandardOutput $outputLog -PassThru
    Start-Sleep -Seconds 3
    if ($appProcess.HasExited -and $appProcess.ExitCode -ne 0) {
        Get-Content -LiteralPath $errorLog | Write-Host
        throw "Startup failed. Log: $errorLog"
    }
    Write-Host "Started. Log: $errorLog"
    exit 0
} catch {
    Write-Host $_.Exception.Message -ForegroundColor Red
    exit 1
}
