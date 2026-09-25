import { describe, expect, it } from "vitest";
import {
  EVIDENCE_FLOW,
  evidenceStageOf,
  evidenceStepLabel,
  fmtArea,
  fmtDateTime,
  fmtNum,
  fmtPct,
  humanize,
  severitySeries,
  toneFor,
} from "./format";

describe("fmtNum", () => {
  it("formats numbers and returns — for empty", () => {
    expect(fmtNum(1234.567, 2)).toBe("1,234.57");
    expect(fmtNum(null)).toBe("—");
    expect(fmtNum(undefined)).toBe("—");
    expect(fmtNum(Number.NaN)).toBe("—");
  });
});

describe("fmtArea/fmtPct", () => {
  it("appends units", () => {
    expect(fmtArea(43.04)).toBe("43.0 m²");
    expect(fmtPct(0.314)).toBe("31%");
    expect(fmtPct(null)).toBe("—");
  });
});

describe("fmtDateTime", () => {
  it("returns — for empty and formats valid ISO", () => {
    expect(fmtDateTime(null)).toBe("—");
    expect(fmtDateTime("2026-01-31T12:00:00Z")).not.toBe("—");
  });
});

describe("humanize", () => {
  it("strips sensor prefix and tidies idents", () => {
    expect(humanize("sensor-dfd7a151")).toBe("Dfd7a151");
    expect(humanize("storey_1-korrus")).toBe("Storey 1 Korrus");
    expect(humanize(null)).toBe("—");
  });
});

describe("toneFor", () => {
  it("maps severity batteries", () => {
    expect(toneFor("CRITICAL")).toBe("danger");
    expect(toneFor("HIGH")).toBe("danger");
    expect(toneFor("MEDIUM")).toBe("warn");
    expect(toneFor("LOW")).toBe("ok");
    expect(toneFor("UNKNOWN_LOCATION")).toBe("dim");
  });
});

describe("severitySeries", () => {
  it("returns ordered, non-zero severities with counts", () => {
    const s = severitySeries({ HIGH: 4, LOW: 3, CRITICAL: 2, NONE: 0 });
    expect(s.map((x) => x.key)).toEqual(["CRITICAL", "HIGH", "LOW"]);
    expect(s.find((x) => x.key === "HIGH")?.count).toBe(4);
  });
});

describe("evidence chain flow", () => {
  it("labels known steps", () => {
    expect(evidenceStepLabel("anomaly_detected")).toBe("Anomaly detected");
    expect(evidenceStepLabel("priority_ranking")).toBe("Priority ranking");
    expect(evidenceStepLabel("mystery_step")).toBe("mystery_step");
  });

  it("maps steps to the canonical narrative flow", () => {
    expect(EVIDENCE_FLOW).toHaveLength(7);
    expect(evidenceStageOf("anomaly_detected")).toBe("PROBLEM");
    expect(evidenceStageOf("sensor_location")).toBe("MEASUREMENT");
    expect(evidenceStageOf("resource_lookup")).toBe("HISTORICAL BASELINE");
    expect(evidenceStageOf("resource_comparison")).toBe("DEVIATION");
    expect(evidenceStageOf("forecast_direction")).toBe("PERSISTENCE");
    expect(evidenceStageOf("impact_estimation")).toBe("DECISION CANDIDATE");
    expect(evidenceStageOf("priority_ranking")).toBe("RECOMMENDATION");
  });
});

describe("Storey and Space naming helpers", () => {
  it("formats storey names accurately", async () => {
    const { formatStoreyName } = await import("./format");
    expect(formatStoreyName("+Kelder")).toBe("Basement");
    expect(formatStoreyName("Kelder")).toBe("Basement");
    expect(formatStoreyName("1. korrus")).toBe("Floor 1");
    expect(formatStoreyName("2. korrus")).toBe("Floor 2");
    expect(formatStoreyName("3. korrus")).toBe("Floor 3");
    expect(formatStoreyName("Katus")).toBe("Roof");
    expect(formatStoreyName(null)).toBe("Floor —");
  });

  it("formats room names from IFC numbers", async () => {
    const { formatSpaceRoomName } = await import("./format");
    expect(formatSpaceRoomName("114")).toBe("Room 114");
    expect(formatSpaceRoomName("5")).toBe("Room 5");
    expect(formatSpaceRoomName("Room 102")).toBe("Room 102");
    expect(formatSpaceRoomName(null, "space_3U1W8Xs6L9pRXU5Afk5MW1")).toBe("Room 114");
  });

  it("formats full space display name 'Room <name> · Floor <storey>'", async () => {
    const { formatSpaceDisplayName } = await import("./format");
    expect(
      formatSpaceDisplayName({ ifcName: "114", storeyName: "1. korrus" })
    ).toBe("Room 114 · Floor 1");
    expect(
      formatSpaceDisplayName({ ifcName: "5", storeyName: "+Kelder" })
    ).toBe("Room 5 · Basement");
  });

  it("resolves known spaces from dictionary synchronously", async () => {
    const { resolveSpaceDisplayName, resolveSpaceRoomName } = await import("./format");
    expect(resolveSpaceDisplayName("space_3U1W8Xs6L9pRXU5Afk5MW1")).toBe("Room 114 · Floor 3");
    expect(resolveSpaceRoomName("space_3U1W8Xs6L9pRXU5Afk5MW1")).toBe("Room 114");
  });
});