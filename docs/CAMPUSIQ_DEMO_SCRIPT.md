# CampusIQ — Live Demo Script (3–5 minutes)

**Presenter:** The Commit Crew
**Runtime target:** 3:30–4:30 (hard stop by 5:00)

This script is built **exclusively from elements that actually exist in the
product UI** (routes, panels, labels, tabs, buttons) and the verified data in
`output/*.json`. If a screen does not match, the product state is what it is —
do not improvise extra features.

---

## Before you start (checklist — 60s of silence, not part of the clock)

- [ ] Backend running: `cd scripts && uvicorn api_app:app --port 8000`
- [ ] Frontend running: `cd frontend && npm run dev` → http://localhost:5173
- [ ] Sidebar footer reads **SYSTEM OPERATIONAL** (green dot), header shows
      **1.39M Telemetry Readings**
- [ ] Default route `/` (Overview) is loaded

---

## Act 1 — Overview (≈45s)

> "This is CampusIQ — a smart-campus operations platform for the TalTech DS3
> building. Behind me are the raw ingredients: **1.39 million validated
> readings** from 36 sensors across 69 channels, and the building's official
> IFC model — 115 spaces across 5 storeys. CampusIQ's job is to turn that data
> into decisions."

Walk the strip (mouse over the numbered cards):

> "Here's the state of the building at a glance — **spaces, storeys, sensors,
> channels, readings, and 98 actions** the system wants us to look at."

> "And here's what needs attention: **the critical-signal count, the severity
> breakdown, and the featured recommendation** — the system's highest-priority
> action, with its reasoning shown right on the page."

> "Finally, note the pipeline every reading flows through:
> **Observe → Detect → Understand → Recommend**."

`[Click]` **EXPLORE DIGITAL TWIN** → `/twin`

---

## Act 2 — Digital Twin (≈60s)

> "This is the building in 3D — the geometry comes from the real IFC4 model,
> so it's a genuine spatial index of the building, not a mockup."

`[Click]` a floor e.g. **Floor 3** in the top-center toolbar, then **ALL FLOORS**
to restore.

> "I can navigate floor by floor with the toolbar, search any room, and select
> it — either here in the directory or directly in the model."

`[Click]` **Search room…**, type part of a room name, then click the result.

> "Selecting a room opens the **Space Inspector** — area, volume, height,
> design capacity. And this is where we're deliberate about honesty: these are
> **BIM design values from the IFC model — not measured operational data**.
> You'll also see that sensor-to-room mapping is marked **UNRESOLVED** in the
> current data release. We'd rather label the uncertainty than paper over it."

`[Click]` **Inspector ▲/▼** once for effect; then navigate to Intelligence via
sidebar.

> "Now let's look at what the data is actually saying."

---

## Act 3 — Intelligence: Anomalies (≈60s)

`[Click]` **Intelligence** in the sidebar → `/intelligence` (lands on the
Anomalies tab).

> "The intelligence workspace opens on **anomalies**. The header strip gives
> the operational pulse: critical signals, high priority, environmental,
> resource & power, and degraded sensors."

`[Click]` **High** (or **Critical**) filter chip; then clear back to **All**.

> "Every row is a flagged reading with its full evidence: **sensor, what was
> observed, the time-aware baseline expectation, the deviation, and the
> severity**. The engine detected **37 thousand** anomaly candidates and
> retained detailed records for the strongest. What you see on screen are
> those records — observed versus baseline, no black box."

---

## Act 4 — Intelligence: the Recommendation & Evidence Chain (≈60s)

`[Click]` **Recommendations** tab.

> "Anomalies that meet the bar become **98 prioritized recommendations** —
> split across environmental conditions, sensor health, and energy. Priorities
> are set by a **transparent weighted score** over severity, persistence,
> deviation, forecast relevance, and actionability — every factor you can see."

`[Click]` one **High priority** recommendation card → opens the detail page.

> "This is where CampusIQ earns trust. The brief answers the questions a
> facilities manager actually asks."

> "- **What happened?** — the detected condition and its issues.
> - **What should I do?** — the proposed action.
> - **Why does it matter?** — the impact framing.
> - **Location & expected impact** — with impact claims **classified**, not
>   fabricated."

`[Click]` expand **Evidence Traceability Chain**:

> "And beneath it, the full evidence chain — measurement, baseline, deviation,
> anomaly, candidate, recommendation — so this recommendation can be audited
> back to the original reading."

`[Click]` expand **Technical Diagnostic Details** (show the engine metadata
briefly).

> "The data itself carries this rule, and I'll read it because it's our design
> philosophy: *'No measured savings, timetables, or sensor locations are
> fabricated.'*"

`[Click]` **← Back to Recommendations**, then open **Space Planning** in the
sidebar.

---

## Act 5 — What-If Space Planning (≈60s)

`[Click]` **Space Planning** → `/what-if`

> "Finally, the planning question every campus team asks: *can we fit this much
> where?* Here I'll ask the engine directly."

`[Click]` set **REQUIRED CAPACITY** to a value, e.g. **22**, keep
**Office Workstations** selected, leave availability unchecked:

> "Notice it also flags the limits of the dataset: equipment inventory isn't in
> the bundle, so compatibility is reported as **unverified**, and scheduling
> availability isn't provided either."

`[Click]` **EVALUATE SCENARIO**.

> "The engine evaluates **all 115 rooms** against verified BIM capacity and
> returns the capacity matches, equipment status, and excluded rooms — ranked
> by verified constraints only."

`[Click]` **View in Digital Twin →** on the top result → `/twin?space=…`

> "And every match deep-links straight back into the 3D twin — from a planning
> question to the actual room in one click."

---

## Act 6 — Return & Closing (≈30s)

`[Click]` **Overview** in the sidebar.

> "So the loop closes back where we started: real telemetry, a real BIM model,
> one spatial view. **1.39 million readings → 15.9 thousand evidence-backed
> signals → 98 prioritized, auditable actions — and zero invented facts.**"

> "Next steps: resolve room-level sensor mapping, measure the outcomes of
> recommended interventions, and take the pipeline live. **CampusIQ turns
> campus data into decisions.** Thank you."

---

## Backup beats (if something breaks)

- **Twin doesn't load:** fall back immediately to Intelligence — the story
  survives without 3D.
- **A tab shows "Empty":** say naturally "the dataset keeps this channel
  sparse — the honest empty state is part of the design," then switch tabs.
- **No time / network stalls:** skip Act 4's technical-details expand and the
  What-If re-link; keep the recommendation evidence chain — it is the
  strongest beat.

## Do NOT say or show

- ❌ Sensor "Room X" attribution — mapping is **UNRESOLVED** (the UI shows it).
- ❌ Energy savings figures — classified **UNKNOWN** until an intervention is
  verified.
- ❌ "ML model / accuracy %" — ranking is a transparent heuristic.
- ❌ The replay bar / replay endpoints — they exist in the backend as a
  scripting tool, **not** in any page.
- ❌ Live hardware — this demo replays curated data through the same pipeline.