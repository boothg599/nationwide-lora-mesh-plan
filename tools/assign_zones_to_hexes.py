import json
from pathlib import Path

ZONES_PATH = Path("data/zones.geojson")
HEX_PATH = Path("data/hex_cells.geojson")

def centroid_of_polygon(poly_coords):
    # poly_coords: [ [ [lon,lat], ... ] ] (outer ring only)
    ring = poly_coords[0]
    # drop closing point
    xs = [p[0] for p in ring[:-1]]
    ys = [p[1] for p in ring[:-1]]
    return (sum(xs) / len(xs), sum(ys) / len(ys))

def point_in_ring(point, ring):
    # Ray casting algorithm
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
    # polygon_coords: [outer_ring, hole1, hole2...]
    outer = polygon_coords[0]
    if not point_in_ring(point, outer):
        return False
    # Ignore holes for now (planning-grade); add later if you introduce holes.
    return True

def point_in_geometry(point, geom):
    gtype = geom["type"]
    coords = geom["coordinates"]
    if gtype == "Polygon":
        return point_in_polygon(point, coords)
    if gtype == "MultiPolygon":
        return any(point_in_polygon(point, poly) for poly in coords)
    raise ValueError(f"Unsupported geometry type: {gtype}")

def main():
    zones = json.loads(ZONES_PATH.read_text(encoding="utf-8"))
    hexes = json.loads(HEX_PATH.read_text(encoding="utf-8"))

    zone_geoms = []
    for f in zones["features"]:
        zid = f["properties"].get("zone_id", "")
        zone_geoms.append((zid, f["geometry"]))

    assigned = 0
    unassigned = 0

    for hf in hexes["features"]:
        hgeom = hf["geometry"]
        hprops = hf.get("properties", {})

        c = centroid_of_polygon(hgeom["coordinates"])

        zid_found = None
        for zid, zgeom in zone_geoms:
            if zid and point_in_geometry(c, zgeom):
                zid_found = zid
                break

        if zid_found is None:
            unassigned += 1
            hprops["zone_id"] = ""
        else:
            assigned += 1
            hprops["zone_id"] = zid_found

        hf["properties"] = hprops

    HEX_PATH.write_text(json.dumps(hexes, indent=2), encoding="utf-8")
    print(f"Assigned zone_id for {assigned} hexes; {unassigned} unassigned (outside zone polygons).")

if __name__ == "__main__":
    main()
