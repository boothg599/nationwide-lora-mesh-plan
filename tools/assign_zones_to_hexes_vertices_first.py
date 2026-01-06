import json
from pathlib import Path

ZONES_PATH = Path("data/zones.geojson")
HEX_PATH = Path("data/hex_cells.geojson")

def centroid_of_polygon(poly_coords):
    ring = poly_coords[0]
    xs = [p[0] for p in ring[:-1]]
    ys = [p[1] for p in ring[:-1]]
    return (sum(xs) / len(xs), sum(ys) / len(ys))

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
    # planning-grade: ignore holes
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
    return ring[:-1]

def main():
    zones = json.loads(ZONES_PATH.read_text(encoding="utf-8-sig"))
    hexes = json.loads(HEX_PATH.read_text(encoding="utf-8-sig"))

    zone_geoms = [(f["properties"].get("zone_id",""), f["geometry"]) for f in zones["features"]]

    assigned_centroid = 0
    assigned_vertex = 0
    unassigned = 0

    for hf in hexes["features"]:
        props = hf.get("properties", {})
        c = centroid_of_polygon(hf["geometry"]["coordinates"])
        verts = hex_vertices(hf)

        zid = None

        # 1) centroid-in-zone
        for zid0, g in zone_geoms:
            if zid0 and point_in_geometry(c, g):
                zid = zid0
                assigned_centroid += 1
                break

        # 2) vertex-touch vote
        if zid is None:
            hits = {}
            for zid0, g in zone_geoms:
                if not zid0:
                    continue
                count = 0
                for v in verts:
                    if point_in_geometry(v, g):
                        count += 1
                if count:
                    hits[zid0] = count

            if hits:
                zid = sorted(hits.items(), key=lambda kv: (-kv[1], kv[0]))[0][0]
                assigned_vertex += 1

        if zid is None:
            props["zone_id"] = ""
            unassigned += 1
        else:
            props["zone_id"] = zid

        hf["properties"] = props

    HEX_PATH.write_text(json.dumps(hexes, indent=2), encoding="utf-8")
    print(f"Assigned by centroid: {assigned_centroid}; by vertex-touch: {assigned_vertex}; unassigned: {unassigned}.")

if __name__ == "__main__":
    main()
