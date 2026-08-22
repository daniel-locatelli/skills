# Cordyceps JSON-RPC helper.
#   Import-Module "$env:USERPROFILE\.claude\skills\using-cordyceps\cordyceps.psm1"
#
# Exists so driver scripts and ad-hoc calls stop re-declaring the same six-line CCall helper.
# Every function returns a PARSED object (not the raw text), so callers can test .success.

$script:CcPort = 26929

function Set-CordycepsPort {
    param([Parameter(Mandatory)][int]$Port)
    $script:CcPort = $Port
}

function Invoke-Cordyceps {
    <#
      .SYNOPSIS  Call one Cordyceps tool action.
      .EXAMPLE   CCall gh_canvas @{ action='help' }
      .EXAMPLE   CCall gh_document @{ action='info' } -Port 26930
    #>
    param(
        [Parameter(Mandatory, Position = 0)][string]$Tool,
        [Parameter(Position = 1)][hashtable]$Arguments = @{},
        [int]$Port = 0,
        [int]$TimeoutSec = 300
    )
    $p = if ($Port) { $Port } else { $script:CcPort }
    $payload = @{
        jsonrpc = '2.0'; id = [int](Get-Random -Maximum 99999)
        method  = 'tools/call'; params = @{ name = $Tool; arguments = $Arguments }
    } | ConvertTo-Json -Depth 20 -Compress
    $r = Invoke-RestMethod -Uri "http://127.0.0.1:$p/mcp" -Method POST -TimeoutSec $TimeoutSec `
        -Headers @{ 'Content-Type' = 'application/json'; 'Accept' = 'application/json,text/event-stream' } `
        -Body $payload
    $txt = $r.result.content[0].text
    try { return ($txt | ConvertFrom-Json) } catch { return $txt }
}

function Read-CordycepsDoc {
    <# .EXAMPLE  Read-CordycepsDoc gh://docs/rendering #>
    param(
        [Parameter(Mandatory, Position = 0)][string]$Uri,
        [int]$Port = 0
    )
    $p = if ($Port) { $Port } else { $script:CcPort }
    $payload = @{ jsonrpc = '2.0'; id = 1; method = 'resources/read'; params = @{ uri = $Uri } } |
        ConvertTo-Json -Depth 10 -Compress
    $r = Invoke-RestMethod -Uri "http://127.0.0.1:$p/mcp" -Method POST -TimeoutSec 60 `
        -Headers @{ 'Content-Type' = 'application/json'; 'Accept' = 'application/json,text/event-stream' } `
        -Body $payload
    return $r.result.contents[0].text
}

function Test-Cordyceps {
    <# Is the server answering? Returns $true/$false, never throws. #>
    param([int]$Port = 0)
    try { $null = Invoke-Cordyceps 'gh_document' @{ action = 'info' } -Port $Port -TimeoutSec 8; $true }
    catch { $false }
}

function Assert-CordycepsScript {
    <#
      .SYNOPSIS  Run a Rhino Python script and PROVE it ran.
      .DESCRIPTION
        rhino_scene script returns success:true regardless of what the script did — it only queues the command
        string. A failing script parks a MODAL dialog in Rhino that blocks the UI until a human dismisses it.
        This wrapper appends a witness write and checks for the file, so a silent failure surfaces as an error
        here instead of as a hung session.

        The call itself is SYNCHRONOUS — measured: a script sleeping 4s blocked the HTTP call for 4.2s. So
        GraceMs is only a short settle window after the call returns, NOT a budget for the script's runtime;
        a long-running script will not false-throw.
      .EXAMPLE
        Assert-CordycepsScript "import Grasshopper; Grasshopper.CentralSettings.PreviewMeshEdges = False"
    #>
    param(
        [Parameter(Mandatory, Position = 0)][string]$Body,
        [int]$Port = 0,
        [int]$GraceMs = 2000
    )
    $witness = Join-Path ([IO.Path]::GetTempPath()) ("cc-witness-{0}.txt" -f [int](Get-Random -Maximum 999999))
    $file    = Join-Path ([IO.Path]::GetTempPath()) ("cc-script-{0}.py"  -f [int](Get-Random -Maximum 999999))
    @"
$Body
_f = open(r'$witness', 'w'); _f.write('ok'); _f.close()
"@ | Set-Content -Path $file -Encoding UTF8
    Invoke-Cordyceps 'rhino_scene' @{ action = 'script'; cmd = "-_RunPythonScript `"$file`"" } -Port $Port | Out-Null
    $sw = [Diagnostics.Stopwatch]::StartNew()
    do {
        if (Test-Path $witness) { Remove-Item $witness, $file -ErrorAction SilentlyContinue; return $true }
        Start-Sleep -Milliseconds 150
    } while ($sw.ElapsedMilliseconds -lt $GraceMs)
    throw "Rhino script did not complete — it most likely raised an error, which parks a MODAL dialog in Rhino that blocks the UI until someone dismisses it. Check Rhino now. Script kept at: $file"
}

Set-Alias CCall Invoke-Cordyceps
Export-ModuleMember -Function Invoke-Cordyceps, Read-CordycepsDoc, Test-Cordyceps, Assert-CordycepsScript, Set-CordycepsPort -Alias CCall
