# CampusIQ — Pitch Presentation Deck

**10 slides · ~5 minutes · The Commit Crew**

Goal of the deck: tell one honest story — **"CampusIQ turns campus data into
decisions."** Every number below was taken directly from the produced
artifacts in this repository (`output/*.json`) and the running product.

> Pacing rule for the presenter: **never push past what the product actually
> shows.** When in doubt, the demo screen is the source of truth.

---

## Slide 1 — Title

**Title:** **CAMPUSIQ — From Campus Data to Better Decisions**

**Visual:** Live Overview page (hero twin render) or a full-bleed shot of the
3D building with the logo overlaid.

**Content (on-slide):**
- CampusIQ · Smart Campus Operations
- TalTech DS3 – Ehituse Mäemaja
- 115 spaces · 5 storeys · 1.39M telemetry readings
- The Commit Crew

**Speaker notes (≈40s):**
> "CampusIQ is a smart-campus operations platform. We connect two datasets
> that are almost never used together: over a million real sensor readings
> from a university building, and the building's official IFC BIM model. The
> result is a single spatial view that tells a facilities manager what the
> building is doing, what deserves attention, and what to do next — with the
> reasoning shown, not hidden."

**Demo action:** none (or hero live).

---

## Slide 2 — The Problem

**Title:** **Facility teams operate in the dark**

**Visual:** 3-across "gap" cards (stylized).

**Content:**
1. **Telemetry is orphaned** — sensor streams exist as files; nobody turns
   them into decisions.
2. **BIM is a static drawing** — design capacity and loads never meet live
   conditions.
3. **Alerts don't explain** — "something's wrong" without the evidence chain
   behind it.
4. **Planning is tribal knowledge** — "can 40 people fit?" is guessed, not
   answered from the model.

**Speaker notes (≈35s):**
> "Every campus has data and a BIM model. But the sensor logs never feed the
> model, and the model never feeds the operations dashboard. Alerts fire
> without context, and space-planning questions get answered from memory. The
> result: reactive maintenance, wasted energy, and decisions made without
> evidence."

**Demo action:** none.

---

## Slide 3 — Our Solution

**Title:** **One pipeline: Observe → Detect → Understand → Recommend**

**Visual:** Mermaid pipeline diagram (OBSERVE → DETECT → UNDERSTAND →
RECOMMEND) with the four product views underneath.

**Content:**
- **OBSERVE** — 69 channels validated and journeyed through the pipeline
- **DETECT** — anomaly & deviation scoring per channel
- **UNDERSTAND** — time-aware historical baselines
- **RECOMMEND** — prioritized, explainable operational actions
- Plus **What-If space planning** on verified BIM capacity.

**Speaker notes (≈35s):**
> "CampusIQ is one pipeline, not five tools. Every reading is validated,
> compared against a time-aware baseline, scored for anomalies, and — when the
> evidence is strong enough — turned into a prioritized recommendation that
> explains itself. On the right, you see the four product surfaces: the
> operational overview, the digital twin, the intelligence workspace, and the
> space planner."

**Demo action:** none.

---

## Slide 4 — Data & Scale

**Title:** **We built it on real data**

**Visual:** Big-number stat cards.

**Content (all verified from artifacts):**
- **1,390,297** validated telemetry readings
- **36** sensor devices · **69** channels
- **temperature 29 · humidity 26 · CO₂ 7 · energy 4 · PM2.5 3**
- Span **2024-03-18 → 2025-06-30**
- **115 spaces · 5 storeys · 1 building** from `DS3_TalTech_V4.ifc`
- Quality: **0 missing, 0 duplicates, 0 out-of-range** in the validated set

**Speaker notes (≈30s):**
> "We didn't invent a demo dataset. This is a year and a quarter of real
> campus telemetry — 1.39 million readings from 36 devices across 69 channels:
> temperature, humidity, CO₂, energy, and PM2.5 — joined to the official IFC
> model of the building. We validated every reading before the pipeline would
> touch it."

**Demo action:** none.

---

## Slide 5 — The Digital Twin

**Title:** **The campus, in 3D**

**Visual:** Live `/twin` render (rotate/floors on click).

**Content:**
- True IFC4 geometry extracted from `DS3_TalTech_V4.ifc`
- **ALL FLOORS** navigation across 5 storeys
- Search + Space Inspector: area, volume, height, **design capacity**, and IFC
  design loads (lighting, power, HVAC)
- Every panel says explicitly: **BIM design data — not measured operational
  data**

**Speaker notes (≈30s):**
> "Because the model comes from real IFC4 geometry, the twin is a true
> spatial index, not a cartoon. Click any room and the inspector shows its BIM
> facts — area, volume, height, design capacity, even design loads for
> lighting and HVAC. And we're honest about provenance: every value is labeled
> as BIM *design* data, not a live measurement."

**Demo action:** floor switch + select a room → show inspector.

---

## Slide 6 — The Intelligence Pipeline

**Title:** **From readings to signals**

**Visual:** Anomalies + Forecasts screens; z-score pipeline diagram.

**Content:**
- Time-aware baselines define *normal* for each channel and hour
- Anomaly scoring uses a transparent z-score family (time-aware, rolling,
  global, MAD)
- **37,359** anomaly candidates → **15,937** recorded with full detail
- Severity mix: **3,168 Critical · 1,493 High · 3,486 Medium · 7,790 Low**
- Forecasts at **1h / 6h / 24h** — labeled as predictions, with coverage
  metadata instead of fabricated confidence

**Speaker notes (≈40s):**
> "Our detection isn't a black box. For every channel we learn a time-aware
> baseline — what value is normal at this hour — then score each reading
> against it. The engine surfaced 37 thousand anomaly candidates and kept
> detail on almost 16 thousand of the strongest. Every row shows observed,
> baseline, deviation, and severity. And our forecasts are explicitly marked
> as model predictions, because we refuse to fake confidence intervals that we
> didn't compute."

**Demo action:** Intelligence → Anomalies tab; filter High/Critical.

---

## Slide 7 — Explainable Recommendations

**Title:** **Recommendations with the receipts**

**Visual:** A Recommendation detail card (from `/intelligence?rec=…`).

**Content:**
- **98 recommendations** — ENVIRONMENTAL · SENSOR_HEALTH · ENERGY
- Priority split: **55 High · 36 Medium · 7 Low**
- Ranking is a **transparent weighted heuristic** over severity, persistence,
  deviation, forecast relevance, actionability, confidence, and data quality —
  not a hidden ML model
- Each card ships an **Evidence Traceability Chain** and engine metadata
- Quote from the data:
  > "No measured savings, timetables, or sensor locations are fabricated."

**Speaker notes (≈40s):**
> "Every recommendation is an auditable claim about the data. Its priority is
> a transparent weighted score — you can see every factor and every step of the
> evidence chain from measurement to recommendation. We say explicitly that
> impact and savings are *classified as unknown* until an intervention is
> measured, and we never attach a sensor to a room we can't prove it's in."

**Demo action:** open a High recommendation → expand Evidence Chain.

---

## Slide 8 — What-If Space Planning

**Title:** **Questions answered from the model**

**Visual:** Space Planning screen after evaluating a scenario.

**Content:**
- Set a required capacity + equipment
- Engine evaluates **all 115 rooms** against verified BIM capacity
- Results: **capacity matches / equipment verified / excluded / total
  evaluated**
- Anything unverifiable (e.g. equipment inventory, availability) is flagged
  **unverified**, never assumed
- Click-through: every match deep-links to its room in the Digital Twin

**Speaker notes (≈35s):**
> "Space planning becomes a computation over the model, not a guess. Tell the
> engine what you need — say 22 workstations and AV — and it evaluates every
> room against verified capacity, marks what it can't verify, and ranks the
> matches. Click any result and you jump straight to that room in the 3D
> twin."

**Demo action:** What-If → set capacity → EVALUATE SCENARIO → open a match.

---

## Slide 9 — Architecture & Tech

**Title:** **Clean, inspectable, and honest by design**

**Visual:** Mermaid architecture diagram (Data → Engine → API → UI).

**Content:**
- **Backend:** Python FastAPI + pipeline modules (baseline, anomaly, health,
  forecast, decision, recommendation); no database — versioned JSON artifacts,
  every stage inspectable
- **Frontend:** React 19 · TypeScript · Vite · Tailwind v4; Three.js / R3F for
  the 3D twin
- **Integrity:** sensor↔room mapping is **UNRESOLVED** in this release and we
  say so in the UI
- **Tests:** 124 backend · 33 frontend — all passing

**Speaker notes (≈30s):**
> "Two clean layers: a Python data pipeline that writes versioned JSON
> artifacts — so any step can be audited — and a FastAPI server that serves
> them, with a React frontend on top, plus a Three.js twin. 157 tests pass.
> Architecturally, the honest choice was just as deliberate as the good ones:
> where mapping or measurement is not available, the product reports it rather
> than papering over it."

**Demo action:** none.

---

## Slide 10 — Closing

**Title:** **CampusIQ turns campus data into decisions.**

**Visual:** Twin render with tagline; final stat strip.

**Content:**
- Real data, real BIM, one spatial view
- Explainable, auditable recommendations
- Verification-first honesty in every screen

**Takeaways:**
- **1.39M** readings processed → **15.9k** evidence-backed signals →
  **98** prioritized actions → **0** invented facts

**Speaker notes (≈30s):**
> "CampusIQ shows what's possible when telemetry and BIM finally talk to each
> other: a million and a half readings become 15 thousand evidence-backed
> signals, which become 98 prioritized actions a facilities team can actually
> act on — and not one number in that chain was invented. Next steps are clear:
> resolve room-level sensor mapping, close the loop with measured outcomes,
> and go live. Thank you."

**Demo action:** none (or final full-screen twin).

---

## Presenter Quick Reference

| # | Slide | Honesty guardrail |
| --- | --- | --- |
| 3 | Pipeline | "OBSERVE→DETECT→UNDERSTAND→RECOMMEND" is the product's own framing — reuse it verbatim. |
| 5 | Digital Twin | Always say values are **BIM design**, never "measured". |
| 7 | Recommendations | Emphasize: transparent heuristic, **not** ML; savings **UNKNOWN**. |
| 8 | Space Planning | It evaluates **allocation feasibility**, not HVAC/energy outcome. |
| 9 | Architecture | Sensor→room mapping is **UNRESOLVED** — state it proudly. |

---

*Prepared from the running product and `output/*.json` artifacts. See also
`CAMPUSIQ_DEMO_SCRIPT.md` for the 3–5 minute live walkthrough.*