#!/usr/bin/env python3
"""
Seed Tier B candidate sites from scored hexes.

Reads:
  - data/hex_cells.geojson

Writes:
  - data/sites.geojson (Tier B CANDIDATE features appended or replaced; see mode)
  - data/tierb_requirements_by_zone.csv

Design goals:
  - stdlib-only
  - deterministic output
  - schema-friendly fields and conservative defaults
"""

import csv
import json
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

HEX_PATH = Path("data/hex_cells.geojson")
SITES_PATH = Path("data/sites.geojson")
OUT_CSV = Path("data/tierb_requirements_by_zone.csv")

# If True: replace sites.geojson with ONLY seeded Tier B candidates.
# If False: keep existing features and append Tier B candidates.
REPLACE_SITES_FILE = True

DEFAULT_SITE_FIELDS = {
    "tier": "B",
    "status": "CANDIDATE",
    "site_class": "OTHER",
    "access_class": "MODERATE",
    "power_class": "UNKNOWN",
    "risk_lightning": "UNKNOWN",
    "corridor_id": None,
}


def _load_geojson(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {"type": "FeatureCollection", "features": []}
    return json.loads(path.read_text(encoding="utf-8"))


def _write_geojson(path: Path, fc: Dict[str, Any]) -> None:
    path.write_text(json.dumps(fc, indent=2, sort_keys=True), encoding="utf-8")


def _polygon_area(ring: Iterable[Tuple[float, float]]) -> float:
    points = list(ring)
    if len(points) < 3:
        return 0.0
    area = 0.0
    for (x1, y1), (x2, y2) in zip(points, points[1:] + points[:1]):
        area += x1 * y2 - x2 * y1
    return abs(area) / 2.0


def _centroid_from_ring(ring: List[List[float]]) -> Tuple[float, float]:
    # Planning-grade centroid for a ring; assumes last point repeats the first.
    xs = [p[0] for p in ring[:-1]]
    ys = [p[1] for p in ring[:-1]]
    return (sum(xs) / len(xs), sum(ys) / len(ys))


def _get_centroid(geom: Dict[str, Any]) -> Tuple[float, float]:
    gtype = geom.get("type")
    coords = geom.get("coordinates")
    if gtype == "Polygon":
        return _centroid_from_ring(coords[0])
    if gtype == "MultiPolygon":
        # Use largest outer ring by area for a stable planning-grade centroid.
        largest = max(coords, key=lambda poly: _polygon_area([(p[0], p[1]) for p in poly[0][:-1]]))
        return _centroid_from_ring(largest[0])
    raise SystemExit(f"Unsupported geometry type for hex: {gtype}")


def _candidate_points(lon: float, lat: float, n: int) -> List[Tuple[float, float]]:
    """
    Deterministic tiny offsets so multiple points in same cell are distinct.
    Uses a small grid pattern in degrees; magnitude is planning-grade.
    """
    if n <= 1:
        return [(lon, lat)]
    pts: List[Tuple[float, float]] = []
    step = 0.0003
    base_offsets = [
        (-1, -1),
        (0, -1),
        (1, -1),
        (-1, 0),
        (0, 0),
        (1, 0),
        (-1, 1),
        (0, 1),
        (1, 1),
    ]
    for i in range(min(n, len(base_offsets))):
        dx, dy = base_offsets[i]
        pts.append((lon + dx * step, lat + dy * step))
    for i in range(len(base_offsets), n):
        pts.append((lon + (i - len(base_offsets) + 1) * step, lat))
    return pts


def _next_site_seq(existing_features: List[Dict[str, Any]]) -> int:
    max_id = 0
    for feat in existing_features:
        site_id = feat.get("properties", {}).get("site_id", "")
        if isinstance(site_id, str) and site_id.startswith("S_B_"):
            tail = site_id.split("_")[-1]
            if tail.isdigit():
                max_id = max(max_id, int(tail))
    return max_id + 1


def _new_site_id(seq: int) -> str:
    return f"S_B_{seq:04d}"


def main() -> None:
    hex_fc = _load_geojson(HEX_PATH)
    hex_features = hex_fc.get("features", [])
    if not hex_features:
        raise SystemExit(f"No hex features found in {HEX_PATH}")

    sites_fc = _load_geojson(SITES_PATH)
    existing_features = sites_fc.get("features", [])

    kept_features: List[Dict[str, Any]] = []
    if not REPLACE_SITES_FILE:
        kept_features = existing_features

    seq = _next_site_seq(kept_features) if kept_features else 1

    by_zone: Dict[str, Dict[str, int]] = {}
    seeded: List[Dict[str, Any]] = []

    for hf in hex_features:
        props = hf.get("properties", {}) or {}
        geom = hf.get("geometry", {}) or {}

        cell_id = props.get("cell_id") or props.get("id") or props.get("hex_id")
        zone_id = props.get("zone_id")

        if cell_id is None:
            raise SystemExit("Hex feature missing cell_id (or id/hex_id fallback).")
        if zone_id is None:
            raise SystemExit(f"Hex {cell_id} missing zone_id; run zone assignment first.")

        req = int(props.get("tierB_sites_required", 0) or 0)
        alt = int(props.get("tierB_alternate_required", 0) or 0)
        total = req + alt

        z = by_zone.setdefault(zone_id, {"tierB_sites_required": 0, "tierB_alternate_required": 0, "total": 0})
        z["tierB_sites_required"] += req
        z["tierB_alternate_required"] += alt
        z["total"] += total

        if total == 0:
            continue

        lon0, lat0 = _get_centroid(geom)
        pts = _candidate_points(lon0, lat0, total)

        for i in range(total):
            lon, lat = pts[i]
            is_alt = i >= req
            site_id = _new_site_id(seq)
            seq += 1

            site_name = f"Tier B {cell_id} #{i + 1:02d}"
            p: Dict[str, Any] = {
                "site_id": site_id,
                "site_name": site_name,
                "cell_id": cell_id,
                "zone_id": zone_id,
                **DEFAULT_SITE_FIELDS,
                "notes": "ALT" if is_alt else "",
            }

            seeded.append(
                {
                    "type": "Feature",
                    "geometry": {"type": "Point", "coordinates": [lon, lat]},
                    "properties": p,
                }
            )

    out_fc = {"type": "FeatureCollection", "features": kept_features + seeded}
    _write_geojson(SITES_PATH, out_fc)

    with OUT_CSV.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["zone_id", "tierB_sites_required", "tierB_alternate_required", "total"])
        for zone_id in sorted(by_zone.keys()):
            row = by_zone[zone_id]
            w.writerow([zone_id, row["tierB_sites_required"], row["tierB_alternate_required"], row["total"]])

    print(f"Seeded Tier B candidates: {len(seeded)}")
    print(f"Wrote: {SITES_PATH}")
    print(f"Wrote: {OUT_CSV}")


if __name__ == "__main__":
    main()
