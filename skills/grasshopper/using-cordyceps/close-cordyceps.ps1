# Closes the Rhino that launch-cordyceps.ps1 started, without any "Save?" prompt.
# The Grasshopper document is a disposable temp copy, so it is saved in place
# (that clears Grasshopper's dirty flag) and the Rhino document is marked
# unmodified; only then is the window asked to close.
#
# Only a Rhino whose command line names a cordyceps-*.gh temp file is touched:
# a Rhino the user opened by hand is never closed by this script.
#
# Usage:
#   pwsh "$env:USERPROFILE\.claude\skills\using-cordyceps\close-cordyceps.ps1"
#   ... -Force   # if a modal dialog still blocks exit, stop the process

[CmdletBinding()]
param(
  [int]   $Port = 26929,
  [int]   $TimeoutSec = 45,
  [switch]$Force
)

Import-Module (Join-Path $PSScriptRoot 'cordyceps.psm1') -Force
if ($Port -ne 26929) { Set-CordycepsPort $Port }

$procs = @(Get-CimInstance Win32_Process -Filter "Name = 'Rhino.exe'" |
  Where-Object { $_.CommandLine -match 'cordyceps-[0-9a-f]{8}\.gh' })
if (-not $procs) { Write-Host "No launcher-started Rhino is running."; exit 0 }

if (Test-Cordyceps) {
  try {
    Assert-CordycepsScript @'
import Rhino, Grasshopper
from Grasshopper.Kernel import GH_DocumentIO
for d in list(Grasshopper.Instances.DocumentServer):
    if d.IsFilePathDefined:
        GH_DocumentIO(d).Save()
Rhino.RhinoDoc.ActiveDoc.Modified = False
'@ | Out-Null
  } catch { Write-Warning "Could not clear the dirty flags: $($_.Exception.Message)" }
} else {
  Write-Warning "Cordyceps is not answering; closing without clearing dirty flags."
}

foreach ($p in $procs) {
  $proc = Get-Process -Id $p.ProcessId -ErrorAction SilentlyContinue
  if (-not $proc) { continue }
  $null = $proc.CloseMainWindow()
  if ($proc.WaitForExit($TimeoutSec * 1000)) { Write-Host "Rhino $($proc.Id) closed cleanly."; continue }
  if ($Force) {
    Stop-Process -Id $proc.Id -Force
    Write-Warning "Rhino $($proc.Id) did not exit within ${TimeoutSec}s (modal dialog?) and was stopped."
  } else {
    Write-Error "Rhino $($proc.Id) did not exit within ${TimeoutSec}s - a dialog is probably open. Re-run with -Force."
    exit 1
  }
}
exit 0
