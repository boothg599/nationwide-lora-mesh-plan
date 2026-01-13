#!/usr/bin/env python3
"""
Seed Tier A candidate sites from corridor LineStrings.

Reads:
  - data/corridors.geojson
  - data/hex_cells.geojson

Writes:
  - data/sites.geojson (adds/refreshes Tier A sites; keeps existing non-A sites)
  - data/tiera_targets_by_corridor.csv (rollup)

Notes:
  - stdlib-only
  - deterministic sampling along each corridor line
  - assigns cell_id + zone_id by finding which hex polygon contains the sampled point
"""

import csv
import json
from math import cos, radians, sqrt
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

CORRIDORS_PATH = Path("data/corridors.geojson")
HEX_PATH = Path("data/hex_cells.geojson")
SITES_PATH = Path("data/sites.geojson")
OUT_CSV = Path("data/tiera_targets_by_corridor.csv")

DEFAULT_SITE_FIELDS = {
    "tier": "A",
    "status": "CANDIDATE",
    "site_class": "OTHER",
    "access_class": "MODERATE",
    "power_class": "UNKNOWN",
    "risk_lightning": "UNKNOWN",
}

def _load_geojson(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {"type": "FeatureCollection", "features": []}
    return json.loads(path.read_text(encoding="utf-8"))

def _write_geojson(path: Path, fc: Dict[str, Any]) -> None:
    path.write_text(json.dumps(fc, indent=2, sort_keys=True), encoding="utf-8")

def _point_in_ring(point: Tuple[float, float], ring: List[List[float]]) -> bool:
    # Ray casting algorithm (planning-grade)
    x, y = point
    inside = False
    n = len(ring)
    for i in range(n - 1):
        x1, y1 = ring[i]
        x2, y2 = ring[i + 1]
        if (y1 > y) != (y2 > y):
            xinters = (x2 - x1) * (y - y1) / ((y2 - y1) + 1e-12) + x1
            if x < xinters:
                inside = not inside
    return inside

def _point_in_polygon(point: Tuple[float, float], polygon_coords: Any) -> bool:
    outer = polygon_coords[0]
    if not _point_in_ring(point, outer):
        return False
    # planning-grade: ignore holes
    return True

def _deg_to_miles_lon(dlon: float, lat_deg: float) -> float:
    return dlon * 69.0 * cos(radians(lat_deg))

def _deg_to_miles_lat(dlat: float) -> float:
    return dlat * 69.0

def _segment_len_mi(a: Tuple[float, float], b: Tuple[float, float]) -> float:
    # planning-grade: convert degrees to miles using local latitude
    lon1, lat1 = a
    lon2, lat2 = b
    dlon = lon2 - lon1
    dlat = lat2 - lat1
    mx = _deg_to_miles_lon(dlon, (lat1 + lat2) / 2.0)
    my = _deg_to_miles_lat(dlat)
    return sqrt(mx * mx + my * my)

def _line_length_mi(coords: List[List[float]]) -> float:
    total = 0.0
    for i in range(len(coords) - 1):
        a = (coords[i][0], coords[i][1])
        b = (coords[i + 1][0], coords[i + 1][1])
        total += _segment_len_mi(a, b)
    return total

def _interpolate_on_segment(a: Tuple[float, float], b: Tuple[float, float], t: float) -> Tuple[float, float]:
    return (a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t)

def _sample_points_along_line(coords: List[List[float]], n: int) -> List[Tuple[float, float]]:
    """
    Deterministic: place points at equal arc-length fractions along the line.
    n>=1
    """
    if n <= 0:
        return []
    if n == 1:
        # midpoint by distance
        target = _line_length_mi(coords) / 2.0
        return [_point_at_distance(coords, target)]

    total_len = _line_length_mi(coords)
    if total_len <= 0:
        # degenerate line: return first coord repeated
        lon, lat = coords[0][0], coords[0][1]
        return [(lon, lat) for _ in range(n)]

    # Place at fractions excluding endpoints (more useful than sampling exact endpoints)
    # i = 1..n => fraction = i/(n+1)
    targets = [total_len * (i / (n + 1)) for i in range(1, n + 1)]
    return [_point_at_distance(coords, d) for d in targets]

def _point_at_distance(coords: List[List[float]], dist_mi: float) -> Tuple[float, float]:
    walked = 0.0
    for i in range(len(coords) - 1):
        a = (coords[i][0], coords[i][1])
        b = (coords[i + 1][0], coords[i + 1][1])
        seg = _segment_len_mi(a, b)
        if walked + seg >= dist_mi:
            t = 0.0 if seg == 0 else (dist_mi - walked) / seg
            return _interpolate_on_segment(a, b, t)
        walked += seg
    # If rounding puts us past the end, return last point
    return (coords[-1][0], coords[-1][1])

def _build_hex_index(hex_features: List[Dict[str, Any]]) -> List[Tuple[str, str, Any]]:
    """
    Returns list of (cell_id, zone_id, polygon_coords)
    """
    out = []
    for f in hex_features:
        props = f.get("properties", {}) or {}
        geom = f.get("geometry", {}) or {}
        if geom.get("type") != "Polygon":
            continue
        cell_id = props.get("cell_id") or props.get("id") or props.get("hex_id")
        zone_id = props.get("zone_id")
        if cell_id is None or zone_id is None:
            continue
        out.append((str(cell_id), str(zone_id), geom.get("coordinates")))
    return out

def _find_hex_for_point(pt: Tuple[float, float], hex_index: List[Tuple[str, str, Any]]) -> Optional[Tuple[str, str]]:
    for cell_id, zone_id, poly_coords in hex_index:
        if _point_in_polygon(pt, poly_coords):
            return (cell_id, zone_id)
    return None

def main() -> None:
    corridors_fc = _load_geojson(CORRIDORS_PATH)
    hex_fc = _load_geojson(HEX_PATH)
    sites_fc = _load_geojson(SITES_PATH)

    corridors = corridors_fc.get("features", [])
    hex_features = hex_fc.get("features", [])
    if not corridors:
        raise SystemExit(f"No corridor features found in {CORRIDORS_PATH}")
    if not hex_features:
        raise SystemExit(f"No hex features found in {HEX_PATH}")

    # Keep existing non-Tier-A sites; drop existing Tier A so we can regenerate deterministically
    existing = sites_fc.get("features", [])
    kept = [f for f in existing if (f.get("properties", {}) or {}).get("tier") != "A"]

    hex_index = _build_hex_index(hex_features)

    seeded: List[Dict[str, Any]] = []
    seq = 1

    rollup: Dict[str, Dict[str, int]] = {}

    for c in corridors:
        props = c.get("properties", {}) or {}
        geom = c.get("geometry", {}) or {}
        if geom.get("type") != "LineString":
            raise SystemExit("corridors.geojson contains non-LineString geometry; update script if needed.")

        corridor_id = props.get("corridor_id")
        corridor_name = props.get("corridor_name", "") or ""
        tmin = int(props.get("tierA_target_sites_min", 0) or 0)
        tmax = int(props.get("tierA_target_sites_max", 0) or 0)

        if corridor_id is None:
            raise SystemExit("corridor feature missing corridor_id")

        required = max(0, tmin)
        alternate = max(0, tmax - tmin)
        total = required + alternate

        r = rollup.setdefault(str(corridor_id), {"required": 0, "alternate": 0, "total": 0})
        r["required"] += required
        r["alternate"] += alternate
        r["total"] += total

        if total == 0:
            continue

        coords = geom.get("coordinates", [])
        pts = _sample_points_along_line(coords, total)

        for i in range(total):
            lon, lat = pts[i]
            match = _find_hex_for_point((lon, lat), hex_index)
            if match is None:
                # If point falls outside all hexes (unlikely), skip deterministically
                continue
            cell_id, zone_id = match
            is_alt = i >= required

            site_id = f"S_A_{seq:04d}"
            seq += 1

            p = {
                "site_id": site_id,
                "site_name": f"Tier A {corridor_id} #{i+1:02d}",
                "cell_id": cell_id,
                "zone_id": zone_id,
                "corridor_id": corridor_id,
                "notes": "ALT" if is_alt else "",
                **DEFAULT_SITE_FIELDS,
            }

            seeded.append(
                {
                    "type": "Feature",
                    "geometry": {"type": "Point", "coordinates": [lon, lat]},
                    "properties": p,
                }
            )

    out_fc = {"type": "FeatureCollection", "features": kept + seeded}
    _write_geojson(SITES_PATH, out_fc)

    with OUT_CSV.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["corridor_id", "required", "alternate", "total"])
        for cid in sorted(rollup.keys()):
            row = rollup[cid]
            w.writerow([cid, row["required"], row["alternate"], row["total"]])

    print(f"Seeded Tier A candidates: {len(seeded)}")
    print(f"Wrote: {SITES_PATH}")
    print(f"Wrote: {OUT_CSV}")

if __name__ == "__main__":
    main()
