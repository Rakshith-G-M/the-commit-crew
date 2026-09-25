import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { useApi } from "../hooks/useApi";
import { api } from "../api";
import type { AllocationResponse, AllocationSpaceResult } from "../api/types";
import type { ApiError } from "../api/client";
import { ErrorState, LoadingState } from "../components/common";
import {
  fmtArea,
  formatSpaceRoomName,
  formatStoreyName,
  getSpaceMeta,
} from "../lib/format";
import {
  IconPlanning,
  IconArrowRight,
  IconSparkles,
  IconSliders,
  IconBuilding,
} from "../components/icons";

const EQUIPMENT_OPTIONS = [
  { key: "office_workstations", label: "Office Workstations", desc: "Desks, ergonomic seating, electrical power" },
  { key: "classroom_furniture", label: "Classroom Furniture", desc: "Lecture tables, seating rows" },
  { key: "general_equipment", label: "General Equipment & AV", desc: "AV presentation display, whiteboards, wifi" },
];

export function WhatIfPage() {
  const { state: spacesState } = useApi(() => api.spaces({ limit: 500 }), []);

  const [capacity, setCapacity] = useState<number>(22);
  const [equipment, setEquipment] = useState<string[]>(["office_workstations"]);
  const [declareAvailability, setDeclareAvailability] = useState(false);
  const [result, setResult] = useState<AllocationResponse | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<ApiError | null>(null);

  const spaces = spacesState.status === "READY" ? spacesState.data.items : [];
  const spaceIds = useMemo(() => spaces.map((s) => s.space_id), [spaces]);

  const spacesMap = useMemo(() => {
    return new Map(spaces.map((s) => [s.space_id, s]));
  }, [spaces]);

  const availability = useMemo(
    () => (declareAvailability ? Object.fromEntries(spaceIds.map((id) => [id, true])) : null),
    [declareAvailability, spaceIds],
  );

  async function evaluateScenario() {
    setSubmitting(true);
    setError(null);
    setResult(null);
    try {
      const res = await api.evaluateAllocation({
        required_capacity: capacity,
        equipment,
        availability,
      });
      setResult(res);
    } catch (e) {
      setError(e as ApiError);
    } finally {
      setSubmitting(false);
    }
  }

  const qualifiedSpaces = result?.qualified ?? [];
  const excludedSpaces = result?.excluded ?? [];

  const counts = result?.summary_counts ?? {
    total_evaluated: qualifiedSpaces.length + excludedSpaces.length || 115,
    capacity_matches: qualifiedSpaces.length,
    equipment_verified: 0,
    unverified_equipment_matches: equipment.length > 0 ? qualifiedSpaces.length : 0,
    excluded: excludedSpaces.length,
  };

  const hasUnverifiedEquipment = equipment.length > 0;

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "1.75rem", maxWidth: "1440px", margin: "0 auto" }} className="fade-in">
      {/* Page Header */}
      <div>
        <div style={{ display: "flex", alignItems: "center", gap: "0.5rem", fontSize: "0.75rem", fontWeight: 800, color: "var(--accent-cyan)", textTransform: "uppercase", letterSpacing: "0.08em" }}>
          <IconPlanning size={16} /> SPACE OPTIMIZATION & EVALUATION
        </div>
        <h1 style={{ fontSize: "2rem", fontWeight: 800, color: "#ffffff", letterSpacing: "-0.02em", margin: "0.25rem 0 0.5rem" }}>
          SPACE PLANNING
        </h1>
        <p style={{ fontSize: "0.95rem", color: "var(--color-ink-muted)", margin: 0 }}>
          Evaluate space suitability across 115 building spaces based on BIM capacity, equipment requirements, and availability rules.
        </p>
      </div>

      {/* 2-Column Planning Workspace */}
      <div style={{ display: "grid", gridTemplateColumns: "380px 1fr", gap: "1.5rem", alignItems: "start" }}>
        {/* Left Column: Scenario Builder Form */}
        <div className="glass-panel" style={{ padding: "1.5rem", display: "flex", flexDirection: "column", gap: "1.5rem" }}>
          <div style={{ display: "flex", alignItems: "center", gap: "0.5rem", fontSize: "0.85rem", fontWeight: 800, color: "var(--color-ink)", textTransform: "uppercase", letterSpacing: "0.05em" }}>
            <IconSliders size={18} color="var(--accent-cyan)" /> SCENARIO REQUIREMENTS
          </div>

          {/* Capacity Input */}
          <div>
            <label style={{ display: "block", fontSize: "0.75rem", fontWeight: 700, color: "var(--color-ink-muted)", textTransform: "uppercase", marginBottom: "0.5rem" }}>
              REQUIRED CAPACITY (PEOPLE)
            </label>
            <div style={{ display: "flex", alignItems: "center", gap: "0.75rem" }}>
              <input
                type="number"
                min={1}
                max={500}
                value={capacity}
                onChange={(e) => setCapacity(Math.max(1, Number(e.target.value)))}
                style={{
                  width: "120px",
                  background: "rgba(16, 26, 49, 0.8)",
                  border: "1px solid var(--color-line-bright)",
                  borderRadius: "8px",
                  padding: "0.6rem 0.85rem",
                  fontSize: "1.4rem",
                  fontWeight: 800,
                  color: "var(--accent-cyan)",
                  textAlign: "center",
                  outline: "none",
                }}
              />
              <span style={{ fontSize: "0.9rem", color: "var(--color-ink-2)", fontWeight: 600 }}>Occupants</span>
            </div>
          </div>

          {/* Equipment Checklist */}
          <div>
            <label style={{ display: "block", fontSize: "0.75rem", fontWeight: 700, color: "var(--color-ink-muted)", textTransform: "uppercase", marginBottom: "0.5rem" }}>
              EQUIPMENT & FIXTURES
            </label>
            <div style={{ display: "flex", flexDirection: "column", gap: "0.65rem" }}>
              {EQUIPMENT_OPTIONS.map((e) => {
                const isSelected = equipment.includes(e.key);
                return (
                  <label
                    key={e.key}
                    style={{
                      display: "flex",
                      alignItems: "flex-start",
                      gap: "0.75rem",
                      padding: "0.65rem 0.85rem",
                      borderRadius: "8px",
                      background: isSelected ? "rgba(34, 211, 238, 0.1)" : "rgba(16, 26, 49, 0.4)",
                      border: `1px solid ${isSelected ? "rgba(34, 211, 238, 0.4)" : "var(--color-line)"}`,
                      cursor: "pointer",
                      transition: "all 0.2s ease",
                    }}
                  >
                    <input
                      type="checkbox"
                      checked={isSelected}
                      onChange={(ev) => {
                        setEquipment(ev.target.checked ? [...equipment, e.key] : equipment.filter((k) => k !== e.key));
                      }}
                      style={{ marginTop: "3px" }}
                    />
                    <div>
                      <div style={{ fontSize: "0.85rem", fontWeight: 700, color: isSelected ? "#ffffff" : "var(--color-ink)" }}>
                        {e.label}
                      </div>
                      <div style={{ fontSize: "0.725rem", color: "var(--color-ink-dim)" }}>{e.desc}</div>
                    </div>
                  </label>
                );
              })}
            </div>

            {/* Equipment Dataset Disclaimer */}
            <div
              style={{
                marginTop: "0.75rem",
                padding: "0.6rem 0.75rem",
                background: "rgba(251, 191, 36, 0.05)",
                border: "1px solid rgba(251, 191, 36, 0.2)",
                borderRadius: "6px",
                fontSize: "0.75rem",
                color: "var(--color-ink-2)",
                lineHeight: 1.45,
              }}
            >
              <strong style={{ color: "#fbbf24" }}>Equipment Data Notice:</strong> Equipment inventory is not available in the current dataset. Rooms are evaluated by BIM capacity; equipment compatibility is reported as unverified.
            </div>
          </div>

          {/* Availability Toggle */}
          <div>
            <label style={{ display: "flex", alignItems: "center", gap: "0.65rem", cursor: "pointer", fontSize: "0.85rem", color: "var(--color-ink-2)" }}>
              <input
                type="checkbox"
                checked={declareAvailability}
                onChange={(e) => setDeclareAvailability(e.target.checked)}
              />
              Declare all rooms available for allocation
            </label>
            <div style={{ fontSize: "0.75rem", color: "var(--color-ink-dim)", marginTop: "0.35rem", paddingLeft: "1.6rem" }}>
              Scheduling availability is not provided by the current dataset.
            </div>
          </div>

          {/* Evaluate CTA Button */}
          <button
            onClick={evaluateScenario}
            disabled={submitting}
            className="btn-primary"
            style={{ width: "100%", justifyContent: "center", padding: "0.75rem", marginTop: "0.5rem" }}
          >
            {submitting ? "Evaluating Spaces..." : "EVALUATE SCENARIO"} <IconArrowRight size={18} />
          </button>

          {error && <ErrorState error={error} />}
        </div>

        {/* Right Column: Results Panel */}
        <div style={{ display: "flex", flexDirection: "column", gap: "1rem" }}>
          {!result && !submitting && (
            <div className="glass-panel" style={{ padding: "3.5rem 2rem", textAlign: "center", color: "var(--color-ink-muted)" }}>
              <IconSparkles size={40} color="var(--accent-cyan)" style={{ marginBottom: "1rem" }} />
              <h3 style={{ fontSize: "1.2rem", fontWeight: 700, color: "#ffffff", marginBottom: "0.4rem" }}>
                Ready to Evaluate Space Requirements
              </h3>
              <p style={{ fontSize: "0.9rem", color: "var(--color-ink-2)", maxWidth: "460px", margin: "0 auto", lineHeight: 1.5 }}>
                Set your target capacity and required equipment parameters, then click Evaluate Scenario to view matching rooms evaluated by BIM capacity.
              </p>
            </div>
          )}

          {submitting && <LoadingState label="Running space suitability evaluation engine..." />}

          {result && (
            <div style={{ display: "flex", flexDirection: "column", gap: "1.25rem" }}>
              {/* Summary Stats Grid (4 Cards) */}
              <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: "0.85rem" }}>
                {/* Capacity Matches */}
                <div className="glass-panel" style={{ padding: "1rem 1.15rem", borderTop: "3px solid #34d399" }}>
                  <div style={{ fontSize: "0.7rem", fontWeight: 800, color: "#34d399", textTransform: "uppercase", letterSpacing: "0.05em" }}>
                    CAPACITY MATCHES
                  </div>
                  <div style={{ fontSize: "1.8rem", fontWeight: 800, color: "#ffffff", margin: "0.2rem 0", fontFamily: "var(--font-mono)" }}>
                    {counts.capacity_matches}
                  </div>
                  <div style={{ fontSize: "0.725rem", color: "var(--color-ink-dim)" }}>BIM Capacity Suitable</div>
                </div>

                {/* Equipment Verified */}
                <div className="glass-panel" style={{ padding: "1rem 1.15rem", borderTop: "3px solid var(--accent-cyan)" }}>
                  <div style={{ fontSize: "0.7rem", fontWeight: 800, color: "var(--accent-cyan)", textTransform: "uppercase", letterSpacing: "0.05em" }}>
                    EQUIPMENT VERIFIED
                  </div>
                  <div style={{ fontSize: "1.8rem", fontWeight: 800, color: "#ffffff", margin: "0.2rem 0", fontFamily: "var(--font-mono)" }}>
                    {counts.equipment_verified}
                  </div>
                  <div style={{ fontSize: "0.725rem", color: "var(--color-ink-dim)" }}>Verified Inventory</div>
                </div>

                {/* Excluded */}
                <div className="glass-panel" style={{ padding: "1rem 1.15rem", borderTop: "3px solid #f87171" }}>
                  <div style={{ fontSize: "0.7rem", fontWeight: 800, color: "#f87171", textTransform: "uppercase", letterSpacing: "0.05em" }}>
                    EXCLUDED
                  </div>
                  <div style={{ fontSize: "1.8rem", fontWeight: 800, color: "#ffffff", margin: "0.2rem 0", fontFamily: "var(--font-mono)" }}>
                    {counts.excluded}
                  </div>
                  <div style={{ fontSize: "0.725rem", color: "var(--color-ink-dim)" }}>Capacity Insufficient</div>
                </div>

                {/* Total Evaluated */}
                <div className="glass-panel" style={{ padding: "1rem 1.15rem", borderTop: "3px solid var(--color-line-bright)" }}>
                  <div style={{ fontSize: "0.7rem", fontWeight: 800, color: "var(--color-ink-muted)", textTransform: "uppercase", letterSpacing: "0.05em" }}>
                    TOTAL EVALUATED
                  </div>
                  <div style={{ fontSize: "1.8rem", fontWeight: 800, color: "#ffffff", margin: "0.2rem 0", fontFamily: "var(--font-mono)" }}>
                    {counts.total_evaluated}
                  </div>
                  <div style={{ fontSize: "0.725rem", color: "var(--color-ink-dim)" }}>Building Spaces</div>
                </div>
              </div>

              {/* Recommended Spaces Section */}
              <div>
                <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: "0.5rem" }}>
                  <div style={{ fontSize: "0.95rem", fontWeight: 800, color: "#ffffff", letterSpacing: "0.02em" }}>
                    {hasUnverifiedEquipment ? `RECOMMENDED SPACES (${qualifiedSpaces.length})` : `MATCHING SPACES (${qualifiedSpaces.length})`}
                  </div>
                </div>
                <div style={{ fontSize: "0.8rem", color: "var(--color-ink-2)", marginBottom: "1rem" }}>
                  Ranked by verified BIM constraints. Unverified requirements are shown separately.
                </div>

                {qualifiedSpaces.length === 0 ? (
                  <div className="glass-panel" style={{ padding: "2.5rem 2rem", textAlign: "center", color: "#f87171" }}>
                    <div style={{ fontSize: "1rem", fontWeight: 700, marginBottom: "0.35rem" }}>
                      No spaces match the required capacity ({capacity} occupants)
                    </div>
                    <p style={{ fontSize: "0.85rem", color: "var(--color-ink-muted)", margin: 0 }}>
                      Try reducing the required occupant capacity to see available building spaces.
                    </p>
                  </div>
                ) : (
                  <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(320px, 1fr))", gap: "1rem" }}>
                    {qualifiedSpaces.map((q: AllocationSpaceResult, idx: number) => {
                      const spaceData = spacesMap.get(q.space_id);
                      const meta = getSpaceMeta(q.space_id);
                      const roomName = formatSpaceRoomName(meta?.ifcName, q.space_id);
                      const storeyName = formatStoreyName(meta?.storeyName ?? meta?.rawStorey);
                      const area = spaceData?.area_m2 ?? meta?.areaM2;
                      const roomCap = q.capacity_occupants ?? spaceData?.capacity_occupants ?? "N/A";

                      return (
                        <div
                          key={q.space_id}
                          className="glass-panel glass-panel-hover"
                          style={{
                            padding: "1.25rem",
                            display: "flex",
                            flexDirection: "column",
                            gap: "0.75rem",
                            borderLeft: "4px solid #34d399",
                          }}
                        >
                          {/* Room Title Header */}
                          <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between" }}>
                            <div>
                              <div style={{ fontSize: "1.05rem", fontWeight: 800, color: "#ffffff" }}>
                                {roomName}
                              </div>
                              <div style={{ fontSize: "0.8rem", color: "var(--color-ink-muted)", marginTop: "0.15rem" }}>
                                {storeyName} {area ? `· ${fmtArea(area)}` : ""}
                              </div>
                            </div>
                            <span style={{ fontSize: "0.725rem", fontFamily: "var(--font-mono)", color: "var(--color-ink-dim)", background: "rgba(255,255,255,0.06)", padding: "0.15rem 0.45rem", borderRadius: "4px" }}>
                              #{idx + 1}
                            </span>
                          </div>

                          {/* Room Specs Line */}
                          <div style={{ fontSize: "0.825rem", color: "var(--color-ink-2)", fontFamily: "var(--font-mono)" }}>
                            Design capacity: <strong style={{ color: "var(--accent-cyan)" }}>{roomCap} persons</strong>
                          </div>

                          {/* Status Chips */}
                          <div style={{ display: "flex", flexDirection: "column", gap: "0.35rem" }}>
                            {/* Capacity Suitable Chip */}
                            <div style={{ display: "flex", alignItems: "center", gap: "0.4rem", fontSize: "0.8rem", fontWeight: 700, color: "#34d399" }}>
                              <span>✓ Capacity suitable</span>
                              <span style={{ fontSize: "0.725rem", fontWeight: 400, color: "var(--color-ink-dim)" }}>
                                ({roomCap} &ge; {capacity})
                              </span>
                            </div>

                            {/* Equipment Status Chip */}
                            {equipment.length > 0 && (
                              <div style={{ display: "flex", alignItems: "center", gap: "0.4rem", fontSize: "0.8rem", fontWeight: 700, color: "#fbbf24" }}>
                                <span>⚠ Equipment compatibility not verified</span>
                              </div>
                            )}
                          </div>

                          {/* View in Digital Twin Link */}
                          <div style={{ paddingTop: "0.35rem", borderTop: "1px solid var(--color-line)" }}>
                            <Link
                              to={`/twin?space=${encodeURIComponent(q.space_id)}`}
                              style={{
                                display: "inline-flex",
                                alignItems: "center",
                                gap: "0.35rem",
                                fontSize: "0.8rem",
                                fontWeight: 700,
                                color: "var(--accent-cyan)",
                                textDecoration: "none",
                              }}
                            >
                              <IconBuilding size={14} /> View in Digital Twin &rarr;
                            </Link>
                          </div>
                        </div>
                      );
                    })}
                  </div>
                )}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}