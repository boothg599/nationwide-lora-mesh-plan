# GeoJSON layer schema (minimal)

This repo uses four GeoJSON layers:

- `data/zones.geojson` (polygons)
- `data/corridors.geojson` (lines)
- `data/hex_cells.geojson` (polygons / hexes)
- `data/sites.geojson` (points)

All are WGS84 lon/lat (EPSG:4326). Properties are documented in `docs/scoring.md` and enforced (optionally) by JSON Schema in `schemas/`.

## Required IDs
- zone_id: unique
- corridor_id: unique
- cell_id: unique
- site_id: unique

## Foreign keys
- hex_cells.zone_id -> zones.zone_id
- sites.zone_id -> zones.zone_id
- sites.corridor_id -> corridors.corridor_id (required for Tier A)
- sites.cell_id -> hex_cells.cell_id (required for Tier B)
