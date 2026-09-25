import { describe, expect, it } from "vitest";
import {
  anomalyDirection,
  anomalyNarrative,
  measurementTypeSeries,
  measureLabel,
  pickMostSignificant,
  splitSignals,
} from "./anomaly";
import type { AnomalyItem } from "../api/types";

const item = (overrides: Partial<AnomalyItem>): AnomalyItem => ({
  sensor_id: "s1",
  timestamp: "2026-01-10T00:00:00Z",
  measurement_type: "co2",
  unit: "ppm",
  value: 1200,
  expected: 800,
  deviation: 50,
  score: 0.9,
  severity: "HIGH",
  category: "air_quality",
  method: "zscore",
  persistence: 3,
  location_status: "UNKNOWN_LOCATION",
  ...overrides,
});

describe("measureLabel", () => {
  it("renders human labels for the dataset measurement types", () => {
    expect(measureLabel("co2")).toBe("CO₂");
    expect(measureLabel("humidity")).toBe("Humidity");
    expect(measureLabel("temperature")).toBe("Temperature");
    expect(measureLabel("pm2.5")).toBe("Particulate matter (PM2.5)");
    expect(measureLabel("energy")).toBe("Energy");
    expect(measureLabel(null)).toBe("Measurement");
  });
});

describe("anomalyNarrative", () => {
  it("leads human-readable above baseline", () => {
    expect(anomalyNarrative({ measurement_type: "co2", deviation: 50 })).toBe(
      "CO₂ is significantly above this sensor's historical baseline.",
    );
  });
  it("leads human-readable below baseline", () => {
    expect(anomalyNarrative({ measurement_type: "temperature", deviation: -0.6 })).toBe(
      "Temperature is significantly below this sensor's historical baseline.",
    );
  });
  it("falls back when no deviation", () => {
    expect(anomalyNarrative({ measurement_type: "humidity", deviation: null })).toBe(
      "Humidity deviates from this sensor's historical baseline.",
    );
  });
});

describe("anomalyDirection", () => {
  it("returns above/below/null", () => {
    expect(anomalyDirection({ deviation: 2 })).toBe("above");
    expect(anomalyDirection({ deviation: -2 })).toBe("below");
    expect(anomalyDirection({ deviation: null })).toBe(null);
  });
});

describe("splitSignals", () => {
  it("separates environmental from resource counts", () => {
    const out = splitSignals({
      co2: 3174,
      energy: 28,
      humidity: 3254,
      "pm2.5": 1500,
      temperature: 7981,
    });
    expect(out.environmental).toBe(3174 + 3254 + 1500 + 7981);
    expect(out.resource).toBe(28);
  });
});

describe("pickMostSignificant", () => {
  it("returns highest-score representative per measurement type", () => {
    const items = [
      item({ sensor_id: "a", measurement_type: "co2", score: 0.8 }),
      item({ sensor_id: "b", measurement_type: "co2", score: 0.95 }),
      item({ sensor_id: "c", measurement_type: "temperature", score: 0.9 }),
      item({ sensor_id: "d", measurement_type: "temperature", score: 0.1 }),
      item({ sensor_id: "e", measurement_type: "energy", score: 0.7 }),
      item({ sensor_id: "f", measurement_type: "humidity", score: 0.5 }),
      item({ sensor_id: "g", measurement_type: "pm2.5", score: 0.6 }),
    ];
    const picked = pickMostSignificant(items, 5);
    const ids = picked.map((p) => p.sensor_id);
    expect(ids).toContain("b");
    expect(ids).toContain("c");
    expect(picked.length).toBeLessThanOrEqual(5);
    expect(new Set(ids).size).toBe(ids.length);
  });
});

describe("measurementTypeSeries", () => {
  it("ranks known types and labels them", () => {
    const s = measurementTypeSeries({ co2: 3174, energy: 28, "pm2.5": 1500 });
    const keys = s.map((x) => x.key);
    expect(keys[0]).toBe("temperature");
    expect(keys[2]).toBe("co2");
    expect(s.find((x) => x.key === "co2")?.label).toBe("CO₂");
  });
});