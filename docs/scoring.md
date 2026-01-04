# Scoring formulas

## Hex cell confidence (0..4)
confidence_score =
  elev_adv_avail
+ tall_struct_avail
+ backbone_los_likely
+ (1 - clutter_high)

Where each flag is 0/1.

## Confidence class
- HIGH: confidence_score >= 3
- MED:  confidence_score == 2
- LOW:  confidence_score <= 1

## Tier B requirement
- HIGH: tierB_sites_required = 1; tierB_alternate_required = 0
- MED:  tierB_sites_required = 1; tierB_alternate_required = 1
- LOW:  tierB_sites_required = 2; tierB_alternate_required = 1

## Tier C priority (planning)
demand_driver = 0.6*pop_weight + 0.4*critical_weight
priority_score = demand_driver + (confidence_class == "LOW" ? 0.25 : 0.0)

tierC_demand_class:
- HIGH: priority_score >= 0.70
- MED:  0.40 <= priority_score < 0.70
- LOW:  priority_score < 0.40
