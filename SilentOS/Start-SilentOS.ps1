param(
    [string]$ApiUrl = $env:FLARE_API_URL,
    [int]$Port = 8000,
    [switch]$Stop,
    [switch]$NoBrowser
)

$ErrorActionPreference = 'Stop'
$serverPath = Join-Path $PSScriptRoot 'server.py'
$url = "http://127.0.0.1:$Port"
$listener = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
if ($listener) {
    $serverProcess = Get-CimInstance Win32_Process -Filter "ProcessId = $($listener[0].OwningProcess)"
    if (-not $serverProcess.CommandLine.Contains($serverPath)) {
        throw "Port $Port belongs to another process. Choose a different -Port."
    }
    if ($Stop) {
        Stop-Process -Id $serverProcess.ProcessId
        Write-Host 'SilentOS stopped.'
        exit
    }
    if ($ApiUrl) {
        throw 'SilentOS is already running. Stop it with -Stop before changing -ApiUrl.'
    }
} elseif ($Stop) {
    Write-Host 'SilentOS is already stopped.'
    exit
} else {
    $python = (Get-Command python.exe -ErrorAction Stop).Source
    $arguments = @('-u', ('"{0}"' -f $serverPath), '--port', $Port)
    if ($ApiUrl) {
        if ($ApiUrl -match '["\s]') { throw 'API URL must not contain quotes or whitespace.' }
        $arguments += @('--api-url', $ApiUrl)
    }
    $process = Start-Process -FilePath $python -ArgumentList $arguments -WorkingDirectory $PSScriptRoot -WindowStyle Hidden -RedirectStandardOutput (Join-Path $PSScriptRoot 'server.log') -RedirectStandardError (Join-Path $PSScriptRoot 'server-error.log') -PassThru
    $loaded = $false
    for ($attempt = 0; $attempt -lt 30; $attempt++) {
        if ($process.HasExited) { throw 'Server exited. See server-error.log.' }
        try {
            $null = Invoke-WebRequest -Uri "$url/api/config" -UseBasicParsing -TimeoutSec 1
            $loaded = $true
            break
        } catch { Start-Sleep -Milliseconds 200 }
    }
    if (-not $loaded) { throw 'Server did not respond. See server-error.log.' }
}
Write-Host "SilentOS is running at http://localhost:$Port"
if (-not $NoBrowser) { Start-Process "http://localhost:$Port" }
