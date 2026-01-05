import json
from math import cos, radians, sqrt
from pathlib import Path

# CONUS bounding box (planning-grade).
# lon_min, lat_min, lon_max, lat_max
BBOX = (-125.0, 24.0, -66.5, 49.5)

# Use smallest-zone radius (East) so you do not redraw later.
HEX_RADIUS_MI = 35.0

OUT_PATH = Path("data/hex_cells.geojson")

def miles_to_deg_lat(mi: float) -> float:
    return mi / 69.0  # ~69 miles per degree latitude

def miles_to_deg_lon(mi: float, lat_deg: float) -> float:
    return mi / (69.0 * cos(radians(lat_deg)))  # ~69*cos(lat) miles per degree longitude

def hex_polygon(center_lon: float, center_lat: float, r_mi: float):
    # Flat-top hex approximation in degrees; planning-grade.
    r_lat = miles_to_deg_lat(r_mi)
    r_lon = miles_to_deg_lon(r_mi, center_lat)

    pts = [
        (center_lon + r_lon, center_lat),
        (center_lon + r_lon / 2, center_lat + r_lat * sqrt(3) / 2),
        (center_lon - r_lon / 2, center_lat + r_lat * sqrt(3) / 2),
        (center_lon - r_lon, center_lat),
        (center_lon - r_lon / 2, center_lat - r_lat * sqrt(3) / 2),
        (center_lon + r_lon / 2, center_lat - r_lat * sqrt(3) / 2),
        (center_lon + r_lon, center_lat),  # close ring
    ]
    return [[[lon, lat] for lon, lat in pts]]

def main():
    lon_min, lat_min, lon_max, lat_max = BBOX

    features = []
    cell_idx = 0

    lat = lat_min
    row = 0
    while lat <= lat_max:
        r_lon = miles_to_deg_lon(HEX_RADIUS_MI, lat)
        r_lat = miles_to_deg_lat(HEX_RADIUS_MI)

        lon_step = 1.5 * r_lon
        lat_step = sqrt(3) * r_lat

        lon = lon_min + (0.75 * r_lon if row % 2 else 0.0)

        while lon <= lon_max:
            cell_idx += 1
            cell_id = f"H_{cell_idx:06d}"

            geom = {
                "type": "Polygon",
                "coordinates": hex_polygon(lon, lat, HEX_RADIUS_MI),
            }

            props = {
                "cell_id": cell_id,
                "zone_id": "",
                "cell_radius_mi": 35,

                "elev_adv_avail": 0,
                "tall_struct_avail": 0,
                "clutter_high": 0,
                "backbone_los_likely": 0,

                "pop_weight": 0.0,
                "critical_weight": 0.0,

                "confidence_score": None,
                "confidence_class": None,
                "tierB_sites_required": None,
                "tierB_alternate_required": None,
                "tierC_demand_class": None,
                "priority_score": None,

                "notes": ""
            }

            features.append({"type": "Feature", "geometry": geom, "properties": props})
            lon += lon_step

        lat += lat_step
        row += 1

    fc = {"type": "FeatureCollection", "features": features}
    OUT_PATH.write_text(json.dumps(fc, indent=2), encoding="utf-8")
    print(f"Wrote {len(features)} hex cells to {OUT_PATH}")

if __name__ == "__main__":
    main()
