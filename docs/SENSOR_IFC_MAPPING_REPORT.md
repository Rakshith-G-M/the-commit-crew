# TalTech Sensor <-> IFC Space Mapping — Investigation Report

- **Task**: M1-SENSOR-IFC-MAPPING
- **Generated**: 2026-09-24T19:19:38
- **IFC source**: `/Users/rakshith/Documents/hackathon/DS3_TalTech_V4.ifc`
- **Sensor dataset**: `/Users/rakshith/Documents/hackathon/Taltech.zip`

## Executive summary

> **No reliable sensor-to-IFC-space mapping could be established from the provided files alone.** The two datasets share no identifier. All 36 sensor devices are therefore reported as UNMAPPED. The IFC-space identity layer is fully characterized (115 spaces, Revit Element Ids in `IfcSpaceType.Tag`), and the sensor side is fully characterized (36 devices / 69 channels). The missing piece is an external asset/BMS key that connects device UUID to an IfcSpace GlobalId, Tag or storey.

## 1. Dataset structure

- ZIP: `Taltech.zip` (5,727,705 bytes), 69 CSV files, 1,390,297 rows total.
- Every CSV shares the identical 5-column schema `device_id,timestamp,meas_type,value,unit` (verified over every row).
- Filename pattern: `{UUID}_{SENSORTYPE}.csv`; the UUID equals the `device_id` column (verified).
- Sensor files by type: {'temperature': 29, 'energy': 4, 'pm2.5': 3, 'humidity': 26, 'co2': 7}.
- Unique devices: 36; median sampling ~899.0 s.

### CSV schema (identical across all 69 files)

| column | example | role |
|---|---|---|
| device_id | `7a0b43e6-…-feddd15131c5` | sensor device UUID (same as filename) |
| timestamp | `2024-07-18T04:30:00` | ISO-8601 measurement time |
| meas_type | `TEMPERATURESENSOR` | channel type |
| value | `20.94` | measurement |
| unit | `C`, `%`, `ppm`, `µg/m3`, `kWh` | unit |

**No room, space, storey, building or location field exists in any CSV.**

## 2. IFC structure

- Schema: **IFC4** (`IFC4`).
- **115 IfcSpace** entities.
- Storey distribution: {'+Kelder': 44, '1. korrus': 29, '3. korrus': 24, '2. korrus': 18}.
- Storeys: `+Kelder`, `1. korrus`, `2. korrus`, `3. korrus`, `Katus`.
- No `IfcSensor`, `IfcSensorType`, `IfcFlowInstrument` or `IfcAnnotation` entities exist.
- 0 sensor-like entities were found (none). The IFC contains mechanical systems (IfcPipeSegment, IfcSpaceHeater, …) but **no sensor devices**.

### Space identity encoding (KEY FINDING)

Each IfcSpace is linked 1:1 (via `IfcRelDefinesByType`) to an `IfcSpaceType` whose `Name`/`Tag` encode the source Revit Element Id:

| IfcSpace | GlobalId | IfcSpaceType.Name | IfcSpaceType.Tag (Revit Id) | Storey |
|---|---|---|---|---|
| Space 1 | `3WAA5EqJ58HBqF0jqdih16` | Space 1:4165094 | 4165094 | +Kelder |
| Space 2 | `3WAA5EqJ58HBqF0jqdih18` | Space 2:4165096 | 4165096 | +Kelder |
| Space 3 | `3WAA5EqJ58HBqF0jqdih1A` | Space 3:4165098 | 4165098 | +Kelder |
| Space 4 | `3WAA5EqJ58HBqF0jqdih1C` | Space 4:4165100 | 4165100 | +Kelder |
| Space 5 | `3WAA5EqJ58HBqF0jqdih1E` | Space 5:4165102 | 4165102 | +Kelder |
| Space 6 | `3WAA5EqJ58HBqF0jqdih1G` | Space 6:4165104 | 4165104 | +Kelder |
| Space 7 | `3WAA5EqJ58HBqF0jqdih1I` | Space 7:4165106 | 4165106 | +Kelder |
| Space 8 | `3WAA5EqJ58HBqF0jqdih1K` | Space 8:4165108 | 4165108 | +Kelder |
| Space 9 | `3WAA5EqJ58HBqF0jqdih1M` | Space 9:4165110 | 4165110 | +Kelder |
| Space 10 | `3WAA5EqJ58HBqF0jqdih1O` | Space 10:4165112 | 4165112 | +Kelder |
| Space 11 | `3WAA5EqJ58HBqF0jqdih1Q` | Space 11:4165114 | 4165114 | +Kelder |
| Space 12 | `3WAA5EqJ58HBqF0jqdih1S` | Space 12:4165116 | 4165116 | +Kelder |
| Space 13 | `3WAA5EqJ58HBqF0jqdihEZ` | Space 13:4165123 | 4165123 | +Kelder |
| Space 14 | `3WAA5EqJ58HBqF0jqdihEb` | Space 14:4165125 | 4165125 | +Kelder |
| Space 15 | `3WAA5EqJ58HBqF0jqdihEd` | Space 15:4165127 | 4165127 | +Kelder |
| Space 16 | `3WAA5EqJ58HBqF0jqdihEf` | Space 16:4165129 | 4165129 | +Kelder |
| Space 17 | `3WAA5EqJ58HBqF0jqdihEh` | Space 17:4165131 | 4165131 | +Kelder |
| Space 18 | `3WAA5EqJ58HBqF0jqdihEj` | Space 18:4165133 | 4165133 | +Kelder |
| Space 19 | `3WAA5EqJ58HBqF0jqdihEl` | Space 19:4165135 | 4165135 | +Kelder |
| Space 20 | `3WAA5EqJ58HBqF0jqdihEn` | Space 20:4165137 | 4165137 | +Kelder |
| Space 21 | `3WAA5EqJ58HBqF0jqdihEp` | Space 21:4165139 | 4165139 | +Kelder |
| Space 22 | `3WAA5EqJ58HBqF0jqdihEr` | Space 22:4165141 | 4165141 | +Kelder |
| Space 23 | `3WAA5EqJ58HBqF0jqdihEt` | Space 23:4165143 | 4165143 | +Kelder |
| Space 24 | `3WAA5EqJ58HBqF0jqdihEv` | Space 24:4165145 | 4165145 | +Kelder |
| Space 25 | `3WAA5EqJ58HBqF0jqdihEx` | Space 25:4165147 | 4165147 | +Kelder |
| Space 26 | `3WAA5EqJ58HBqF0jqdihEz` | Space 26:4165149 | 4165149 | +Kelder |
| Space 27 | `3WAA5EqJ58HBqF0jqdihE$` | Space 27:4165151 | 4165151 | +Kelder |
| Space 28 | `3WAA5EqJ58HBqF0jqdihE1` | Space 28:4165153 | 4165153 | +Kelder |
| Space 29 | `3WAA5EqJ58HBqF0jqdihE3` | Space 29:4165155 | 4165155 | +Kelder |
| Space 30 | `3WAA5EqJ58HBqF0jqdihE5` | Space 30:4165157 | 4165157 | +Kelder |
| Space 31 | `3WAA5EqJ58HBqF0jqdihE7` | Space 31:4165159 | 4165159 | +Kelder |
| Space 32 | `3WAA5EqJ58HBqF0jqdihE9` | Space 32:4165161 | 4165161 | +Kelder |
| Space 33 | `3WAA5EqJ58HBqF0jqdihEB` | Space 33:4165163 | 4165163 | +Kelder |
| Space 34 | `3WAA5EqJ58HBqF0jqdihED` | Space 34:4165165 | 4165165 | +Kelder |
| Space 35 | `3WAA5EqJ58HBqF0jqdihEF` | Space 35:4165167 | 4165167 | +Kelder |
| Space 36 | `3WAA5EqJ58HBqF0jqdihEH` | Space 36:4165169 | 4165169 | +Kelder |
| Space 37 | `3WAA5EqJ58HBqF0jqdihEJ` | Space 37:4165171 | 4165171 | +Kelder |
| Space 38 | `3WAA5EqJ58HBqF0jqdihEL` | Space 38:4165173 | 4165173 | +Kelder |
| Space 39 | `3WAA5EqJ58HBqF0jqdihEN` | Space 39:4165175 | 4165175 | +Kelder |
| Space 40 | `3WAA5EqJ58HBqF0jqdihEP` | Space 40:4165177 | 4165177 | +Kelder |
| Space 41 | `3WAA5EqJ58HBqF0jqdihER` | Space 41:4165179 | 4165179 | +Kelder |
| Space 42 | `3WAA5EqJ58HBqF0jqdihET` | Space 42:4165181 | 4165181 | +Kelder |
| Space 43 | `3WAA5EqJ58HBqF0jqdihEV` | Space 43:4165183 | 4165183 | +Kelder |
| Space 44 | `3WAA5EqJ58HBqF0jqdihFX` | Space 44:4165185 | 4165185 | +Kelder |
| Space 45 | `3WAA5EqJ58HBqF0jqdihFg` | Space 45:4165194 | 4165194 | 1. korrus |
| Space 46 | `3WAA5EqJ58HBqF0jqdihFx` | Space 46:4165211 | 4165211 | 1. korrus |
| Space 47 | `3WAA5EqJ58HBqF0jqdihFz` | Space 47:4165213 | 4165213 | 1. korrus |
| Space 48 | `3WAA5EqJ58HBqF0jqdihF$` | Space 48:4165215 | 4165215 | 1. korrus |
| Space 49 | `3WAA5EqJ58HBqF0jqdihF1` | Space 49:4165217 | 4165217 | 1. korrus |
| Space 50 | `3WAA5EqJ58HBqF0jqdihF3` | Space 50:4165219 | 4165219 | 1. korrus |
| Space 51 | `3WAA5EqJ58HBqF0jqdihF5` | Space 51:4165221 | 4165221 | 1. korrus |
| Space 52 | `3WAA5EqJ58HBqF0jqdihF7` | Space 52:4165223 | 4165223 | 1. korrus |
| Space 53 | `3WAA5EqJ58HBqF0jqdihF9` | Space 53:4165225 | 4165225 | 1. korrus |
| Space 54 | `3WAA5EqJ58HBqF0jqdihFB` | Space 54:4165227 | 4165227 | 1. korrus |
| Space 55 | `3WAA5EqJ58HBqF0jqdihFD` | Space 55:4165229 | 4165229 | 1. korrus |
| Space 56 | `3WAA5EqJ58HBqF0jqdihFF` | Space 56:4165231 | 4165231 | 1. korrus |
| Space 57 | `3WAA5EqJ58HBqF0jqdihFH` | Space 57:4165233 | 4165233 | 1. korrus |
| Space 58 | `3WAA5EqJ58HBqF0jqdihFJ` | Space 58:4165235 | 4165235 | 1. korrus |
| Space 59 | `3WAA5EqJ58HBqF0jqdihFL` | Space 59:4165237 | 4165237 | 1. korrus |
| Space 60 | `3WAA5EqJ58HBqF0jqdihFN` | Space 60:4165239 | 4165239 | 1. korrus |
| Space 61 | `3WAA5EqJ58HBqF0jqdihFP` | Space 61:4165241 | 4165241 | 1. korrus |
| Space 62 | `3WAA5EqJ58HBqF0jqdihFR` | Space 62:4165243 | 4165243 | 1. korrus |
| Space 63 | `3WAA5EqJ58HBqF0jqdihFT` | Space 63:4165245 | 4165245 | 1. korrus |
| Space 64 | `3WAA5EqJ58HBqF0jqdihFV` | Space 64:4165247 | 4165247 | 1. korrus |
| Space 65 | `3WAA5EqJ58HBqF0jqdihCX` | Space 65:4165249 | 4165249 | 1. korrus |
| Space 66 | `3WAA5EqJ58HBqF0jqdihCZ` | Space 66:4165251 | 4165251 | 1. korrus |
| Space 67 | `3WAA5EqJ58HBqF0jqdihCb` | Space 67:4165253 | 4165253 | 1. korrus |
| Space 68 | `3WAA5EqJ58HBqF0jqdihCd` | Space 68:4165255 | 4165255 | 1. korrus |
| Space 69 | `3WAA5EqJ58HBqF0jqdihCf` | Space 69:4165257 | 4165257 | 1. korrus |
| Space 70 | `3WAA5EqJ58HBqF0jqdihCh` | Space 70:4165259 | 4165259 | 1. korrus |
| Space 71 | `3WAA5EqJ58HBqF0jqdihCj` | Space 71:4165261 | 4165261 | 1. korrus |
| Space 72 | `3WAA5EqJ58HBqF0jqdihCl` | Space 72:4165263 | 4165263 | 1. korrus |
| Space 73 | `3WAA5EqJ58HBqF0jqdihCn` | Space 73:4165265 | 4165265 | 1. korrus |
| Space 74 | `3WAA5EqJ58HBqF0jqdihD6` | Space 74:4165350 | 4165350 | 2. korrus |
| Space 75 | `3WAA5EqJ58HBqF0jqdihD9` | Space 75:4165353 | 4165353 | 2. korrus |
| Space 76 | `3WAA5EqJ58HBqF0jqdihDB` | Space 76:4165355 | 4165355 | 2. korrus |
| Space 77 | `3WAA5EqJ58HBqF0jqdihDD` | Space 77:4165357 | 4165357 | 2. korrus |
| Space 78 | `3WAA5EqJ58HBqF0jqdihDF` | Space 78:4165359 | 4165359 | 2. korrus |
| Space 79 | `3WAA5EqJ58HBqF0jqdihDH` | Space 79:4165361 | 4165361 | 2. korrus |
| Space 80 | `3WAA5EqJ58HBqF0jqdihDJ` | Space 80:4165363 | 4165363 | 2. korrus |
| Space 81 | `3WAA5EqJ58HBqF0jqdihDL` | Space 81:4165365 | 4165365 | 2. korrus |
| Space 82 | `3WAA5EqJ58HBqF0jqdihDN` | Space 82:4165367 | 4165367 | 2. korrus |
| Space 83 | `3WAA5EqJ58HBqF0jqdihDP` | Space 83:4165369 | 4165369 | 2. korrus |
| Space 84 | `3WAA5EqJ58HBqF0jqdihDR` | Space 84:4165371 | 4165371 | 2. korrus |
| Space 85 | `3WAA5EqJ58HBqF0jqdihDT` | Space 85:4165373 | 4165373 | 2. korrus |
| Space 86 | `3WAA5EqJ58HBqF0jqdihDV` | Space 86:4165375 | 4165375 | 2. korrus |
| Space 87 | `3WAA5EqJ58HBqF0jqdihAX` | Space 87:4165377 | 4165377 | 2. korrus |
| Space 88 | `3WAA5EqJ58HBqF0jqdihAZ` | Space 88:4165379 | 4165379 | 2. korrus |
| Space 89 | `3WAA5EqJ58HBqF0jqdihAb` | Space 89:4165381 | 4165381 | 2. korrus |
| Space 90 | `3WAA5EqJ58HBqF0jqdihAd` | Space 90:4165383 | 4165383 | 2. korrus |
| Space 91 | `3WAA5EqJ58HBqF0jqdihAf` | Space 91:4165385 | 4165385 | 2. korrus |
| Space 92 | `3U1W8Xs6L9pRXU5Afk5MWq` | Space 92:4165454 | 4165454 | 3. korrus |
| Space 93 | `3U1W8Xs6L9pRXU5Afk5MWh` | Space 93:4165457 | 4165457 | 3. korrus |
| Space 94 | `3U1W8Xs6L9pRXU5Afk5MWf` | Space 94:4165459 | 4165459 | 3. korrus |
| Space 95 | `3U1W8Xs6L9pRXU5Afk5MWl` | Space 95:4165461 | 4165461 | 3. korrus |
| Space 96 | `3U1W8Xs6L9pRXU5Afk5MWj` | Space 96:4165463 | 4165463 | 3. korrus |
| Space 97 | `3U1W8Xs6L9pRXU5Afk5MWZ` | Space 97:4165465 | 4165465 | 3. korrus |
| Space 98 | `3U1W8Xs6L9pRXU5Afk5MWX` | Space 98:4165467 | 4165467 | 3. korrus |
| Space 99 | `3U1W8Xs6L9pRXU5Afk5MWd` | Space 99:4165469 | 4165469 | 3. korrus |
| Space 100 | `3U1W8Xs6L9pRXU5Afk5MWb` | Space 100:4165471 | 4165471 | 3. korrus |
| Space 101 | `3U1W8Xs6L9pRXU5Afk5MWR` | Space 101:4165473 | 4165473 | 3. korrus |
| Space 102 | `3U1W8Xs6L9pRXU5Afk5MWP` | Space 102:4165475 | 4165475 | 3. korrus |
| Space 103 | `3U1W8Xs6L9pRXU5Afk5MWV` | Space 103:4165477 | 4165477 | 3. korrus |
| Space 104 | `3U1W8Xs6L9pRXU5Afk5MWT` | Space 104:4165479 | 4165479 | 3. korrus |
| Space 105 | `3U1W8Xs6L9pRXU5Afk5MWJ` | Space 105:4165481 | 4165481 | 3. korrus |
| Space 106 | `3U1W8Xs6L9pRXU5Afk5MWH` | Space 106:4165483 | 4165483 | 3. korrus |
| Space 107 | `3U1W8Xs6L9pRXU5Afk5MWN` | Space 107:4165485 | 4165485 | 3. korrus |
| Space 108 | `3U1W8Xs6L9pRXU5Afk5MWL` | Space 108:4165487 | 4165487 | 3. korrus |
| Space 109 | `3U1W8Xs6L9pRXU5Afk5MWB` | Space 109:4165489 | 4165489 | 3. korrus |
| Space 110 | `3U1W8Xs6L9pRXU5Afk5MW9` | Space 110:4165491 | 4165491 | 3. korrus |
| Space 111 | `3U1W8Xs6L9pRXU5Afk5MWF` | Space 111:4165493 | 4165493 | 3. korrus |
| Space 112 | `3U1W8Xs6L9pRXU5Afk5MWD` | Space 112:4165495 | 4165495 | 3. korrus |
| Space 113 | `3U1W8Xs6L9pRXU5Afk5MW3` | Space 113:4165497 | 4165497 | 3. korrus |
| Space 114 | `3U1W8Xs6L9pRXU5Afk5MW1` | Space 114:4165499 | 4165499 | 3. korrus |
| Space 115 | `3U1W8Xs6L9pRXU5Afk5MW7` | Space 115:4165501 | 4165501 | 3. korrus |

## 3. Sensor categories observed

| category | CSV suffix | unit | files | rows | typical interval |
|---|---|---|---:|---:|---:|
| temperature | TEMPERATURESENSOR | C | 29 | - | ~600 s |
| humidity | HUMIDITYSENSOR | % | 26 | - | ~900 s |
| CO2 | CO2SENSOR | ppm | 7 | - | ~600 s |
| PM2.5 | PM25SENSOR | µg/m3 | 3 | - | ~600 s |
| energy | ENERGYMETER | kWh | 4 | - | ~900 s (delta-only) |

Temperature + humidity are co-located on 26 shared devices; CO2 is co-located on several of them (multi-channel devices).

## 4. Identifier analysis

- Sensor identifiers are **device UUIDs** only (filename + `device_id`).
- IFC identifiers are **IfcGlobalIds**, sequential `Name` values, and **Revit Element Ids** in `IfcSpaceType.Tag`.
- The IFC contains **only two** UUID-shaped strings: a `VersionGUID` in `FILE_DESCRIPTION` and a `Loss Method` property value — neither is a sensor device UUID.
- **Direct search result:** of 36 device UUIDs, **0** appear anywhere in the IFC text.
- **Reverse search result:** no space Revit Element Id (e.g. `4165094`) appears in any CSV value or filename.
- **Conclusion**: there is **no direct identifier match** between the two datasets (`{J['identifier_analysis']['device_uuids_found_in_ifc']}` UUID hits).

## 5. Indirect mapping investigation

- ZIP archive contains **no metadata files**: no JSON/XML/README/device inventory/room list/database export; no archive comments; 69 CSV entries only.
- CSV content is strictly the 5-column time series; no 6th column, no multi-record rows (verified over all 1,390,297 rows).
- `IfcZone`/`IfcSystem` carry mechanical/zone names only (`School:4343393`, `Non_Conditioned:4502359`, ventilation/DHW systems); no sensor references.
- No property set anywhere in the IFC references a sensor device UUID.
- **There is no hidden mapping table in the supplied dataset.**

## 6. Mapping mechanism (discovered, for future execution)

Once an external key is available, the *mechanism* to use is:

```
sensor UUID (CSV filename / device_id)
        |   via: external asset/BMS registry   (NOT present in files)
        v
room / space key   ->   IfcSpace
        -> IfcSpace.GlobalId (e.g. 3WAA5EqJ58HBqF0jqdih16)
        -> IfcSpace.Name (sequential 1..115)
        -> IfcSpaceType.Tag / Revit Element Id (e.g. 4165094)
        -> Storey (+Kelder, 1./2./3. korrus, Katus)
```

## 7. Mapping coverage

- Devices total: 36
- Mapped: 0 (HIGH 0, MEDIUM 0, LOW 0)
- Unmapped: 36

| Sensor ID | Type | IFC Space | Method | Evidence | Confidence |
|---|---|---|---|---|---|
| 04f80f82-e206-427c-a913-69758a1ec283 | temperature | none | none_found | CSV carries only device_id UUID, timestamp, meas_type, value, unit; no room/space/building identifier present. Device UU | UNMAPPED |
| 065931eb-3930-492c-ac91-85a0936fcf82 | energy | none | none_found | CSV carries only device_id UUID, timestamp, meas_type, value, unit; no room/space/building identifier present. Device UU | UNMAPPED |
| 08e2d921-2317-4642-b003-90bc1fce878a | pm2.5 | none | none_found | CSV carries only device_id UUID, timestamp, meas_type, value, unit; no room/space/building identifier present. Device UU | UNMAPPED |
| 2522f700-8446-4619-9399-23b97d077209 | humidity,temperature | none | none_found | CSV carries only device_id UUID, timestamp, meas_type, value, unit; no room/space/building identifier present. Device UU | UNMAPPED |
| 2cc97dbf-8e73-475b-a2e7-cecdb74e7838 | energy | none | none_found | CSV carries only device_id UUID, timestamp, meas_type, value, unit; no room/space/building identifier present. Device UU | UNMAPPED |
| 33281c95-d69f-4611-a0c7-38790e115426 | energy | none | none_found | CSV carries only device_id UUID, timestamp, meas_type, value, unit; no room/space/building identifier present. Device UU | UNMAPPED |
| 37b7c0e4-9943-489e-98a9-2ab4796a7d94 | humidity,temperature | none | none_found | CSV carries only device_id UUID, timestamp, meas_type, value, unit; no room/space/building identifier present. Device UU | UNMAPPED |
| 3ca720cf-53ac-4326-9c09-c435c4d4e13a | energy | none | none_found | CSV carries only device_id UUID, timestamp, meas_type, value, unit; no room/space/building identifier present. Device UU | UNMAPPED |
| 421151cb-043f-4ccc-844d-ff94cd659f2b | humidity,temperature | none | none_found | CSV carries only device_id UUID, timestamp, meas_type, value, unit; no room/space/building identifier present. Device UU | UNMAPPED |
| 42cb320d-b911-4648-bb65-f0d54984551d | humidity,temperature | none | none_found | CSV carries only device_id UUID, timestamp, meas_type, value, unit; no room/space/building identifier present. Device UU | UNMAPPED |
| 4565853e-95df-4027-8b05-82d26bf6eec1 | humidity,temperature | none | none_found | CSV carries only device_id UUID, timestamp, meas_type, value, unit; no room/space/building identifier present. Device UU | UNMAPPED |
| 45f91780-63fc-4d24-bf64-0e42c440fca5 | temperature | none | none_found | CSV carries only device_id UUID, timestamp, meas_type, value, unit; no room/space/building identifier present. Device UU | UNMAPPED |
| 4dcb026e-d888-4e84-9892-6e81d487a214 | humidity,temperature | none | none_found | CSV carries only device_id UUID, timestamp, meas_type, value, unit; no room/space/building identifier present. Device UU | UNMAPPED |
| 6690d4cb-bb58-47a8-b0f8-be2e99056be0 | humidity,temperature | none | none_found | CSV carries only device_id UUID, timestamp, meas_type, value, unit; no room/space/building identifier present. Device UU | UNMAPPED |
| 76824528-d7e4-423b-b818-8f900b41d6fb | humidity,temperature | none | none_found | CSV carries only device_id UUID, timestamp, meas_type, value, unit; no room/space/building identifier present. Device UU | UNMAPPED |
| 79c625d4-2530-4332-903e-82d480563c75 | humidity,temperature | none | none_found | CSV carries only device_id UUID, timestamp, meas_type, value, unit; no room/space/building identifier present. Device UU | UNMAPPED |
| 7a0b43e6-7a9b-48bc-84b8-feddd15131c5 | humidity,temperature | none | none_found | CSV carries only device_id UUID, timestamp, meas_type, value, unit; no room/space/building identifier present. Device UU | UNMAPPED |
| 81845c1a-5a2c-43eb-a443-8276649abb67 | humidity,temperature | none | none_found | CSV carries only device_id UUID, timestamp, meas_type, value, unit; no room/space/building identifier present. Device UU | UNMAPPED |
| 8af61c3a-e76f-45cb-abae-504c208d0ccb | humidity,temperature | none | none_found | CSV carries only device_id UUID, timestamp, meas_type, value, unit; no room/space/building identifier present. Device UU | UNMAPPED |
| 99ca72a1-36de-4e79-b65d-16cdec7e42fb | co2,humidity,temperature | none | none_found | CSV carries only device_id UUID, timestamp, meas_type, value, unit; no room/space/building identifier present. Device UU | UNMAPPED |
| 9a7e9493-2411-4213-a65b-1372023e02d3 | pm2.5 | none | none_found | CSV carries only device_id UUID, timestamp, meas_type, value, unit; no room/space/building identifier present. Device UU | UNMAPPED |
| 9b662d91-8343-46b6-848a-9c190d6d46b7 | humidity,temperature | none | none_found | CSV carries only device_id UUID, timestamp, meas_type, value, unit; no room/space/building identifier present. Device UU | UNMAPPED |
| a6bbc801-c605-4782-8d17-111c606cf662 | humidity,temperature | none | none_found | CSV carries only device_id UUID, timestamp, meas_type, value, unit; no room/space/building identifier present. Device UU | UNMAPPED |
| ad03002a-9ba7-4b0a-b055-2e981dfa95a2 | humidity,temperature | none | none_found | CSV carries only device_id UUID, timestamp, meas_type, value, unit; no room/space/building identifier present. Device UU | UNMAPPED |
| c6f4d193-bab8-438a-8706-d2f60e0ef81b | co2,humidity,temperature | none | none_found | CSV carries only device_id UUID, timestamp, meas_type, value, unit; no room/space/building identifier present. Device UU | UNMAPPED |
| d2948a1d-b2a0-435b-a9f6-abe67df61b70 | co2,humidity,temperature | none | none_found | CSV carries only device_id UUID, timestamp, meas_type, value, unit; no room/space/building identifier present. Device UU | UNMAPPED |
| d77ac61a-ca38-4030-810e-738161f81c7e | humidity,temperature | none | none_found | CSV carries only device_id UUID, timestamp, meas_type, value, unit; no room/space/building identifier present. Device UU | UNMAPPED |
| d9a2275e-351a-4095-9e35-7cae87c0112f | co2,humidity,temperature | none | none_found | CSV carries only device_id UUID, timestamp, meas_type, value, unit; no room/space/building identifier present. Device UU | UNMAPPED |
| dfd7a151-1cae-4cd6-b3af-91ff110a21b2 | humidity,temperature | none | none_found | CSV carries only device_id UUID, timestamp, meas_type, value, unit; no room/space/building identifier present. Device UU | UNMAPPED |
| e0f66126-28e9-4681-bf89-9ecccd961997 | humidity,temperature | none | none_found | CSV carries only device_id UUID, timestamp, meas_type, value, unit; no room/space/building identifier present. Device UU | UNMAPPED |
| e4373caf-650d-40e9-8f12-ec47d40eb1c2 | temperature | none | none_found | CSV carries only device_id UUID, timestamp, meas_type, value, unit; no room/space/building identifier present. Device UU | UNMAPPED |
| e720f446-3626-4318-a136-079529b57492 | pm2.5 | none | none_found | CSV carries only device_id UUID, timestamp, meas_type, value, unit; no room/space/building identifier present. Device UU | UNMAPPED |
| f4a76a84-7b19-4f32-a681-3eabdaeaaabe | co2,humidity,temperature | none | none_found | CSV carries only device_id UUID, timestamp, meas_type, value, unit; no room/space/building identifier present. Device UU | UNMAPPED |
| f5c3c0e6-cf08-439f-8d31-fc739c100455 | co2,humidity,temperature | none | none_found | CSV carries only device_id UUID, timestamp, meas_type, value, unit; no room/space/building identifier present. Device UU | UNMAPPED |
| f776d51d-bd6c-40a9-8af7-58142934ee9f | humidity,temperature | none | none_found | CSV carries only device_id UUID, timestamp, meas_type, value, unit; no room/space/building identifier present. Device UU | UNMAPPED |
| fa54ef81-7df5-41e7-a5e8-5d97a69dc151 | co2,humidity,temperature | none | none_found | CSV carries only device_id UUID, timestamp, meas_type, value, unit; no room/space/building identifier present. Device UU | UNMAPPED |

## 8. Unmapped / ambiguous sensors

All 36 devices are unmapped. No assignment was fabricated. Ambiguity: two CSVs (`dfd7a151…` temperature is the largest file; energy meters cover building/section level rather than a single space) have no space attribution at all.

## 9. Evidence & method

- All 69 CSV files profiled read-only (schema, rows, ranges, sampling, anomalies).
- All 115 IfcSpace + associated type/storey/pset extracted with IfcOpenShell 0.8.5.
- Exact-match search of all 36 device UUIDs against the raw IFC text.
- Exact-match search of space Revit Element Ids against all CSV cells.
- ZIP structure and comments inspected for hidden metadata.

## 10. Limitations

- Sensor locations are not present in any provided file.
- Geometry proximity could not be used: sensor coordinates are not published in the dataset.
- The Revit Element Id (`IfcSpaceType.Tag`) is the strongest IFC identifier for future external joins, but no external registry was provided for the M1 scope.

## 11. Recommended next step

1. Obtain the TalTech BMS / asset registry (or the device->room table that produced these UUIDs).
2. Join on device UUID; then join room to IfcSpace via Revit Element Id (`IfcSpaceType.Tag`) or `IfcSpace.GlobalId`.
3. Re-run `scripts/investigate_sensor_ifc_mapping.py` — the space registry and device registry are persisted and will produce a populated mapping on the next run.

---
*Report auto-generated by `scripts/investigate_sensor_ifc_mapping.py`.*