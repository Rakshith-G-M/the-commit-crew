// Presentation helpers: value formatting, status palettes, and pure mapping
// functions shared across pages. Kept dependency-free for easy unit testing.
import { getSpaceMeta, SPACES_LOOKUP, type SpaceMeta } from "./spacesData";

export { getSpaceMeta, SPACES_LOOKUP, type SpaceMeta };

export function fmtNum(v: number | null | undefined, digits = 1): string {
  if (v === null || v === undefined || Number.isNaN(v)) return "—";
  return new Intl.NumberFormat("en-US", {
    maximumFractionDigits: digits,
    minimumFractionDigits: 0,
  }).format(v);
}

export function fmtArea(m2: number | null | undefined): string {
  if (m2 === null || m2 === undefined || Number.isNaN(m2)) return "—";
  return `${m2.toFixed(1)} m²`;
}

export function fmtVolume(m3: number | null | undefined): string {
  if (m3 === null || m3 === undefined || Number.isNaN(m3)) return "—";
  return `${m3.toFixed(1)} m³`;
}

export function fmtPct(f: number | null | undefined, digits = 0): string {
  if (f === null || f === undefined || Number.isNaN(f)) return "—";
  return `${(f * 100).toFixed(digits)}%`;
}

export function fmtDate(iso: string | null | undefined): string {
  if (!iso) return "—";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toISOString();
}

export function fmtDateTime(iso: string | null | undefined): string {
  if (!iso) return "—";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleString("en-GB", {
    day: "2-digit",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });
}

export type Tone = "ok" | "warn" | "danger" | "dim" | "info";

export const tonePalette: Record<Tone, string> = {
  ok: "bg-emerald-400/10 text-emerald-300 border-emerald-400/30",
  warn: "bg-amber-400/10 text-amber-300 border-amber-400/30",
  danger: "bg-rose-400/10 text-rose-300 border-rose-400/30",
  info: "bg-sky-400/10 text-sky-300 border-sky-400/30",
  dim: "bg-slate-400/10 text-slate-300 border-slate-400/25",
};

export function toneFor(key: string | null | undefined): Tone {
  const k = (key ?? "").toUpperCase();
  if (["CRITICAL", "HIGH", "CRIT", "SEVERE", "FAILED", "POOR"].includes(k))
    return "danger";
  if (["MEDIUM", "MED", "MODERATE", "WARN", "DEGRADED", "PARTIAL"].includes(k))
    return "warn";
  if (["LOW", "OK", "HEALTHY", "GOOD", "RESOLVED", "CONFIRMED"].includes(k))
    return "ok";
  if (["UNKNOWN", "UNKNOWN_LOCATION", "NONE"].includes(k)) return "dim";
  return "info";
}

export function toneForRecommendation(priority: string): Tone {
  return toneFor(priority === "CRITICAL" ? "CRITICAL" : priority);
}

export function label(key: string | null | undefined, fallback = "Unknown"): string {
  return key && key.length ? key : fallback;
}

export function humanize(ident: string | null | undefined): string {
  if (!ident) return "—";
  return ident
    .replace(/^sensor-/i, "")
    .replace(/[_-]+/g, " ")
    .replace(/\b\w/g, (c) => c.toUpperCase());
}

/**
 * Convert IFC storey names to clean human-readable floor labels.
 * e.g., "+Kelder" -> "Basement", "1. korrus" -> "Floor 1", "Katus" -> "Roof"
 */
export function formatStoreyName(storeyName: string | null | undefined): string {
  if (!storeyName) return "Floor —";
  const s = storeyName.trim();
  if (/^\+?kelder/i.test(s)) return "Basement";
  if (/^katus/i.test(s)) return "Roof";
  const korrusMatch = s.match(/^(\d+)\.?\s*korrus/i);
  if (korrusMatch) {
    return `Floor ${korrusMatch[1]}`;
  }
  const floorMatch = s.match(/^(?:floor|level)\s*(\d+)/i);
  if (floorMatch) {
    return `Floor ${floorMatch[1]}`;
  }
  return s;
}

/**
 * Format a human-readable room name from IFC Space Name.
 * e.g. "114" -> "Room 114"
 */
export function formatSpaceRoomName(
  ifcName: string | null | undefined,
  fallbackId?: string | null
): string {
  if (ifcName && ifcName.trim()) {
    const trimmed = ifcName.trim();
    if (/^(room|space|lab|office|hall|corridor|toilet|wc|kitchen|auditorium)\b/i.test(trimmed)) {
      return trimmed;
    }
    if (/^\d+([A-Za-z_-]?\d*)*$/.test(trimmed)) {
      return `Room ${trimmed}`;
    }
    return `Space ${trimmed}`;
  }

  if (fallbackId) {
    const meta = getSpaceMeta(fallbackId);
    if (meta) return meta.roomName;
    const cleaned = fallbackId.replace(/^space_/i, "");
    if (/^\d+$/.test(cleaned)) return `Room ${cleaned}`;
    return `Space ${cleaned.slice(0, 6)}…`;
  }
  return "Space —";
}

/**
 * Full preferred display format: "Room <name> · Floor <storey>"
 * e.g. "Room 114 · Floor 1"
 */
export function formatSpaceDisplayName(opts: {
  ifcName?: string | null;
  storeyName?: string | null;
  spaceId?: string | null;
}): string {
  if (opts.spaceId) {
    const meta = getSpaceMeta(opts.spaceId);
    if (meta) {
      if (opts.storeyName) {
        return `${meta.roomName} · ${formatStoreyName(opts.storeyName)}`;
      }
      return meta.displayName;
    }
  }
  const room = formatSpaceRoomName(opts.ifcName, opts.spaceId);
  if (opts.storeyName) {
    const floor = formatStoreyName(opts.storeyName);
    return `${room} · ${floor}`;
  }
  return room;
}

/**
 * Resolve any space_id (e.g. "space_3U1W8Xs6L9pRXU5Afk5MW1") to its full
 * human-facing label "Room 114 · Floor 3".
 */
export function resolveSpaceDisplayName(spaceId: string | null | undefined): string {
  if (!spaceId) return "—";
  const meta = getSpaceMeta(spaceId);
  if (meta) return meta.displayName;
  return formatSpaceRoomName(null, spaceId);
}

/**
 * Resolve any space_id to just its room label e.g. "Room 114".
 */
export function resolveSpaceRoomName(spaceId: string | null | undefined): string {
  if (!spaceId) return "—";
  const meta = getSpaceMeta(spaceId);
  if (meta) return meta.roomName;
  return formatSpaceRoomName(null, spaceId);
}

// Short suffix of a long IFC-ish/node identifier for compact UI display.
export function shortId(id: string | null | undefined): string {
  if (!id) return "—";
  if (id.startsWith("space_")) {
    const meta = getSpaceMeta(id);
    if (meta) return meta.roomName;
  }
  if (id.length <= 18) return id;
  return `${id.slice(0, 8)}…${id.slice(-6)}`;
}

export interface SeverityMeta {
  key: string;
  count: number;
  tone: Tone;
}

// Sorted-by-severity series from a by_severity map (API gives {"CRITICAL": n,
// "HIGH": n, ...}); unknown keys appended last.
export function severitySeries(map: Record<string, number> | null | undefined): SeverityMeta[] {
  const order = ["CRITICAL", "HIGH", "MEDIUM", "LOW", "INFO", "NONE", "UNKNOWN"];
  const entries = Object.entries(map ?? {});
  const ranked = order
    .map((k, i) => ({ k, i }))
    .filter(({ k }) => entries.some(([ek]) => ek === k));
  const rest = entries.filter(([ek]) => !order.includes(ek)).map(([ek]) => ek);
  return [...ranked.map(({ k }) => k), ...rest]
    .map((k) => ({
      key: k,
      count: (map ?? {})[k] ?? 0,
      tone: toneFor(k),
    }))
    .filter((s) => s.count > 0);
}

// Map an allocation result — server excluded/qualified reasons to a friendly
// phrase. Pure, so it can be unit tested.
export function exclusionPhrase(reason: string): string {
  switch (reason) {
    case "insufficient capacity":
      return "Declared operational capacity below requirement";
    case "unavailable":
      return "Marked unavailable in operational state";
    case "availability not declared":
      return "Availability not declared (treated as unknown)";
    case "equipment mismatch":
      return "Not available for requested equipment";
    case "not occupiable":
      return "Not occupiable per BIM design";
    case "capacity unknown":
      return "Capacity not published in resource state";
    case "other explicit constraint":
      return "Constrained by another explicit rule";
    default:
      return reason;
  }
}

export function qualificationPhrase(reason: string): string {
  switch (reason) {
    case "capacity":
      return "Reported capacity satisfies the requirement";
    case "occupiable":
      return "Space is occupiable per BIM design";
    case "availability":
      return "Availability explicitly declared";
    default:
      return reason;
  }
}

// Evidence chain step → short label for the UI.
export function evidenceStepLabel(step: string): string {
  switch (step) {
    case "anomaly_detected":
      return "Anomaly detected";
    case "sensor_location":
      return "Sensor location";
    case "resource_lookup":
      return "Space lookup";
    case "resource_comparison":
      return "Capacity / occupancy comparison";
    case "forecast_direction":
      return "Forecast direction";
    case "impact_estimation":
      return "Impact estimation";
    case "priority_ranking":
      return "Priority ranking";
    default:
      return step;
  }
}

// Maps an evidence-chain step to its canonical stage in the product narrative.
export const EVIDENCE_FLOW = [
  "PROBLEM",
  "MEASUREMENT",
  "HISTORICAL BASELINE",
  "DEVIATION",
  "PERSISTENCE",
  "DECISION CANDIDATE",
  "RECOMMENDATION",
] as const;

export function evidenceStageOf(step: string): string {
  switch (step) {
    case "anomaly_detected":
      return "PROBLEM";
    case "sensor_location":
      return "MEASUREMENT";
    case "resource_lookup":
      return "HISTORICAL BASELINE";
    case "resource_comparison":
      return "DEVIATION";
    case "forecast_direction":
      return "PERSISTENCE";
    case "impact_estimation":
      return "DECISION CANDIDATE";
    case "priority_ranking":
      return "RECOMMENDATION";
    default:
      return step.toUpperCase();
  }
}

// Which storeys a GLB twin stores (from manifest); used by the twin UI.
export interface TwinStoreyRef {
  storey_id: string;
  node: string;
  name: string | null;
  elevation: number | null;
}

export interface TwinSpaceRef {
  space_id: string;
  node: string;
  storey_id: string | null;
  ifc_name: string;
  ifc_global_id?: string | null;
  area_m2: number | null;
  height_m: number | null;
  volume_m3: number | null;
}

export interface TwinManifest {
  task: string;
  schema_version: string;
  model: string;
  generation: string;
  honesty_note: string;
  storeys: TwinStoreyRef[];
  spaces: TwinSpaceRef[];
}