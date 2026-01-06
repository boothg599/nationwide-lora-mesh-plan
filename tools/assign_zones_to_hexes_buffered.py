import json
from math import cos, radians, sqrt
from pathlib import Path

ZONES_PATH = Path("data/zones.geojson")
HEX_PATH = Path("data/hex_cells.geojson")

# Planning-grade coastal buffer (miles). Increase to 35–45 if coast still looks too jagged.
COASTAL_BUFFER_MI = 25.0

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
    return True  # holes ignored (planning-grade)

def point_in_geometry(point, geom):
    gtype = geom["type"]
    coords = geom["coordinates"]
    if gtype == "Polygon":
        return point_in_polygon(point, coords)
    if gtype == "MultiPolygon":
        return any(point_in_polygon(point, poly) for poly in coords)
    raise ValueError(f"Unsupported geometry type: {gtype}")

def miles_per_degree_lon(lat_deg: float) -> float:
    return 69.0 * cos(radians(lat_deg))

def deg_to_miles(dx_deg: float, dy_deg: float, lat_deg: float) -> float:
    # Equirectangular approximation: good enough for ~tens of miles.
    mx = dx_deg * miles_per_degree_lon(lat_deg)
    my = dy_deg * 69.0
    return sqrt(mx * mx + my * my)

def point_to_segment_distance_miles(p, a, b):
    # p, a, b are (lon, lat) in degrees; returns approximate miles
    px, py = p
    ax, ay = a
    bx, by = b

    # Project p onto segment ab in degree-space (small distances => acceptable)
    abx, aby = (bx - ax), (by - ay)
    apx, apy = (px - ax), (py - ay)
    ab2 = abx * abx + aby * aby
    if ab2 == 0:
        return deg_to_miles(px - ax, py - ay, py)

    t = (apx * abx + apy * aby) / ab2
    t = 0.0 if t < 0.0 else 1.0 if t > 1.0 else t
    cx = ax + t * abx
    cy = ay + t * aby
    return deg_to_miles(px - cx, py - cy, py)

def distance_to_polygon_outer_ring_miles(point, polygon_coords):
    outer = polygon_coords[0]
    best = float("inf")
    for i in range(len(outer) - 1):
        d = point_to_segment_distance_miles(point, outer[i], outer[i + 1])
        if d < best:
            best = d
    return best

def distance_to_geometry_miles(point, geom):
    gtype = geom["type"]
    coords = geom["coordinates"]
    if gtype == "Polygon":
        return distance_to_polygon_outer_ring_miles(point, coords)
    if gtype == "MultiPolygon":
        return min(distance_to_polygon_outer_ring_miles(point, poly) for poly in coords)
    raise ValueError(f"Unsupported geometry type: {gtype}")

def main():
    zones = json.loads(ZONES_PATH.read_text(encoding="utf-8"))
    hexes = json.loads(HEX_PATH.read_text(encoding="utf-8"))

    zone_geoms = []
    for f in zones["features"]:
        zid = f["properties"].get("zone_id", "")
        zone_geoms.append((zid, f["geometry"]))

    assigned_strict = 0
    assigned_buffer = 0
    unassigned = 0

    for hf in hexes["features"]:
        hgeom = hf["geometry"]
        hprops = hf.get("properties", {})

        c = centroid_of_polygon(hgeom["coordinates"])

        zid_found = None
        # 1) strict
        for zid, zgeom in zone_geoms:
            if zid and point_in_geometry(c, zgeom):
                zid_found = zid
                assigned_strict += 1
                break

        # 2) buffered near-boundary
        if zid_found is None:
            best_zid = None
            best_dist = float("inf")
            for zid, zgeom in zone_geoms:
                if not zid:
                    continue
                d = distance_to_geometry_miles(c, zgeom)
                if d < best_dist:
                    best_dist = d
                    best_zid = zid
            if best_zid is not None and best_dist <= COASTAL_BUFFER_MI:
                zid_found = best_zid
                assigned_buffer += 1

        if zid_found is None:
            unassigned += 1
            hprops["zone_id"] = ""
        else:
            hprops["zone_id"] = zid_found

        hf["properties"] = hprops

    HEX_PATH.write_text(json.dumps(hexes, indent=2), encoding="utf-8")
    print(f"Assigned strict: {assigned_strict}; assigned via buffer: {assigned_buffer}; unassigned: {unassigned}. Buffer mi: {COASTAL_BUFFER_MI}")

if __name__ == "__main__":
    main()
