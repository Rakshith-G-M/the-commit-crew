// Pure presentation helpers for anomaly/signal language.
// No decision logic here — the backend already decided what is an anomaly; we
// only render it understandably.

import type { AnomalyItem } from "../api/types";

const LABELS: Record<string, string> = {
  co2: "CO₂",
  carbon_dioxide: "CO₂",
  humidity: "Humidity",
  relative_humidity: "Relative humidity",
  temperature: "Temperature",
  "pm2.5": "Particulate matter (PM2.5)",
  pm25: "Particulate matter (PM2.5)",
  energy: "Energy",
};

export function measureLabel(mt: string | null | undefined): string {
  if (!mt) return "Measurement";
  const k = mt.toLowerCase().replace(/[^a-z0-9.]/g, "").replace(/\./g, "");
  return LABELS[mt.toLowerCase()] ?? LABELS[k] ?? mt;
}

export const ENVIRONMENTAL_TYPES = new Set([
  "co2",
  "carbon_dioxide",
  "humidity",
  "relative_humidity",
  "temperature",
  "pm2.5",
  "pm25",
]);

export const RESOURCE_TYPES = new Set(["energy"]);

export function isEnvironmental(mt: string | null | undefined): boolean {
  return ENVIRONMENTAL_TYPES.has((mt ?? "").toLowerCase());
}

export function isResource(mt: string | null | undefined): boolean {
  return RESOURCE_TYPES.has((mt ?? "").toLowerCase());
}

export function splitSignals(
  counts: Record<string, number> | null | undefined,
): { environmental: number; resource: number } {
  const entries = Object.entries(counts ?? {});
  let environmental = 0;
  let resource = 0;
  for (const [k, v] of entries) {
    const kk = k.toLowerCase();
    if (isEnvironmental(kk)) environmental += v;
    else if (isResource(kk)) resource += v;
  }
  return { environmental, resource };
}

/**
 * Human-first anomaly statement.
 * Example: "CO₂ is significantly above this sensor's historical baseline."
 */
export function anomalyNarrative(a: {
  measurement_type?: string | null;
  value?: number | null;
  expected?: number | null;
  deviation?: number | null;
}): string {
  const label = measureLabel(a.measurement_type);
  const dev = a.deviation;
  if (dev === null || dev === undefined || Number.isNaN(dev)) {
    return `${label} deviates from this sensor's historical baseline.`;
  }
  const dir = dev >= 0 ? "above" : "below";
  return `${label} is significantly ${dir} this sensor's historical baseline.`;
}

// Canonical direction word (for badges).
export function anomalyDirection(a: {
  deviation?: number | null;
}): "above" | "below" | null {
  const dev = a.deviation;
  if (dev === null || dev === undefined || Number.isNaN(dev)) return null;
  return dev >= 0 ? "above" : "below";
}

// Pick a small, representative set of the most significant signals: highest
// score per measurement type, restricted to the severities provided.
export function pickMostSignificant(
  items: AnomalyItem[],
  max = 5,
): AnomalyItem[] {
  const byType = new Map<string, AnomalyItem>();
  const score = (a: AnomalyItem) => a.score ?? -Infinity;
  for (const a of items) {
    const t = (a.measurement_type ?? "other").toLowerCase();
    const cur = byType.get(t);
    if (!cur || score(a) > score(cur)) byType.set(t, a);
  }
  return [...byType.values()]
    .sort((a, b) => score(b) - score(a))
    .slice(0, max);
}

export const measurementTypeSeries = (
  counts: Record<string, number> | null | undefined,
): Array<{ key: string; label: string; count: number }> => {
  const order = ["temperature", "humidity", "co2", "pm2.5", "energy"];
  const map: Record<string, number> = {};
  if (counts) {
    for (const [k, v] of Object.entries(counts)) {
      map[k.toLowerCase()] = v;
    }
  }
  const result: Array<{ key: string; label: string; count: number }> = [];
  for (const k of order) {
    result.push({
      key: k,
      label: measureLabel(k),
      count: map[k] ?? 0,
    });
  }
  if (counts) {
    for (const [k, v] of Object.entries(counts)) {
      if (!order.includes(k.toLowerCase())) {
        result.push({
          key: k,
          label: measureLabel(k),
          count: v ?? 0,
        });
      }
    }
  }
  return result;
};