/**
 * CampusIQ — Recommendation Presentation Layer
 *
 * Translates raw backend recommendation objects into clean,
 * non-technical operational language for campus administrators.
 *
 * NEVER display UUIDs, enum codes, scoring formulas, or internal pipeline
 * names to the user. This module is the single source of truth for all
 * user-facing recommendation text.
 */

import { getSensorDisplayName } from "./sensorsData";
import { resolveSpaceDisplayName } from "./format";

// ── Issue code → human sentence ──────────────────────────────────
const ISSUE_LABELS: Record<string, string> = {
  CONSTANT_VALUE:     "Repeated constant readings",
  IRREGULAR_SAMPLING: "Irregular measurement intervals",
  LONG_GAP:           "Extended period without readings",
  LONG_DATA_GAP:      "Extended period without readings",
  EXCESSIVE_MISSING:  "High rate of missing readings",
  OUT_OF_BOUNDS:      "Out-of-range readings detected",
  NOISE:              "Noisy or unstable readings",
  SPIKE:              "Sudden measurement spikes",
  DRIFT:              "Gradual sensor drift detected",
};

export function translateIssueCode(code: string): string {
  const u = code.toUpperCase().trim();
  return ISSUE_LABELS[u] ?? u.replace(/[_-]+/g, " ").replace(/\b\w/g, c => c.toUpperCase());
}

// ── Category code → human label ─────────────────────────────────
const CATEGORY_LABELS: Record<string, string> = {
  SENSOR_HEALTH:   "Sensor reliability",
  ENERGY_ANOMALY:  "Energy anomaly",
  AIR_QUALITY:     "Air quality issue",
  OCCUPANCY:       "Occupancy planning",
  MAINTENANCE:     "Maintenance required",
  CAPACITY:        "Capacity planning",
  FORECAST:        "Forecast alert",
};

export function translateCategory(cat: string): string {
  const u = (cat ?? "").toUpperCase().trim();
  return CATEGORY_LABELS[u] ?? cat.replace(/_/g, " ").replace(/\b\w/g, c => c.toUpperCase());
}

// ── Problem type → human label ───────────────────────────────────
const PROBLEM_LABELS: Record<string, string> = {
  MAINTENANCE:   "Maintenance required",
  ANOMALY:       "Anomaly detected",
  CAPACITY:      "Capacity issue",
  FORECAST:      "Forecast warning",
  ENERGY:        "Energy issue",
  AIR_QUALITY:   "Air quality concern",
};

export function translateProblemType(t: string): string {
  const u = (t ?? "").toUpperCase().trim();
  return PROBLEM_LABELS[u] ?? t.replace(/_/g, " ").replace(/\b\w/g, c => c.toUpperCase());
}

// ── Extract issue list from raw recommendation data ──────────────
export function extractIssues(r: any): string[] {
  const raw: string[] = [];

  // evidence.issue_types
  for (const i of r.evidence?.issue_types ?? []) raw.push(i);

  // evidence_chain HEALTH_ISSUE step value array
  for (const step of r.evidence_chain ?? []) {
    if (step.step === "HEALTH_ISSUE" && Array.isArray(step.value)) {
      for (const i of step.value) raw.push(i);
    }
  }

  // data_quality.issues / issue_types
  for (const i of r.data_quality?.issues ?? []) {
    raw.push(typeof i === "string" ? i : i.type ?? "");
  }
  for (const i of r.data_quality?.issue_types ?? []) raw.push(i);

  // Deduplicate, translate
  const seen = new Set<string>();
  const out: string[] = [];
  for (const code of raw) {
    if (!code) continue;
    const label = translateIssueCode(code);
    if (!seen.has(label)) { seen.add(label); out.push(label); }
  }
  return out;
}

// ── Build a clean sensor display name from the recommendation ────
export function recSensorName(r: any): string {
  // Try: affected_entity.sensor_id lookup
  const sensorId = r.affected_entity?.sensor_id;
  const category = r.recommendation_category ?? "";

  // Derive measurement type from category or evidence
  const measureType = category === "SENSOR_HEALTH"
    ? deriveMeasurementType(r)
    : category;

  return getSensorDisplayName(sensorId, measureType || undefined);
}

// Try to derive measurement type from evidence / category
function deriveMeasurementType(r: any): string {
  const cat = (r.recommendation_category ?? "").toLowerCase();
  if (cat.includes("air") || cat.includes("co2") || cat.includes("iaq")) return "co2";
  if (cat.includes("energy") || cat.includes("power")) return "energy";
  if (cat.includes("pm") || cat.includes("particle")) return "pm2.5";
  if (cat.includes("temp")) return "temperature";
  // Fall back to sensor UUID lookup (getSensorDisplayName handles this)
  return "";
}

// ── Generate clean recommendation title ─────────────────────────
export function recTitle(r: any): string {
  const cat = (r.recommendation_category ?? "").toUpperCase();
  const prob = (r.problem_type ?? "").toUpperCase();

  if (cat === "SENSOR_HEALTH" || prob === "MAINTENANCE") {
    return "Sensor maintenance required";
  }
  if (cat === "ENERGY_ANOMALY") return "Unusual energy consumption detected";
  if (cat === "AIR_QUALITY") return "Air quality issue detected";
  if (cat === "OCCUPANCY") return "Occupancy planning recommendation";
  if (cat === "FORECAST") return "Forecast alert";
  if (cat === "CAPACITY") return "Capacity planning recommendation";

  // Fallback: clean up the raw action but strip UUIDs and enums
  return cleanActionText(r.recommended_action ?? "Recommendation");
}

// ── Generate clean action sentence ───────────────────────────────
export function recAction(r: any, sensorName: string): string {
  const cat = (r.recommendation_category ?? "").toUpperCase();
  const issues = extractIssues(r);

  if (cat === "SENSOR_HEALTH") {
    const baseType = sensorName.split("·")[0].trim();
    if (issues.length > 0) {
      return `Inspect and service the ${baseType.toLowerCase()} to restore a consistent measurement stream.`;
    }
    return `Inspect the ${baseType.toLowerCase()} and verify that it is transmitting valid readings.`;
  }

  if (cat === "ENERGY_ANOMALY") {
    return "Investigate the energy meter readings and check for unusual consumption patterns.";
  }

  // Strip UUIDs and enum codes from the raw action
  return cleanActionText(r.recommended_action ?? "Follow up with the facilities team.");
}

// ── Generate clean "what happened" description ───────────────────
export function recReason(r: any): string {
  const cat = (r.recommendation_category ?? "").toUpperCase();
  const healthStatus = r.evidence?.health_status ?? r.data_quality?.health_status ?? "";

  if (cat === "SENSOR_HEALTH") {
    if (healthStatus === "DEGRADED") {
      return "The sensor's data stream is degraded. The system has detected problems with the quality or continuity of its measurements.";
    }
    return "This sensor is showing signs of reduced data quality that may affect environmental monitoring.";
  }

  // Generic: clean raw reason string
  return cleanReasonText(r.reason ?? "An issue has been detected that requires attention.");
}

// ── Generate clean "why does it matter" ─────────────────────────
export function recImportance(r: any): string {
  const cat = (r.recommendation_category ?? "").toUpperCase();

  if (cat === "SENSOR_HEALTH") {
    return "Unreliable sensor data reduces the accuracy and continuity of campus environmental monitoring. Without a healthy data stream, the system cannot reliably detect anomalies, forecast conditions, or support space management decisions.";
  }
  if (cat === "ENERGY_ANOMALY") {
    return "Unexplained energy consumption can indicate equipment faults or inefficiencies. Early investigation helps prevent cost overruns and equipment damage.";
  }
  if (cat === "AIR_QUALITY") {
    return "Poor indoor air quality affects occupant health and comfort. Persistent issues should be investigated to ensure a safe working environment.";
  }

  return "Addressing this issue promptly will help maintain the reliability of campus operations and monitoring.";
}

// ── Generate clean impact description ────────────────────────────
export function recImpactItems(r: any): Array<{ label: string; detail: string }> {
  const cat = (r.recommendation_category ?? "").toUpperCase();
  const items: Array<{ label: string; detail: string }> = [];

  for (const imp of r.expected_impact ?? []) {
    const type = (imp.type ?? "").toLowerCase();
    if (type.includes("data_quality") || type.includes("observability")) {
      items.push({
        label: "Improved sensor reliability",
        detail: "Restoring the measurement stream should improve the quality and continuity of environmental monitoring.",
      });
    } else if (type.includes("energy")) {
      items.push({
        label: "Reduced energy waste",
        detail: imp.reason ?? "Addressing this issue may reduce unnecessary energy consumption.",
      });
    } else if (type.includes("air") || type.includes("iaq") || type.includes("co2")) {
      items.push({
        label: "Better air quality monitoring",
        detail: imp.reason ?? "Improved sensor health will support more accurate air quality assessments.",
      });
    } else {
      items.push({
        label: translateCategory(imp.type ?? "Operational improvement"),
        detail: imp.reason ?? "Operational performance will improve after addressing this issue.",
      });
    }
  }

  if (items.length === 0) {
    if (cat === "SENSOR_HEALTH") {
      items.push({
        label: "Improved sensor reliability",
        detail: "Restoring the measurement stream should improve the quality and continuity of environmental monitoring.",
      });
    } else {
      items.push({
        label: "Operational improvement",
        detail: "Addressing this recommendation will improve campus operational reliability.",
      });
    }
  }

  return items;
}

// ── Location description ─────────────────────────────────────────
export function recLocationText(r: any): { primary: string; note: string; verified: boolean } {
  const status = (r.location_status ?? r.location?.status ?? "").toUpperCase();
  const spaceId = r.location?.space_id ?? r.affected_entity?.space_id;

  if (status === "VERIFIED_BIM" && spaceId) {
    return {
      primary: resolveSpaceDisplayName(spaceId),
      note: "Location verified to building space via BIM model.",
      verified: true,
    };
  }

  return {
    primary: "Location unavailable",
    note: "This dataset does not contain a verified sensor-to-room mapping for this device.",
    verified: false,
  };
}

// ── Build clean evidence steps ────────────────────────────────────
export interface EvidenceStep {
  label: string;
  detail: string;
}

const STEP_LABELS: Record<string, string> = {
  SENSOR_HEALTH: "Sensor health check",
  HEALTH_ISSUE:  "Data-quality analysis",
  OBSERVED:      "Historical behavior comparison",
  CANDIDATE:     "Maintenance candidate identified",
  RECOMMENDATION:"Recommendation generated",
  anomaly_detected: "Anomaly detected",
  sensor_location:  "Sensor location lookup",
  resource_lookup:  "Space lookup",
  resource_comparison: "Capacity comparison",
  forecast_direction: "Forecast direction",
  impact_estimation:  "Impact estimation",
  priority_ranking:   "Priority ranking",
};

export function buildEvidenceSteps(r: any): EvidenceStep[] {
  const chain: any[] = r.evidence_chain ?? [];
  return chain.map((step) => {
    const rawStep = step.step ?? "";
    const label = STEP_LABELS[rawStep] ?? rawStep.replace(/[_-]+/g, " ").replace(/\b\w/g, (c: string) => c.toUpperCase());

    // Translate the note
    let detail = translateNote(step.note ?? "", step.value);
    return { label, detail };
  });
}

function translateNote(note: string, value: any): string {
  if (/device health status/i.test(note)) {
    const v = typeof value === "string" ? value : "";
    if (v === "DEGRADED") return "The sensor's overall health status is degraded.";
    if (v === "HEALTHY") return "The sensor is operating normally.";
    return "Health status recorded.";
  }
  if (/issue types detected/i.test(note)) {
    if (Array.isArray(value) && value.length > 0) {
      const labels = value.map(translateIssueCode).join(", ");
      return `Detected: ${labels}.`;
    }
    return "Issue types recorded.";
  }
  if (/context from sensors with anomalies/i.test(note)) {
    const count = value?.anomaly_candidates;
    if (count !== undefined) return `${count} data-quality events observed in the historical record.`;
    return "Anomaly context recorded.";
  }
  if (/decision candidate/i.test(note)) {
    return "A maintenance candidate was created based on the detected issues.";
  }
  if (/ranked.*explainable recommendation/i.test(note)) {
    return "A ranked, explainable recommendation was generated for this sensor.";
  }
  // Return cleaned note (strip UUIDs and enum codes)
  return cleanNote(note);
}

// ── Text sanitizers ──────────────────────────────────────────────

// UUID pattern
const UUID_RE = /[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}/gi;

// Enum list pattern: "(issues: X, Y, Z)"
const ISSUE_LIST_RE = /\(issues?:[^)]*\)/gi;

// Internal enum names in parens, e.g. "(MAINTENANCE)"
const INTERNAL_PAREN_RE = /\([A-Z_]{4,}\)/g;

function cleanActionText(text: string): string {
  return text
    .replace(UUID_RE, "the sensor")
    .replace(ISSUE_LIST_RE, "")
    .replace(INTERNAL_PAREN_RE, "")
    .replace(/\s{2,}/g, " ")
    .replace(/\s+\./g, ".")
    .trim();
}

function cleanReasonText(text: string): string {
  return text
    .replace(/Health status DEGRADED with \d+ issue type\(s\)\./i,
      "The sensor's data stream is degraded — multiple data-quality issues have been detected.")
    .replace(/DEGRADED/g, "degraded")
    .replace(/HEALTHY/g, "healthy")
    .replace(UUID_RE, "this sensor")
    .replace(ISSUE_LIST_RE, "")
    .replace(INTERNAL_PAREN_RE, "")
    .replace(/\s{2,}/g, " ")
    .trim();
}

function cleanNote(note: string): string {
  return note
    .replace(UUID_RE, "this sensor")
    .replace(/\b(CONSTANT_VALUE|IRREGULAR_SAMPLING|LONG_GAP|SENSOR_HEALTH|HEALTH_ISSUE|MAINTENANCE|UNKNOWN_LOCATION)\b/g,
      (m) => translateIssueCode(m))
    .replace(INTERNAL_PAREN_RE, "")
    .replace(/\s{2,}/g, " ")
    .trim();
}
