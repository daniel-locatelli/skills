# Closes the Rhino that launch-cordyceps.ps1 started, without any "Save?" prompt.
# The launcher's Grasshopper document is a disposable temp copy, so it is saved
# in place (that clears Grasshopper's dirty flag). Every other open Grasshopper
# document is closed without saving, so a real file opened during the session is
# never overwritten (2026-10-22: the old version saved every open document and
# overwrote three test fixtures). The Rhino document is marked unmodified; only
# then is the window asked to close.
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
import re, Rhino, Grasshopper
from Grasshopper.Kernel import GH_DocumentIO
# Save ONLY the launcher's disposable temp copy. Any other document (a real file opened during the session) is
# closed WITHOUT saving: saving it would overwrite the user's file with the session's edits.
canvas = Grasshopper.Instances.ActiveCanvas
for d in list(Grasshopper.Instances.DocumentServer):
    if d.IsFilePathDefined and re.search(r'cordyceps-[0-9a-f]{8}\.gh$', d.FilePath or ''):
        GH_DocumentIO(d).Save()
    else:
        if canvas is not None and canvas.Document is d:
            canvas.Document = None
        Grasshopper.Instances.DocumentServer.RemoveDocument(d)
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
