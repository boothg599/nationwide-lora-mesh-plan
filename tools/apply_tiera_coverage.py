#!/usr/bin/env python3
"""Apply Tier A coverage subtraction to Tier B required sites."""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Dict, Iterable, List, Set, Tuple


ROOT = Path(__file__).resolve().parents[1]
HEX_CELLS_PATH = ROOT / "data" / "hex_cells.geojson"
SITES_PATH = ROOT / "data" / "sites.geojson"
OUTPUT_CSV_PATH = ROOT / "data" / "tierb_after_tiera_by_zone.csv"


Vertex = Tuple[float, float]


def iter_vertices(geometry: Dict) -> Iterable[Vertex]:
    geom_type = geometry.get("type")
    coordinates = geometry.get("coordinates", [])
    if geom_type == "Polygon":
        for ring in coordinates:
            for coord in ring:
                yield tuple(coord)
    elif geom_type == "MultiPolygon":
        for polygon in coordinates:
            for ring in polygon:
                for coord in ring:
                    yield tuple(coord)
    else:
        raise ValueError(f"Unsupported geometry type: {geom_type}")


def build_neighbor_map(hex_features: List[Dict]) -> Dict[str, Set[str]]:
    vertex_to_cells: Dict[Vertex, Set[str]] = {}
    cell_vertices: Dict[str, Set[Vertex]] = {}
    for feature in hex_features:
        cell_id = feature["properties"].get("cell_id")
        if not cell_id:
            continue
        vertices = set(iter_vertices(feature["geometry"]))
        cell_vertices[cell_id] = vertices
        for vertex in vertices:
            vertex_to_cells.setdefault(vertex, set()).add(cell_id)

    neighbor_map: Dict[str, Set[str]] = {}
    for cell_id, vertices in cell_vertices.items():
        neighbors: Set[str] = set()
        for vertex in vertices:
            neighbors.update(vertex_to_cells.get(vertex, set()))
        neighbor_map[cell_id] = neighbors
    return neighbor_map


def load_geojson(path: Path) -> Dict:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def write_geojson(path: Path, data: Dict) -> None:
    with path.open("w", encoding="utf-8") as handle:
        json.dump(data, handle, indent=2)
        handle.write("\n")


def main() -> None:
    hex_cells = load_geojson(HEX_CELLS_PATH)
    sites = load_geojson(SITES_PATH)

    neighbor_map = build_neighbor_map(hex_cells["features"])

    tierb_candidates_by_cell: Dict[str, List[Dict]] = {}
    tierb_required_features: List[Dict] = []
    tierb_alt_features: List[Dict] = []
    tiera_features: List[Dict] = []

    for feature in sites["features"]:
        props = feature.get("properties", {})
        tier = props.get("tier")
        notes = props.get("notes")
        if tier == "A":
            tiera_features.append(feature)
            continue
        if tier != "B":
            continue
        if notes == "ALT":
            tierb_alt_features.append(feature)
            continue
        tierb_required_features.append(feature)
        if props.get("status") == "CANDIDATE":
            cell_id = props.get("cell_id")
            if cell_id:
                tierb_candidates_by_cell.setdefault(cell_id, []).append(feature)

    satisfied_required = 0
    tiera_used: Set[str] = set()

    for tiera_feature in tiera_features:
        props = tiera_feature.get("properties", {})
        cell_id = props.get("cell_id")
        if not cell_id:
            continue
        covered_cells = neighbor_map.get(cell_id, {cell_id})
        satisfied_any = False
        for covered_cell in covered_cells:
            candidates = tierb_candidates_by_cell.get(covered_cell, [])
            for candidate in candidates:
                cand_props = candidate.get("properties", {})
                if cand_props.get("status") != "CANDIDATE":
                    continue
                cand_props["status"] = "SATISFIED"
                cand_props["satisfied_by"] = props.get("site_id")
                cand_props["satisfied_corridor_id"] = props.get("corridor_id")
                satisfied_required += 1
                satisfied_any = True
        if satisfied_any:
            tiera_used.add(props.get("site_id"))

    zone_stats: Dict[str, Dict[str, int]] = {}
    for feature in tierb_required_features:
        props = feature.get("properties", {})
        zone_id = props.get("zone_id")
        if not zone_id:
            continue
        stats = zone_stats.setdefault(
            zone_id,
            {
                "tierB_required_before": 0,
                "tierB_required_after": 0,
                "tierB_alt_total": 0,
                "tierA_sites": 0,
            },
        )
        stats["tierB_required_before"] += 1
        if props.get("status") != "SATISFIED":
            stats["tierB_required_after"] += 1

    for feature in tierb_alt_features:
        props = feature.get("properties", {})
        zone_id = props.get("zone_id")
        if not zone_id:
            continue
        stats = zone_stats.setdefault(
            zone_id,
            {
                "tierB_required_before": 0,
                "tierB_required_after": 0,
                "tierB_alt_total": 0,
                "tierA_sites": 0,
            },
        )
        stats["tierB_alt_total"] += 1

    for feature in tiera_features:
        props = feature.get("properties", {})
        zone_id = props.get("zone_id")
        if not zone_id:
            continue
        stats = zone_stats.setdefault(
            zone_id,
            {
                "tierB_required_before": 0,
                "tierB_required_after": 0,
                "tierB_alt_total": 0,
                "tierA_sites": 0,
            },
        )
        stats["tierA_sites"] += 1

    with OUTPUT_CSV_PATH.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            [
                "zone_id",
                "tierB_required_before",
                "tierB_required_after",
                "tierB_alt_total",
                "tierA_sites",
            ]
        )
        for zone_id in sorted(zone_stats):
            stats = zone_stats[zone_id]
            writer.writerow(
                [
                    zone_id,
                    stats["tierB_required_before"],
                    stats["tierB_required_after"],
                    stats["tierB_alt_total"],
                    stats["tierA_sites"],
                ]
            )

    remaining_required = sum(
        1
        for feature in tierb_required_features
        if feature.get("properties", {}).get("status") != "SATISFIED"
    )

    write_geojson(SITES_PATH, sites)

    print(
        "Summary:",
        f"satisfied_required={satisfied_required}",
        f"remaining_required={remaining_required}",
        f"tierA_used={len(tiera_used)}",
    )


if __name__ == "__main__":
    main()
