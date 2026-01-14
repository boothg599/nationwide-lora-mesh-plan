# Tier A coverage subtraction for Tier B demand

This note documents the planning-grade rules for subtracting Tier A corridor coverage from Tier B required demand. The intent is to avoid a visual pattern of “one site per hex” in Tier B by crediting Tier A coverage in adjacent cells.

## Rules applied

1. **Tier A covers Tier B required only.** Tier B alternates are never satisfied by Tier A coverage. Sites flagged with `notes="ALT"` remain unchanged.
2. **Coverage model is adjacency ring=1.** A Tier A site satisfies Tier B required demand in its own hex plus any hex that shares a vertex with that hex (touching at a point is sufficient).
3. **No deletions.** Satisfied Tier B required sites are marked in-place with:
   - `status="SATISFIED"`
   - `satisfied_by="<tier A site_id>"`
   - `satisfied_corridor_id="<tier A corridor_id>"`
4. **Audit rollups.** A per-zone CSV report is produced for before/after required counts, alternates, and Tier A site totals.

## Tooling and outputs

Run `tools/apply_tiera_coverage.py` to update `data/sites.geojson` and write `data/tierb_after_tiera_by_zone.csv`.

Outputs:

- **Updated sites data**: Tier B required sites may have status updates and satisfaction metadata.
- **CSV rollup** (`data/tierb_after_tiera_by_zone.csv`):
  - `zone_id`
  - `tierB_required_before`
  - `tierB_required_after`
  - `tierB_alt_total`
  - `tierA_sites`

## Limitations

- Geometry is treated as exact coordinate matching for vertex-touch adjacency. If hex polygons do not share identical vertex coordinates, they will not be considered neighbors.
- The subtraction is deterministic and idempotent: re-running the tool does not re-satisfy already satisfied Tier B required sites.
