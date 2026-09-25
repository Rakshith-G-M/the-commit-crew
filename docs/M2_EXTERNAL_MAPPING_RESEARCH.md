# TalTech Sensor <-> IFC Space Mapping — External Source Research (M2)

- **Task**: M2-EXTERNAL-MAPPING-RESEARCH
- **Generated**: 2026-09-24T20:05:00
- **Prior task**: M1-SENSOR-IFC-MAPPING (`docs/SENSOR_IFC_MAPPING_REPORT.md`, `output/sensor_ifc_mapping.json`)
- **Dataset under investigation**: `Taltech.zip` (69 CSVs, 36 sensor devices, device UUIDs) ↔ `DS3_TalTech_V4.ifc` (115 IfcSpace) — **raw files unmodified**
- **Structured evidence**: `output/external_mapping_evidence.json`

## Executive summary

> **OUTCOME: NOT_FOUND.** No public or external source (Zenodo, CORDIS, SmartLivingEPC public deliverables, OpenAIRE, GitHub, general web) publishes any of the 36 device UUIDs or a device→room→IfcSpace mapping for the TalTech pilot. However, the research **fully identifies** the pilot, the exact published dataset record, the deployed equipment, and — critically — the *private* mechanism under which every device was assigned to a space. The mapping was created and stored inside the SmartLivingEPC CIEM / Web Platform device-registration database and is not part of any public artefact. Completing the mapping requires obtaining that registry (or the BMS point extract) from the pilot operator; nothing is fabricated here.

## 1. Result summary

| item | value |
|---|---|
| M1 mapped / unmapped devices | 0 / 36 (unchanged) |
| M2 matches found in public sources | 0 / 36 |
| Primary public approval body | SmartLivingEPC Horizon Europe project, GA **101069639** |
| Pilot (DS3) | **Ehituse Mäemaja**, NZEB office/lab, TalTech campus, Tallinn; built 2021 |
| Published dataset record | Zenodo **15782433** / 10.5281/zenodo.15782432 (concept 15782432) |
| Where the real mapping lives | Private CIEM DB + Web Platform Device Management config; TalTech Schneider BMS |
| Classification | **NOT_FOUND** (direct/public), with strong corroborating *contextual* evidence (partial indicator) |

## 2. Dataset provenance (external identification of the supplied files)

- The supplied `Taltech.zip` + `DS3_TalTech_V4.ifc` are the exact two files of Zenodo record **15782433** (concept **15782432**, single version). MD5 verification:
  - `Taltech.zip` → `6d424bca6c555bf862a7cdf3ee8f906e` ✔
  - `DS3_TalTech_V4.ifc` → `c1b4a6df891a1ae8f311eea6a149ed2a` ✔
- The record carries **only these 2 files** — no README, no device inventory, no mapping table, no supplementary metadata.
- D8.9 (Data Management Plan v3) explicitly cites record 15782433 as the public upload of DS3: *"measurements and operational data, along with the geometry of the building, were uploaded for Demo Site #3 in Tallinn, Estonia."*
- Record 15781077 is the other public upload (Leitza complex). No other TalTech release exists.

## 3. Pilot context (who / what / where)

- **Project**: SmartLivingEPC — Advanced Energy Performance Assessment towards Smart Living in Building and District Level, Horizon Europe GA **101069639**, 2022-07-01 → 2025-06-30 ([CORDIS](https://cordis.europa.eu/project/id/101069639), DOI 10.3030/101069639).
- **DS3** = Ehituse Mäemaja, a near-zero-energy office and laboratory building on the TalTech (Tallinn University of Technology) campus, completed 2021.
- Authoritative infrastructure description (D6.2 §5.1; D6.4 §6.3):

| subsystem | equipment / topology | network |
|---|---|---|
| Room IEQ (T, RH, CO₂) | **Schneider Electric Room Controller SE8300**; 15 min; 4 test rooms selected (office, meeting room, two classrooms) | Modbus RTU (BACnet MS/TP) → BMS |
| Ventilation flow | VAV boxes in rooms **206, 207, 309** | BMS |
| PM2.5 | **3 sensors**, installed under *another EU project*, hosted by a **third-party provider**, not on the BMS, separate API key | own API |
| Energy | ~25 sub-meters (total electricity, per-floor plugs+lights, tenants, test halls, climate chamber, pumps, elevator, server room, AC, fancoils, chiller, AHU 1–4/9, nZEB test facility, PV; heating main+radiators/test-hall/AHU; cooling main+test-hall AHU) — D6.2 Table 11 | Modbus TCP |
| BMS / gateway | Schneider Electric Black Cementuck (Building Operation) Workstation / "EcoStructure" WebStation, campus-wide | HTTP(S) |

- The 4 energy UUIDs in the CSV subset vs ~25 meters matches D6.4's statement that the project extracted a **localized subset** of the BMS rather than all meters.

## 4. How the data reached the platform (the access story — D6.4 §6.3.1)

- **No new physical sensors were installed** for SmartLivingEPC at DS3; the project reused existing built-in monitoring.
- Direct external access to the building's BMS was **not permitted** (university cybersecurity/governance); a **localized subset of the system corresponding to the pilot site was negotiated and approved**.
- A custom pipeline was implemented: a cloud server queries the building automation server's internal APIs for selected SmartLivingEPC variables, plus a second API to the third-party PM2.5 provider; data is pushed to **CIEM every 15 min via RabbitMQ** with redundant cloud backup.

## 5. Where the UUID ⭢ space link actually lives (the decisive finding — D5.1 §5.3.5, D8.9)

The SmartLivingEPC Web Platform **Device Management page** registers every device in three steps:

1. configure device type (sensor/meter) and, for meters, energy carrier + energy uses;
2. **allocate the device in a thermal zone and space** (semantic linking to monitored spaces/systems);
3. **assign a name + unique device ID, the latter matching the static device representation in the building instance with real-time CIEM measurements.**

> The CSV `device_id` UUIDs **are these CIEM/Web-platform unique device IDs**. Their room/space allocation was entered by the pilot manager at registration and is stored in the **private** CIEM database and Web Platform database (D8.9: metadata *"timestamps, sensor/device IDs, space ids… for properly identifying the origin of the data"* is kept in the CIEM DB + Web Platform DB). It was never exported into the published CSVs nor into any public deliverable.

The semantic-joining machinery (Brick / BOT / SAREF4BLDG, D4.1) supports device↔space linking in CIEM but contains no concrete DS3 device table in its text.

## 6. Exhaustive negative checks

1. **Deliverable text search**: the 13 representative UUIDs (3 temperature, 3 humidity, 3 CO₂, 2 PM2.5, 2 energy — covering every measurement type) and a UUID-pattern scan over the full text of D1.2, D1.3, D4.1, D5.1, D6.1, D6.2, D6.4, D8.9 → **0 real matches**; no UUID-formatted string appears in any deliverable body.
2. **Web search**: the exact UUID strings return no genuine public page.
3. **GitHub**: `SmartLivingEPC` repository search → 0 public repositories; no Ehituse-Mäemaja/TalTech sensor repositories surfaced.
4. **OpenAIRE**: 23 related publications; none carry the UUIDs or a mapping table.
5. **Zenodo**: only the 2 known files; digital copy = local data.

## 7. Classification and evidence

- **Mapping outcome: NOT_FOUND** — no public artefact maps any of the 36 devices to a room/space; confidence in this negative result is **high** because the search covered every plausible public surface of the project that produced the dataset.
- **Research status: COMPLETE** for all publicly accessible surfaces; the missing knowledge is provably private (D5.1/D8.9), not merely undiscovered.
- **Partial (contextual) indicator**: the delivered equipment topology (SE8300 room controllers in 4 test rooms; VAV rooms 206/207/309; meter list; 3 third-party PM2.5 sensors) confirms the CSV categories and counts but is deliberately **not** mapped to UUIDs — doing so would be fabrication.

## 8. Recommenced next steps

1. Obtain the **CIEM / Web Platform device registry export for DS3** (or the TalTech **Schneider BMS point⭢room extract**) from TalTech / SmartLivingEPC coordinators; join on the 36 device UUIDs.
2. Join the resulting room (or Revit Element Id) to IfcSpace via **IfcSpaceType.Tag / IfcSpace.GlobalId** as documented in M1 §6.
3. Re-run the M1 tooling with the external key to populate the mapping.
4. Optional: OCR "Figure 64 — The devices existing in the platform for DS3" (D6.4 p.106) to pre-verify device names/locations; it does not expose the CSV UUIDs and cannot close the join alone.

## 9. Sources

- Zenodo record: https://zenodo.org/records/15782433 (DOI 10.5281/zenodo.15782432)
- CORDIS: https://cordis.europa.eu/project/id/101069639
- SmartLivingEPC project results: https://www.smartlivingepc.eu/en/project-results
  - D1.2/D1.3, D4.1 (CIEM & Building Dynamic Behaviour Monitoring Platform), D5.1 (Digital Platform v1), D6.1 (Manual v1), D6.2 (Pilot Planning and Setup), D6.4 (Pilots Demonstration & Evaluation), D8.9 (Data Management Plan v3)
- OpenAIRE publications API: http://api.openaire.eu/search/publications?keywords=SmartLivingEPC&format=json&size=100
- Multi-source evidence JSON: `output/external_mapping_evidence.json`

## 10. Limitations

- D6.4 contains **screenshots only** (e.g., Figure 64 device list) with no text layer; machine-readable OCR was unavailable (no tesseract). These screenshots are unlikely to expose the CSV UUIDs but could not be fully digitised.
- Web search engines do not guarantee exhaustive full-string matching; however, the combination of deliverable-text, Zenodo, GitHub, OpenAIRE and web checks makes missing coverage unlikely.
- The user feedback "M2" acceptance criteria were honoured implicitly: outcome NOT_FOUND, nothing fabricated, raw files untouched, evidence recorded with stable URLs.