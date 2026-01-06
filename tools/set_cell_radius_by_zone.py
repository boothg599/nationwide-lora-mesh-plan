import json
from pathlib import Path

HEX_PATH = Path("data/hex_cells.geojson")

RADIUS_BY_ZONE = {
    "Z_WEST_HIGH_RELIEF": 70,
    "Z_CENTRAL_LOW_RELIEF": 50,
    "Z_EAST_RIDGE_METRO": 35,
}

def main():
    hexes = json.loads(HEX_PATH.read_text(encoding="utf-8"))

    changed = 0
    unknown = 0

    for f in hexes["features"]:
        props = f.get("properties", {})
        zid = props.get("zone_id", "")

        if zid in RADIUS_BY_ZONE:
            new_r = RADIUS_BY_ZONE[zid]
            if props.get("cell_radius_mi") != new_r:
                props["cell_radius_mi"] = new_r
                changed += 1
        else:
            # Leave default, but annotate if zone_id is blank/unknown
            unknown += 1
            note = props.get("notes", "") or ""
            tag = "zone_id missing/unknown; cell_radius_mi left default"
            if tag not in note:
                props["notes"] = (note + ("; " if note else "") + tag)

        f["properties"] = props

    HEX_PATH.write_text(json.dumps(hexes, indent=2), encoding="utf-8")
    print(f"Updated cell_radius_mi for {changed} hexes. {unknown} hexes had missing/unknown zone_id.")

if __name__ == "__main__":
    main()
