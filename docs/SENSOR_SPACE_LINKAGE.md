# SENSOR-SPACE LINKAGE ENGINE (M4)

- **Task**: M4-SENSOR-SPACE-LINKAGE-ENGINE
- **Prior foundation**: M3.1 canonical campus (see `docs/SENSOR_IFC_MAPPING_REPORT.md` / `output/*`), M2 external mapping research (`docs/M2_EXTERNAL_MAPPING_RESEARCH.md`, `output/external_mapping_evidence.json`)
- **Core module**: `scripts/linkage_engine.py` (framework-independent Python; no HTTP layer)
- **Canonical artefacts**: `output/sensor_space_mapping.json`, `output/sensor_space_candidates.json`
- **Raw data**: unchanged (IFC / ZIP / CSVs are read-only)

## 1. Current mapping status

| metric | value |
|---|---|
| Sensors | 36 |
| Spaces | 115 |
| CONFIRMED mappings | 0 |
| PROVISIONAL mappings | 0 |
| UNRESOLVED sensors | 36 |
| Generated candidates | 0 |

Every sensor has exactly one active mapping record in
`output/sensor_space_mapping.json`. All 36 are `UNRESOLVED` (`space_id` null,
`confidence` 0.0, method `none_found`). The candidate artefact
`output/sensor_space_candidates.json` contains the per-sensor signal audit:
for every sensor all six candidate signals were evaluated and found **absent**,
and telemetry similarity is explicitly excluded as a physical-location signal.
No mapping — confirmed or provisional — has been fabricated.

## 2. Why mappings cannot currently be verified

- The sensor files (`Taltech.zip`, 69 CSVs) carry only
  `device_id UUID, timestamp, meas_type, value, unit`. There is no room,
  space, building, or asset field (M1 verified over all 1,390,297 rows).
- The IFC (`DS3_TalTech_V4.ifc`) exposes 115 `IfcSpace` with GlobalIds, Revit
  Element Ids (`IfcSpaceType.Tag`) and storeys, but **zero** device UUIDs.
- The two datasets share **no identifier**, and no hidden mapping table exists
  inside the archive or the IFC (M1).
- M2 exhaustively searched every public surface of the producing project
  (Zenodo 15782433, CORDIS, SmartLivingEPC deliverables D1-x/D4-x/D5-x/D6-x/
  D8.9, OpenAIRE, GitHub, web) → **NOT_FOUND**. The device→space assignments
  were entered by the pilot manager into the private CIEM / Web-Platform
  Device Management database (D5.1 §5.3.5; D8.9) at registration time. That
  registry is not published and was not provided.
- The public 4 IEQ test rooms / VAV rooms 206-207-309 / ~25 energy meters
  (D6.2/D6.4) describe equipment types and counts but associate **no UUID**;
  connecting them to specific sensors would be inference, not evidence.

## 3. Evidence model

An explicit evidence record must explain **why** a mapping exists. Every
evidence entry has a type, a description, a source, an optional URL, and (when
created by an import) a recorded time:

```jsonc
{
  "type": "bms_registry",          // see types below
  "description": "sensor assigned to space by authoritative BMS/CIEM registry row",
  "source": "<export file or registry name>",
  "url": null,
  "recorded_at": null
}
```

Supported evidence types, and the strongest status they imply alone:

| type | implies |
|---|---|
| `bms_registry` | CONFIRMED |
| `ciem_registry` | CONFIRMED |
| `manually_verified` | CONFIRMED |
| `explicit_dataset_metadata` | CONFIRMED |
| `ifc_identifier_match` | PROVISIONAL |
| `documented_room_reference` | PROVISIONAL |
| `candidate_inference` | PROVISIONAL |

## 4. Confirmed vs provisional vs unresolved

A mapping record carries `sensor_id`, `space_id`, `status`, `confidence`
(numeric 0..1), `mapping_method`, `evidence[]`, `source`, `created_at`,
`updated_at`, `valid_from/to`, `history[]`, and the location verdict
`location_status` / `location_verified`.

- **CONFIRMED** — backed by authoritative evidence (BMS/CIEM registry entry or
  manual verification). `space_id` **required**, `confidence` must equal
  `1.0`, `evidence` non-empty, `location_status=VERIFIED_LOCATION`,
  `location_verified=True`.
- **PROVISIONAL** — produced by an inference signal (`candidate_inference`,
  `ifc_identifier_match`, `documented_room_reference`). `space_id` required,
  `0 < confidence < 1`, `evidence` non-empty, `location_status=
  PROVISIONAL_LOCATION`, `location_verified=False`.
- **UNRESOLVED** — no evidence. `space_id` **null**, `confidence=0.0`,
  method `none_found`, evidence empty, `location_status=UNKNOWN_LOCATION`,
  `location_verified=False`.

Invariants (enforced by `linkage_engine.validate_mapping` and asserted in
tests): status ↔ method consistency, confidence bounds, evidence presence for
resolved records, and the protected merge rule **provisional never overwrites
confirmed** (`linkage_engine.apply_import`).

## 5. Importing a future BMS / CIEM export

The adapter interface (`linkage_engine.BmsMappingAdapter`) accepts a CSV whose
exact column naming is unknown; it tolerates common aliases
(e.g. `sensor_id`/`device_id`/`uuid`/`device_uuid`, `space_id`, or a room key
like `room_number`/`ifc_name`/`revit`/`tag`) and runs the pipeline:

```
raw BMS rows -> validation -> canonical mapping -> evidence attribution
```

Validation rejects rows whose sensor is not in the CampusIQ registry, whose
`space_id` is unknown or ambiguous, or whose room key matches no / multiple
IFC spaces — it never coerces or invents a link. A valid row becomes a
CONFIRMED mapping with a `bms_registry` (or `ciem_registry`) evidence entry
attributed to the exact source file.

The adapter is **purely functional**: it returns `{imported, rejected}` and
writes nothing. Callers merge via `linkage_engine.apply_import(current,
imported)`, which upgrades UNRESOLVED/PROVISIONAL records to CONFIRMED while
keeping a `history[]` trace, and refuses to downgrade an existing CONFIRMED
record. No fake BMS data exists in the repository; tests exercise the adapter
only with an explicitly synthetic in-memory fixture that never touches any
output artefact.

## 6. Connecting mappings to IFC spaces

A resolved mapping's `space_id` is a M3.1 canonical id (`space_<IfcGlobalId>`),
directly joinable to `output/spaces.json`. A future BMS row typically carries a
room number or the source Revit Element Id; both resolve to the same
`IfcSpace` through the adapter's space index (built from `ifc_global_id`,
`ifc_name`, `ifc_long_name`, `ifc_tag`, `space_id`), then branch upward to
storey and building via `campus_registry.json`:

```
sensor UUID -> BMS/CIEM registry row -> room/Revit Id -> IfcSpace
   -> space_id (output/spaces.json) -> storey_id / building_id (registry)
```

## 7. Query API and the location-veracity principle

Pure-Python functions operate on any mapping list (no framework coupling):
`get_sensor_mapping`, `get_space_sensors`, `get_unresolved_sensors`,
`get_confirmed_mappings`, `get_provisional_mappings`, and
`get_mapping_statistics`. Each record exposes `location_status` and
`location_verified`, so downstream modules (anomaly detection, room-level
energy, recommendations, digital-twin views) can always tell whether a sensor's
data is a **VERIFIED_LOCATION** or **UNKNOWN_LOCATION** — unknown-location data
can never silently masquerade as room-specific.

## 8. Files

- `scripts/linkage_engine.py` — model, evidence, candidate audit, query API, BMS adapter
- `scripts/ingest_sensor_data.py` — M3 producer; mapping artefact now delegated to the engine (single schema source)
- `output/sensor_space_mapping.json` — canonical mapping artefact (v2)
- `output/sensor_space_candidates.json` — candidate slots + signal audit
- `tests/test_linkage_engine.py` — the 14 M4 validation items + adapter tests
- `tests/test_sensor_ingestion.py` — M3 suite; mapping assertions upgraded to the canonical schema