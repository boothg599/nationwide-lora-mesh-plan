import json
from pathlib import Path

HEX_PATH = Path("data/hex_cells.geojson")

# Zone-based default assumptions (planning-grade; conservative)
ZONE_DEFAULTS = {
    "Z_WEST_HIGH_RELIEF": {
        "elev_adv_avail": 1,        # peaks exist often
        "tall_struct_avail": 0,     # towers less dense than metros
        "clutter_high": 0,          # generally lower clutter
        "backbone_los_likely": 1,   # strong if you use peaks
        "pop_weight": 0.2,
        "critical_weight": 0.2,
    },
    "Z_CENTRAL_LOW_RELIEF": {
        "elev_adv_avail": 0,        # limited natural high ground
        "tall_struct_avail": 1,     # towers/water tanks common
        "clutter_high": 0,
        "backbone_los_likely": 1,   # plausible with structure height
        "pop_weight": 0.4,
        "critical_weight": 0.3,
    },
    "Z_EAST_RIDGE_METRO": {
        "elev_adv_avail": 1,        # ridges exist but shadowing is real
        "tall_struct_avail": 1,     # structures common
        "clutter_high": 1,          # urban/forest/clutter higher
        "backbone_los_likely": 0,   # ridge shadowing makes LOS uncertain
        "pop_weight": 0.6,
        "critical_weight": 0.4,
    },
    "": {  # unassigned
        "elev_adv_avail": 0,
        "tall_struct_avail": 0,
        "clutter_high": 0,
        "backbone_los_likely": 0,
        "pop_weight": 0.0,
        "critical_weight": 0.0,
    }
}

def clamp(x, lo, hi):
    return lo if x < lo else hi if x > hi else x

def compute_confidence_score(p):
    # 0/1 inputs; weight LOS and height highest.
    elev = int(p.get("elev_adv_avail", 0))
    tall = int(p.get("tall_struct_avail", 0))
    clutter = int(p.get("clutter_high", 0))
    los = int(p.get("backbone_los_likely", 0))

    # Score components (0..100)
    score = 0
    score += 25 * los
    score += 20 * elev
    score += 20 * tall
    score += 15 * (1 - clutter)  # clutter reduces confidence
    # Reserve 20 points for future refinements (terrain metrics etc.)
    return int(clamp(score, 0, 100))

def confidence_class(score):
    if score >= 70:
        return "HIGH"
    if score >= 40:
        return "MED"
    return "LOW"

def tierB_requirements(conf_class):
    # Conservative: LOW => 2 sites and alternate; MED => 1 + alternate; HIGH => 1 no alternate
    if conf_class == "LOW":
        return (2, 1)
    if conf_class == "MED":
        return (1, 1)
    return (1, 0)

def compute_tierC_demand(p, zid):
    # Rough proxy: based on clutter + pop_weight; refined later with real population layers.
    pop = float(p.get("pop_weight", 0.0))
    clutter = int(p.get("clutter_high", 0))
    demand = pop + (0.2 if clutter else 0.0)
    if zid == "Z_EAST_RIDGE_METRO":
        demand += 0.2
    if demand >= 0.8:
        return "HIGH"
    if demand >= 0.4:
        return "MED"
    return "LOW"

def compute_priority_score(p):
    # priority_score: blend of confidence + weights
    conf = int(p.get("confidence_score") or 0)
    pop = float(p.get("pop_weight", 0.0))
    crit = float(p.get("critical_weight", 0.0))
    # Weighting: confidence matters, but high demand/criticality can elevate priority.
    score = 0.6 * conf + 25.0 * pop + 25.0 * crit
    return int(clamp(round(score), 0, 100))

def main():
    hexes = json.loads(HEX_PATH.read_text(encoding="utf-8"))

    scaffolded = 0
    scored = 0

    for f in hexes["features"]:
        p = f.get("properties", {})
        zid = p.get("zone_id", "")

        defaults = ZONE_DEFAULTS.get(zid, ZONE_DEFAULTS[""])

        # Only set scaffold values if still at "empty default" state.
        for k in ["elev_adv_avail", "tall_struct_avail", "clutter_high", "backbone_los_likely"]:
            if k not in p or p.get(k) in (None, ""):
                p[k] = defaults[k]
                scaffolded += 1
            else:
                # If present but exactly 0 and you want zone defaults to overwrite only when blank,
                # we leave it as-is. 0 is a valid manual decision.
                pass

        for k in ["pop_weight", "critical_weight"]:
            if k not in p or p.get(k) is None:
                p[k] = defaults[k]
                scaffolded += 1

        # If weights are still exactly 0.0 everywhere and you want zone baseline, you can optionally set:
        # if p.get("pop_weight", 0.0) == 0.0: p["pop_weight"] = defaults["pop_weight"]
        # Keeping conservative: do not override explicit 0.0.

        # Derived fields
        cs = compute_confidence_score(p)
        cc = confidence_class(cs)
        sites_required, alt_required = tierB_requirements(cc)

        p["confidence_score"] = cs
        p["confidence_class"] = cc
        p["tierB_sites_required"] = sites_required
        p["tierB_alternate_required"] = alt_required
        p["tierC_demand_class"] = compute_tierC_demand(p, zid)
        p["priority_score"] = compute_priority_score(p)

        f["properties"] = p
        scored += 1

    HEX_PATH.write_text(json.dumps(hexes, indent=2), encoding="utf-8")
    print(f"Scaffolded inputs (where blank): {scaffolded} field sets. Scored {scored} hexes.")

if __name__ == "__main__":
    main()
