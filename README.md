# mesh-plan

Planning artifacts for a US-scale nationwide LoRa mesh operability model (Meshtastic + MeshCore).

## Structure
- `data/`    GeoJSON layers (editable)
- `docs/`    Human-readable schema + scoring notes
- `schemas/` JSON Schemas for validation (optional but CI-friendly)

## Quick start
1. Edit `data/zones.geojson` polygons (3 macro zones).
2. Edit `data/corridors.geojson` lines (10–15 corridor proxies).
3. Generate/commit `data/hex_cells.geojson` (hex overlay), then set cell flags.
4. Add candidate sites in `data/sites.geojson`.

## Conventions
- CRS: WGS84 (`EPSG:4326`) lon/lat
- GeoJSON `FeatureCollection` only
- IDs must be unique within each layer.

See `docs/schema.md` and `docs/scoring.md`.
