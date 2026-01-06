$ErrorActionPreference = "Stop"

Write-Host "1) Clip to CONUS boundary"
python tools/clip_hexes_to_conus.py

Write-Host "2) Clip to zones (vertex-touch)"
python tools/clip_hexes_to_zones_by_vertices.py

Write-Host "3) Assign zone_id (vertices-first)"
python tools/assign_zones_to_hexes_vertices_first.py

Write-Host "4) Apply zone-based cell radius"
python tools/set_cell_radius_by_zone.py

Write-Host "5) Force defaults + score"
python tools/scaffold_and_score_hexes_force_defaults.py

Write-Host "6) Report confidence classes"
python tools/check_confidence_classes.py

Write-Host "DONE"
