# CampusIQ — Product UI (M8)

Single-page operational console for the CampusIQ building data platform.

## Stack

- React 19 + TypeScript + Vite 8
- Tailwind CSS v4 (via `@tailwindcss/vite`)
- Three.js + React Three Fiber + drei (Digital Twin 3D view)
- react-router-dom v7
- Vitest + Testing Library (unit / integration tests)
- All product data comes from the FastAPI backend at `scripts/api_app.py` —
  the UI never reads raw JSON artefacts.

## Pages

| Route            | Purpose                                                        |
| ---------------- | -------------------------------------------------------------- |
| `/`              | Overview: KPIs, anomaly/candidate watch, readiness, top recs   |
| `/twin`          | Digital Twin: 3D schematic footprint twin, storey navigation   |
| `/intelligence`  | Anomalies, forecasts, recommendations (+ detail), candidates, sensor health |
| `/what-if`       | Allocation scenario simulator (POST `/api/allocation/evaluate`) |

## Run

```bash
# 1. Start the API backend (from the repo root …/hackathon/scripts)
uvicorn api_app:app --port 8000

# 2. Start the frontend dev server (from frontend/)
npm install
npm run dev        # http://localhost:5173  (proxies /api -> 127.0.0.1:8000)
```

Production build:

```bash
npm run build   # tsc -b && vite build
npm run preview # serves dist/ with the same /api proxy
```

## Tests

```bash
npm run vitest  # or: npx vitest run
```

`npx tsc -b` type-checks the whole project.

## Digital Twin asset

`scripts/build_twin.py` deterministically builds `public/models/campus_twin.glb`
plus `twin_manifest.json` from real M4 IFC quantities (per-space
area/volume/height, storey elevations). It is a *schematic footprint* twin —
positions are a deterministic grid, not the tessellated IFC mesh (see the
manifest `honesty_note`). Regenerate with:

```bash
python3 ../scripts/build_twin.py
```