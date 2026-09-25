# M8 — Product UI (CampusIQ Operations Console)

Single-page web application that turns the M1–M7 pipeline outputs into a usable
product. Consumes the M7 FastAPI backend (`scripts/api_app.py`) as the **single
source of truth**; the frontend contains **no duplicate business logic** and no
fabricated data — every number in the UI is served by an API endpoint.

---

## 1. Frontend files

```
frontend/
  index.html, vite.config.ts, package.json, README.md, tsconfig*.json
  public/models/campus_twin.glb      # deterministic twin asset (147 KB)
  public/models/twin_manifest.json   # twin provenance + space/storey registry
  src/
    main.tsx, App.tsx                # entry + lazy route table
    index.css                        # Tailwind v4 theme + base styles
    api/
      client.ts                      # fetch wrapper, ApiError, query builder
      index.ts                       # typed endpoint functions (all of /api)
      types.ts                       # response types mirroring api_app.py
      client.test.ts
    hooks/useApi.ts                  # LOADING / READY / EMPTY / ERROR loader
    lib/format.ts                    # formatters, palettes, pure mappings
    lib/format.test.ts
    components/
      common.tsx                     # Panel, Stat, Badge, Pager, states
      layout.tsx                     # sidebar + header + backend-status probe
      TwinViewer.tsx                 # 3D react-three-fiber scene
      BimSpacePanel.tsx              # BIM DESIGN DATA inspector
    pages/
      Overview.tsx (+test)
      DigitalTwin.tsx
      Intelligence.tsx, intelligenceTabs.tsx, RecDetail.tsx (+tests)
      WhatIf.tsx (+test)
    test/setup.ts                    # fetch mock + fixtures
```

Vite config: React + Tailwind v4 plugins; dev and preview servers proxy
`/api` → `http://127.0.0.1:8000` (override via `VITE_API_TARGET`). Separate
`VITE_API_URL` supports an absolute base when the UI is hosted elsewhere.

## 2. Pages

| Route | Content |
|---|---|
| `/` **Overview** | Campus KPIs (buildings/storeys/spaces/sensors/channels/readings), anomaly watch, decision-candidate severity bars, operational readiness (sensor health, forecast availability, mapping status), sensor-location mapping + data-status cards, top 5 recommendations linking into Intelligence. |
| `/twin` **Digital Twin** | 3D schematic twin with orbit / zoom / pan, storey navigation chips (+elevations), space hover + click selection, BIM DESIGN DATA inspector, honesty note. |
| `/intelligence` **Intelligence** | Tabs: Anomalies (severity filter, value vs expected vs deviation), Forecasts (predicted vs baseline, horizon, method, 95% CI availability), Recommendations (list → full detail: scoring factors/factor-basis, evidence chain, expected impact, constraints, data quality), Decision candidates, Sensor health. |
| `/what-if` **What-If** | Allocation scenario form → computes results only by calling POST `/api/allocation/evaluate`; renders qualified vs excluded spaces with per-space reasons. |

## 3. API integration

Every endpoint the UI needs is typed in `src/api/types.ts` and called through
`src/api/index.ts` — no raw JSON artefact reads, no `fetch` outside the client.

- `GET /api/campus`, `/api/spaces`, `/api/resources`
- `GET /api/dashboard/summary`
- `GET /api/telemetry/summary`
- `GET /api/anomalies`, `/api/forecasts`, `/api/recommendations`,
  `/api/recommendations/{id}`, `/api/decision-candidates`, `/api/health`
- `POST /api/allocation/evaluate`

All `List` endpoints use the existing envelope `{items,total,limit,offset}` and
server-side pagination + `Pager` UI. `GET /api/recommendations/{id}` powers the
detail view via `?rec=<id>`.

## 4. Digital Twin

- Asset generator: `scripts/build_twin.py` — dependency-free, deterministic
  (sorted keys, seeded layout) builder producing a glTF 2.0 binary (`GLB`) with
  115 space meshes across 5 storey groups + 4 semi-transparent floor slabs,
  plus `twin_manifest.json`.
- **Honesty**: values are real M4 IFC quantities (area/volume/height per space,
  storey elevations +Kelder −3.5 / 1.k 0.0 / 2.k 4.9 / 3.k 9.8 / Katus 14.51).
  Per-space XZ placement is a deterministic schematic grid; the manifest's
  `honesty_note` states it is *not* the tessellated IFC mesh (ifcopenshell's C++
  tessellation is unreliable in this environment and was deliberately not
  depended on).
- Viewer: multi-storey overlap-free navigation (materials per storey), floor
  transparency, hover/selection highlight, auto-orbit toggle, orbit/zoom/pan.
- Inspector panel is labelled **BIM DESIGN DATA** (space id, IFC name, storey,
  area, volume, height, capacity, occupiable, conditioning). Where the
  sensor→space mapping is unresolved (all sensors in this release) the panel
  states *"Operational sensor mapping unavailable"* — no invented telemetry is
  attached to rooms.

## 5. What-If

Pure form → API. Inputs: required capacity, equipment selection, optional
explicit availability map (built from actual `/api/spaces` ids), request id.
Result panel renders `qualified` with qualification reasons and `excluded` with
humanised exclusion phrases (insufficient capacity / not occupiable / etc.),
plus `satisfied`, note and `generated_at`. Nothing is computed client-side
except visual mapping of server reasons.

## 6. Honesty & unknown states

- Sensor→space mapping is globally `UNRESOLVED` → the UI surfaces this in
  Overview and in each affected panel (amber "mapping unavailable" notes); the
  twin inspector never invents locations.
- Energy action impact `UNKNOWN` (null kWh) → rendered as "unquantified" with
  the `UNKNOWN` badge and the reason shown.
- Forecast CI presence (`coverage.confidence_intervals_calculated`) is shown as
  yes/no; no CI values are fabricated.
- Loading (spinner), empty (∅ with message), and error states (actionable
  "start the backend" guidance) are handled on every data view.

## 7. Tests

- **Frontend (17 passing / 5 files)**: fetch-wrapper error mapping & query
  building, endpoint paths + POST body, formatters/palettes, severity-series
  ordering, What-If full flow (fill → POST → qualified/excluded reasons),
  empty/error states, Overview KPIs + nav, recommendation detail evidence
  chain. `npx vitest run` ✔.
- **Typecheck**: `npx tsc -b` clean ✔.
- **Backend regression**: full suite re-run `python3 -m pytest tests -q`
  → **118 passed** in 95.41 s (M1–M7 unchanged) ✔.

## 8. Build result

`npm run build` (`tsc -b && vite build`) succeeds. Lazy route code-splitting:
main entry 276 KB (gzip 88 KB), three.js isolated in the DigitalTwin chunk
(~980 KB, loaded only on `/twin`). The build logs a chunk-size suggestion for
the three.js chunk — accepted, since it is already on-demand and gzip is 268 KB.

## 9. Run commands

```bash
# Backend (from …/hackathon/scripts)
uvicorn api_app:app --port 8000

# Frontend (from …/hackathon/frontend)
npm install
npm run dev              # http://localhost:5173, /api proxied to :8000
# production:
npm run build            # -> dist/
npm run preview          # serves dist + proxies /api
# checks:
npm run typecheck && npm run vitest
```

Verified live: dev server serves the app, `/api` proxy returns real data
(campus 115 spaces, 98 recommendations), `campus_twin.glb` (147 KB) serves,
`/twin` SPA route returns 200.

## 10. Limitations

- Sensor→space mapping is unresolved across the whole dataset, so no live
  telemetry is bound to twin rooms; the inspector shows BIM design data only.
- Twin is a schematic footprint extrusion (deterministic grid placement) — the
  real tessellated IFC mesh is deferred to a follow-up (needs a reliable
  geometry tessellation path).
- Measured energy is absent → energy savings remain `UNKNOWN`; What-If is
  capacity/equipment-only.
- three.js chunk is heavy (~980 KB) but lazy-loaded; could be reduced further
  via manual chunk splits or drei tree-shaking.

## 11. Next task (recommended)

Add sensor-to-space location resolution (M9): use sensor physical-position
metadata (if available) or an operator-confirmation workflow to move
`mapping.status` from UNRESOLVED to CONFIRMED/PROVISIONAL. That unlocks
room-bound telemetry overlays in the twin, measured-energy-based impact
estimates, and data-quality weighted recommendations — turning the M8 console
from a BIM+telemetry overview into a fully location-aware operations product.