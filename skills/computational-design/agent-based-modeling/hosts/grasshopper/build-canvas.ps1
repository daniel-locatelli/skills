# Builds the agent-based hexagonal-plate test canvas in a running Grasshopper via Cordyceps (JSON-RPC).
# Usage:  pwsh build-canvas.ps1 [-Port 26929] [-Clear] [-Sphere]
#   -Sphere: use Rhino's Sphere primitive (closed surface with seam + poles) instead of the egg-crate test surface.
# Output: JSON lines with the component ids (saved to ./canvas-ids.json) and the solver report.
param([int]$Port = 26929, [switch]$Clear, [switch]$Sphere)
$ErrorActionPreference = 'Stop'
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$uri = "http://127.0.0.1:$Port/mcp"

function CCall($name, $args_) {
  $payload = @{ jsonrpc='2.0'; id=[int](Get-Random -Maximum 99999); method='tools/call'; params=@{ name=$name; arguments=$args_ } } | ConvertTo-Json -Depth 20 -Compress
  $r = Invoke-RestMethod -Uri $uri -Method POST -Headers @{'Content-Type'='application/json'; 'Accept'='application/json,text/event-stream'} -Body $payload -TimeoutSec 300
  $txt = $r.result.content[0].text
  try { return ($txt | ConvertFrom-Json) } catch { return $txt }
}
function Add($type, $x, $y, $nick) {
  $r = CCall 'gh_canvas' @{ action='add'; type=$type; x=$x; y=$y; nickname=$nick }
  if (-not $r.success) { throw "add $nick failed: $($r | ConvertTo-Json -Compress -AsArray)" }
  return $r.id
}
function Slider($x, $y, $nick, $min, $max, $value, [switch]$Integer) {
  $id = Add 'Number Slider' $x $y $nick
  $cfg = @{ action='config'; id=$id; min=$min; max=$max }
  if ($Integer) { $cfg.integer = $true; $cfg.decimals = 0 } else { $cfg.decimals = 2 }
  CCall 'gh_canvas' $cfg | Out-Null
  CCall 'gh_canvas' @{ action='set'; id=$id; value="$value" } | Out-Null
  return $id
}

$CS = 'b6ba1144-02d6-4a2d-b53c-ec62e290eeb7'   # C# Script (GH 8)
if ($Clear) { CCall 'gh_document' @{ action='clear' } | Out-Null }
CCall 'gh_document' @{ action='solver'; enabled=$false } | Out-Null

# --- test surface -----------------------------------------------------------
if ($Sphere) {
  $sR = Slider 50 50 'R' 1 50 10
  $surf = Add 'dabc854d-f50e-408a-b001-d043c7de151d' 300 60 'Sphere'     # closed: seam in u, poles in v -> SurfaceTopology
  $surfOut = 'S'; $surfWires = @(@{sourceId=$sR; sourceParam='0'; targetId=$surf; targetParam='R'})
} else {
  $sL = Slider 50 50  'L' 5 60 20
  $sH = Slider 50 90  'h' 0 20 3
  $sN = Slider 50 130 'n' 4 60 24 -Integer
  $sP = Slider 50 170 'periods' 1 4 2 -Integer
  $surf = Add $CS 300 60 'TestSurface'
  CCall 'gh_script' @{ action='configure'; id=$surf
    inputs=(@(@{name='L';type='double'},@{name='h';type='double'},@{name='n';type='int'},@{name='periods';type='int'}) | ConvertTo-Json -Compress -AsArray)
    outputs=(@(@{name='surface';type='Surface'}) | ConvertTo-Json -Compress -AsArray)
    code=(Get-Content "$here/TestSurface.cs" -Raw) } | Out-Null
  $surfOut = 'surface'
  $surfWires = @(@{sourceId=$sL; sourceParam='0'; targetId=$surf; targetParam='L'}, @{sourceId=$sH; sourceParam='0'; targetId=$surf; targetParam='h'},
                 @{sourceId=$sN; sourceParam='0'; targetId=$surf; targetParam='n'}, @{sourceId=$sP; sourceParam='0'; targetId=$surf; targetParam='periods'})
}

# --- solver sliders ---------------------------------------------------------
$sCount = Slider 50 240 'count' 4 600 150 -Integer
$sIter  = Slider 50 280 'iterations' 0 3000 1000 -Integer
$sSp    = Slider 50 320 'spacing (0=auto)' 0 10 0
$sWSep  = Slider 50 360 'wSeparation' 0 3 1.0
$sWCoh  = Slider 50 400 'wCohesion' 0 3 0.3
$sWCen  = Slider 50 440 'wCentroid' 0 3 0
$sWAli  = Slider 50 480 'wAlignment' 0 2 0.3
$sSpeed = Slider 50 520 'speed' 0.01 0.5 0.2
$sHex   = Add '2e78987b-9dfb-42a2-8b76-3923ac8bd91a' 50 560 'hexLayout'   # Boolean Toggle
CCall 'gh_canvas' @{ action='set'; id=$sHex; value='true' } | Out-Null
$sHexA  = Slider 50 600 'hexAngle (-1=auto)' -1 60 -1
$sKeepB = Add '2e78987b-9dfb-42a2-8b76-3923ac8bd91a' 50 640 'keepBoundary'
CCall 'gh_canvas' @{ action='set'; id=$sKeepB; value='false' } | Out-Null
$sSeed  = Slider 50 680 'seed' 0 100 1 -Integer

# The core is appended AFTER the adapter's types, so its own `using` lines must go (a `using` after a type
# declaration is CS1529 — and the GH8 script component swallows that error silently: empty `out`, null outputs).
$core = ((Get-Content "$here/../../core/AbmCore.cs") | Where-Object { $_ -notmatch '^\s*using\s+[\w.]+;\s*$' }) -join "`n"
$abm = Add $CS 560 300 'AbmHexPlates'
$inputs = @(
  @{name='srf';type='Surface'}, @{name='count';type='int'}, @{name='iterations';type='int'},
  @{name='spacing';type='double'}, @{name='wSeparation';type='double'}, @{name='wCohesion';type='double'},
  @{name='wCentroid';type='double'}, @{name='wAlignment';type='double'}, @{name='speed';type='double'}, @{name='hexLayout';type='bool'},
  @{name='hexAngle';type='double'}, @{name='keepBoundary';type='bool'}, @{name='seed';type='int'})
$outputs = @(
  @{name='plates';type='Curve'}, @{name='meshes';type='Mesh'}, @{name='agents';type='Point3d'}, @{name='normals';type='Vector3d'}, @{name='e1';type='Vector3d'},
  @{name='gauss';type='double'}, @{name='isConvex';type='bool'}, @{name='kClass';type='int'}, @{name='report';type='string'})
CCall 'gh_script' @{ action='configure'; id=$abm; inputs=($inputs|ConvertTo-Json -Compress -AsArray); outputs=($outputs|ConvertTo-Json -Compress -AsArray)
  code=((Get-Content "$here/AbmHexPlates.cs" -Raw) + "`n" + $core) } | Out-Null

# --- wires ------------------------------------------------------------------
function W($sid, $sp, $tid, $tp) { @{sourceId=$sid; sourceParam="$sp"; targetId=$tid; targetParam=$tp} }
$conns = $surfWires + @(
  (W $surf $surfOut $abm 'srf'),
  (W $sCount 0 $abm 'count'), (W $sIter 0 $abm 'iterations'), (W $sSp 0 $abm 'spacing'),
  (W $sWSep 0 $abm 'wSeparation'), (W $sWCoh 0 $abm 'wCohesion'), (W $sWCen 0 $abm 'wCentroid'), (W $sWAli 0 $abm 'wAlignment'),
  (W $sSpeed 0 $abm 'speed'), (W $sHex 0 $abm 'hexLayout'), (W $sHexA 0 $abm 'hexAngle'), (W $sKeepB 0 $abm 'keepBoundary'), (W $sSeed 0 $abm 'seed'))
$w = CCall 'gh_wire' @{ action='connect'; connections=($conns | ConvertTo-Json -Compress -AsArray) }
# Summary only: the full connect payload names every endpoint and carries one bit of information (all ok).
# Raw JSON for the failures alone, which is what you actually need to debug.
Write-Host "wires: $($w.succeeded)/$($w.total) ok"
if ($w.failed) { Write-Host ($w.results | Where-Object { -not $_.success } | ConvertTo-Json -Compress -Depth 5) }

# report panel
$panel = Add 'Panel' 900 520 'report'
CCall 'gh_wire' @{ action='connect'; connections=(@((W $abm 'report' $panel 0)) | ConvertTo-Json -Compress -AsArray) } | Out-Null

# colour preview: convex plates green, concave red (Dispatch plate meshes on isConvex -> two Custom Previews)
$disp = Add 'Sets/Dispatch' 900 300 'byConvex'
CCall 'gh_wire' @{ action='connect'; connections=(@((W $abm 'meshes' $disp 'L'), (W $abm 'isConvex' $disp 'P')) | ConvertTo-Json -Compress -AsArray) } | Out-Null
$mA = Add 'Params/Mesh' 1050 260 'convexMeshes'
$mB = Add 'Params/Mesh' 1050 360 'concaveMeshes'
CCall 'gh_wire' @{ action='connect'; connections=(@((W $disp 'A' $mA 0), (W $disp 'B' $mB 0)) | ConvertTo-Json -Compress -AsArray) } | Out-Null
CCall 'gh_canvas' @{ action='preview'; id=$mA; enabled=$false } | Out-Null
CCall 'gh_canvas' @{ action='preview'; id=$mB; enabled=$false } | Out-Null
$mjA = Add 'Mesh/Mesh Join' 1050 520 'joinConvex'     # bakeable (one mesh per class) for capture.ps1
$mjB = Add 'Mesh/Mesh Join' 1050 580 'joinConcave'
CCall 'gh_wire' @{ action='connect'; connections=(@((W $mA 0 $mjA 'M'), (W $mB 0 $mjB 'M')) | ConvertTo-Json -Compress -AsArray) } | Out-Null
CCall 'gh_canvas' @{ action='preview'; id=$mjA; enabled=$false } | Out-Null
CCall 'gh_canvas' @{ action='preview'; id=$mjB; enabled=$false } | Out-Null
# plate outlines per class (bakeable, clean in wireframe captures): Dispatch curves -> Flip Curve pass-through
$dispC = Add 'Sets/Dispatch' 900 640 'byConvexCrv'
CCall 'gh_wire' @{ action='connect'; connections=(@((W $abm 'plates' $dispC 'L'), (W $abm 'isConvex' $dispC 'P')) | ConvertTo-Json -Compress -AsArray) } | Out-Null
$fcA = Add 'Curve/Flip Curve' 1050 640 'convexCrv'
$fcB = Add 'Curve/Flip Curve' 1050 700 'concaveCrv'
CCall 'gh_wire' @{ action='connect'; connections=(@((W $dispC 'A' $fcA 'C'), (W $dispC 'B' $fcB 'C')) | ConvertTo-Json -Compress -AsArray) } | Out-Null
CCall 'gh_canvas' @{ action='preview'; id=$fcA; enabled=$false } | Out-Null
CCall 'gh_canvas' @{ action='preview'; id=$fcB; enabled=$false } | Out-Null
# Colours: a Colour Swatch cannot be set through Cordyceps ("Cannot set value on GH_ColourSwatch", stays white), so a
# Panel with "R,G,B" feeds a Colour parameter, which feeds the Custom Preview material.
$swA = Add 'Panel' 1050 200 'green'; CCall 'gh_canvas' @{ action='set'; id=$swA; value='42,157,58' } | Out-Null
$swB = Add 'Panel' 1050 440 'red';   CCall 'gh_canvas' @{ action='set'; id=$swB; value='214,40,40' } | Out-Null
$colA = Add 'Params/Colour' 1150 200 'greenCol'
$colB = Add 'Params/Colour' 1150 440 'redCol'
$pvA = Add 'Display/Custom Preview' 1250 260 'convex'
$pvB = Add 'Display/Custom Preview' 1250 360 'concave'
CCall 'gh_wire' @{ action='connect'; connections=(@((W $swA 0 $colA 0), (W $swB 0 $colB 0), (W $mA 0 $pvA 'G'), (W $colA 0 $pvA 'M'), (W $mB 0 $pvB 'G'), (W $colB 0 $pvB 'M')) | ConvertTo-Json -Compress -AsArray) } | Out-Null

CCall 'gh_document' @{ action='solver'; enabled=$true } | Out-Null
CCall 'gh_document' @{ action='recompute' } | Out-Null

$ids = @{ surface=$surf; abm=$abm; panel=$panel; dispatch=$disp; previewConvex=$pvA; previewConcave=$pvB; meshConvex=$mA; meshConcave=$mB; joinConvex=$mjA; joinConcave=$mjB; crvConvex=$fcA; crvConcave=$fcB
  sphere=[bool]$Sphere
  sliders=@{ L=$sL; h=$sH; n=$sN; periods=$sP; R=$sR; count=$sCount; iterations=$sIter; spacing=$sSp; wSeparation=$sWSep; wCohesion=$sWCoh; wCentroid=$sWCen; wAlignment=$sWAli; speed=$sSpeed; hexLayout=$sHex; hexAngle=$sHexA; keepBoundary=$sKeepB; seed=$sSeed } }
$ids | ConvertTo-Json -Depth 4 | Set-Content "$here/canvas-ids.json"
$info = CCall 'gh_script' @{ action='info'; id=$abm }
Write-Host ("abm runtime: " + $info.runtimeLevel + " " + ($info.messages | ConvertTo-Json -Compress -AsArray))
$out = CCall 'gh_inspect' @{ action='outputs'; id=$abm }
Write-Host ("outputs: " + ($out.outputs | ForEach-Object { "$($_.name)=$($_.count)" }) -join ' ')
Write-Host ("report: " + ($out.outputs | Where-Object name -eq 'report').preview)
