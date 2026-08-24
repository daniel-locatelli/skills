# Bakes the plate meshes + outlines (convex / concave) to coloured layers, hides the GH previews and captures Rhino viewports
# into ./captures/.  Usage: pwsh capture.ps1 [-Port 26929] [-Suffix -sphere]   (run after build-canvas.ps1; reads canvas-ids.json)
param([int]$Port = 26929, [string]$Suffix = '')
$ErrorActionPreference = 'Stop'
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$uri = "http://127.0.0.1:$Port/mcp"
function CCall($name, $args_) {
  $payload = @{ jsonrpc='2.0'; id=[int](Get-Random -Maximum 99999); method='tools/call'; params=@{ name=$name; arguments=$args_ } } | ConvertTo-Json -Depth 20 -Compress
  $r = Invoke-RestMethod -Uri $uri -Method POST -Headers @{'Content-Type'='application/json'; 'Accept'='application/json,text/event-stream'} -Body $payload -TimeoutSec 300
  $txt = $r.result.content[0].text
  try { return ($txt | ConvertFrom-Json) } catch { return $txt }
}
$ids = Get-Content "$here/canvas-ids.json" -Raw | ConvertFrom-Json
New-Item -ItemType Directory -Force "$here/captures" | Out-Null

# clean previous bakes, bake again
foreach ($layer in @('abm-convex', 'abm-concave')) {
  $objs = CCall 'rhino_scene' @{ action='objects'; layer=$layer }
  if ($objs.objects -and $objs.objects.Count -gt 0) { CCall 'rhino_scene' @{ action='delete'; ids=(($objs.objects | ForEach-Object { $_.id }) | ConvertTo-Json -Compress -AsArray) } | Out-Null }
}
# Hide every Grasshopper preview (the default dull-red surface/mesh preview z-fights with the plates, which lie on tangent
# planes), then bake plate meshes + outlines per class to coloured layers: Shaded mode then shows green/red plates only.
$all = CCall 'gh_canvas' @{ action='list' }
foreach ($c in $all.components) { CCall 'gh_canvas' @{ action='preview'; id=$c.id; enabled=$false } | Out-Null }
foreach ($pv in @($ids.previewConvex, $ids.previewConcave)) { CCall 'gh_canvas' @{ action='preview'; id=$pv; enabled=$true } | Out-Null }   # the two coloured Custom Previews stay on
# (joinConvex / joinConcave are bakeable too if you want the meshes in the Rhino file: bake them to the same layers.)
CCall 'gh_canvas' @{ action='bake'; id=$ids.crvConvex;   layer='abm-convex' }  | Out-Null   # outlines (visible in wireframe too)
CCall 'gh_canvas' @{ action='bake'; id=$ids.crvConcave;  layer='abm-concave' } | Out-Null
CCall 'rhino_scene' @{ action='layer_set'; name='abm-convex';  color='42,157,58' }  | Out-Null
CCall 'rhino_scene' @{ action='layer_set'; name='abm-concave'; color='214,40,40' } | Out-Null

# no triangulation wires on the preview meshes (Grasshopper.CentralSettings.PreviewMeshEdges; re-applied each run, it is not persisted after a force-kill)
CCall 'rhino_scene' @{ action='script'; cmd='-RunPythonScript (import Grasshopper; Grasshopper.CentralSettings.PreviewMeshEdges = False)' } | Out-Null
CCall 'rhino_render' @{ action='display'; mode='Shaded'; view='Perspective' } | Out-Null
CCall 'rhino_render' @{ action='settings'; style='solid'; colorTop='#FFFFFF' } | Out-Null
CCall 'rhino_render' @{ action='camera'; preset='iso_sw'; view='Perspective' } | Out-Null
CCall 'rhino_render' @{ action='zoom'; view='Perspective' } | Out-Null
$r = CCall 'gh_document' @{ action='capture_viewport'; view='Perspective'; width=1600; height=1000; path="$here/captures/perspective$Suffix.png" }
if ($r.success) { Write-Host "perspective: $($r.viewName) $($r.width)x$($r.height) -> $($r.filePath)" }
else { Write-Host ("perspective FAILED: " + ($r | ConvertTo-Json -Compress)) }
# Plan view: 'camera' RENAMES the viewport to the preset, so driving the active (maximised) viewport to a top
# projection turns it into a second "Top" -- capturing by name is then ambiguous, and the document's own hidden
# Top viewport cannot be captured at all in a maximised layout. Capture the active viewport (no 'view'), then
# put the camera back to iso_sw, which restores the name to Perspective.
CCall 'rhino_render' @{ action='camera'; preset='top'; view='Perspective' } | Out-Null
CCall 'rhino_scene'  @{ action='script'; cmd='-_Zoom _Extents' } | Out-Null
$r = CCall 'gh_document' @{ action='capture_viewport'; width=1200; height=1200; path="$here/captures/top$Suffix.png" }
if ($r.success) { Write-Host "top: $($r.viewName) $($r.width)x$($r.height) -> $($r.filePath)" }
else { Write-Host ("top FAILED: " + ($r | ConvertTo-Json -Compress)) }
CCall 'rhino_render' @{ action='camera'; preset='iso_sw'; view='Top' } | Out-Null
