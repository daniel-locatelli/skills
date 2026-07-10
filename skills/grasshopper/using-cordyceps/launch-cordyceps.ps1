# Launches Rhino with a disposable copy of bootstrap.gh and waits for the
# Cordyceps MCP server on 127.0.0.1:26929. The disposable copy is what
# avoids Grasshopper's "Recover your data" prompt: each session opens a
# fresh unique-name copy, so the autosave can never attach to the
# canonical bootstrap.gh.
#
# Usage from any project:
#   pwsh "$env:USERPROFILE\.claude\skills\using-cordyceps\launch-cordyceps.ps1"

[CmdletBinding()]
param(
  [string]$RhinoExe  = "C:\Program Files\Rhino 8\System\Rhino.exe",
  [string]$Bootstrap = (Join-Path $PSScriptRoot "bootstrap.gh"),
  [int]   $TimeoutSec = 90
)

if (-not (Test-Path $RhinoExe))  { Write-Error "Rhino not found at $RhinoExe";  exit 1 }
if (-not (Test-Path $Bootstrap)) { Write-Error "bootstrap.gh not found at $Bootstrap"; exit 1 }

# Sweep prior session leftovers so GH never offers a stale recovery.
$autosaveDir = Join-Path $env:APPDATA "Grasshopper\AutoSave"
if (Test-Path $autosaveDir) {
  Get-ChildItem $autosaveDir -Filter "cordyceps-*.gh*" -EA SilentlyContinue | Remove-Item -Force
  Get-ChildItem $autosaveDir -Filter "bootstrap*.ghau*" -EA SilentlyContinue | Remove-Item -Force
}

$tmp = Join-Path $env:TEMP ("cordyceps-{0}.gh" -f [guid]::NewGuid().ToString('N').Substring(0,8))
Copy-Item $Bootstrap $tmp -Force

Write-Host "Launching Rhino with $tmp"
Start-Process $RhinoExe -ArgumentList $tmp

$deadline = (Get-Date).AddSeconds($TimeoutSec)
while ((Get-Date) -lt $deadline) {
  try {
    $r = Invoke-WebRequest -Uri 'http://127.0.0.1:26929/mcp' -Method POST `
      -Headers @{'Content-Type'='application/json';'Accept'='application/json,text/event-stream'} `
      -Body '{"jsonrpc":"2.0","id":1,"method":"tools/list","params":{}}' `
      -TimeoutSec 2 -UseBasicParsing -ErrorAction Stop
    if ($r.StatusCode -eq 200) {
      Write-Host "Cordyceps online at http://127.0.0.1:26929/mcp"
      exit 0
    }
  } catch { Start-Sleep -Seconds 2 }
}
Write-Warning "Cordyceps did not respond within ${TimeoutSec}s — Rhino may still be loading; retry the probe in a moment."
exit 0
