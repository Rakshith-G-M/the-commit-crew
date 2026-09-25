# CampusIQ — Recommendation Engine (M7)

Converts M6 decision candidates into ranked, explainable, actionable
recommendations. Answers WHAT IS HAPPENING, WHY IT MATTERS, WHAT THE
ADMIN CAN DO, WHY THIS ACTION, WHAT EVIDENCE SUPPORTS IT, and WHAT
INFORMATION IS MISSING.

## 1. Ranking formula

- campusiq.weighted-linear/v1:
  `priority_score = sum(weights[f] * factors[f])`
- Weights: {"severity": 0.3, "persistence": 0.15, "deviation": 0.15, "forecast_relevance": 0.05, "resource_relevance": 0.1, "actionability": 0.1, "confidence": 0.1, "data_quality": 0.05}
- Factors (0..1, all stored per candidate in `ranking.factors` with
  `factor_basis`): severity, persistence, deviation, forecast_relevance,
  resource_relevance, actionability, confidence, data_quality.
- Priority bands: {"critical": 0.75, "high": 0.6, "medium": 0.4}.
- This is decision-support ranking, not a claim of objective best.

## 2. Recommendations generated: 98

- By category: {"SENSOR_HEALTH": 36, "ENVIRONMENTAL": 61, "ENERGY": 1}
- By priority: {"HIGH": 55, "MEDIUM": 36, "LOW": 7}
- By location status: {"UNKNOWN_LOCATION": 98}
- Top recommendation: R-0001 (HIGH, score 0.73) -> Schedule sensor maintenance / calibration check for dfd7a151-1cae-4cd6-b3af-91ff110a21b2 (issues: CONSTANT_VALUE, IRREGULAR_SAMPLING, LONG_GAP).

## 3. Categories

- ENVIRONMENTAL: investigate ventilation / abnormal indoor conditions /
  inspect affected environmental system.
- ENERGY: inspect abnormal energy behaviour / operating schedule /
  high-load equipment.
- SENSOR_HEALTH: inspect sensor, check communication, validate readings.
- ALLOCATION: feasible spaces, why they qualify, why others are rejected.

## 4. Evidence chain

Every recommendation carries `evidence_chain`, e.g. for anomalies:

    ANOMALY -> MEASUREMENT -> HISTORICAL_BASELINE -> DEVIATION
      -> PERSISTENCE -> CANDIDATE -> RECOMMENDATION

Each step has an entity, value and note so the front-end can render it.

## 5. Impact classification

- `CALCULATED`   — from explicit model/data (e.g., BIM design capacity).
- `ESTIMATED`    — reserved for a verified intervention model (none yet).
- `QUALITATIVE`  — directional, non-numeric (e.g., risk reduction).
- `UNKNOWN`      — no model/data (e.g., energy savings: value null, kWh,
  'No verified intervention model').
Never is a qualitative assumption turned into a numeric saving.

## 6. Location and allocation honesty

- M4 status: 36 UNRESOLVED / 36 sensors -> sensor-derived
  recommendations are UNKNOWN_LOCATION.
- BIM/IFC-derived recommendations are VERIFIED_BIM.
- Allocation evaluates ONLY explicit request + availability;  no timetable fabricated.

## 7. Outputs

- output/recommendations.json (full, ranked, explainable)
- output/recommendation_summary.json (compact)
- GET /api/* FastAPI layer (scripts/api_app.py)

## 8. Recommended next step

- M8: integrate a confirmed mapping (when available) to attach 
  recommendations to rooms, and a schedule-aware allocation optimizer.

