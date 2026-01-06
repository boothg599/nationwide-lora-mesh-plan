import json
from pathlib import Path

ZONES_PATH = Path("data/zones.geojson")
HEX_PATH = Path("data/hex_cells.geojson")

def point_in_ring(point, ring):
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

def point_in_polygon(point, polygon_coords):
    outer = polygon_coords[0]
    if not point_in_ring(point, outer):
        return False
    # planning-grade: ignore holes for zone clipping
    return True

def point_in_geometry(point, geom):
    gtype = geom["type"]
    coords = geom["coordinates"]
    if gtype == "Polygon":
        return point_in_polygon(point, coords)
    if gtype == "MultiPolygon":
        return any(point_in_polygon(point, poly) for poly in coords)
    raise ValueError(f"Unsupported geometry type: {gtype}")

def hex_vertices(hf):
    ring = hf["geometry"]["coordinates"][0]
    return ring[:-1]  # drop closing vertex

def main():
    zones = json.loads(ZONES_PATH.read_text(encoding="utf-8-sig"))
    hexes = json.loads(HEX_PATH.read_text(encoding="utf-8-sig"))

    zone_geoms = [f["geometry"] for f in zones["features"]]

    kept = []
    dropped = 0

    for hf in hexes["features"]:
        verts = hex_vertices(hf)
        keep = False
        for v in verts:
            if any(point_in_geometry(v, zg) for zg in zone_geoms):
                keep = True
                break
        if keep:
            kept.append(hf)
        else:
            dropped += 1

    HEX_PATH.write_text(json.dumps({"type": "FeatureCollection", "features": kept}, indent=2), encoding="utf-8")
    print(f"Kept {len(kept)} hexes (touch zone by vertex); dropped {dropped} fully outside zones.")

if __name__ == "__main__":
    main()
