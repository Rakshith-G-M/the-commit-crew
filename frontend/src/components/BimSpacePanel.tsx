import { useState, type ReactNode } from "react";
import { useApi } from "../hooks/useApi";
import { api } from "../api";
import {
  fmtArea,
  fmtNum,
  fmtVolume,
  formatStoreyName,
  formatSpaceRoomName,
  getSpaceMeta,
} from "../lib/format";
import { Badge } from "./common";

function Row({ label, value }: { label: string; value: ReactNode }) {
  return (
    <div
      style={{
        display: "flex",
        alignItems: "center",
        justifyContent: "space-between",
        gap: "0.625rem",
        padding: "0.4rem 0",
        borderBottom: "1px solid rgba(30,47,66,0.4)",
        fontSize: "0.78rem",
      }}
    >
      <span style={{ color: "var(--color-ink-dim)", flexShrink: 0 }}>{label}</span>
      <span style={{ fontFamily: "var(--font-mono)", textAlign: "right", color: "var(--color-ink)" }}>
        {value}
      </span>
    </div>
  );
}

const DESIGN_LABELS: Array<{ key: string; label: string; unit: string }> = [
  { key: "lighting_design_load_w", label: "Lighting design load", unit: "W" },
  { key: "lighting_design_load_w_per_area", label: "Lighting intensity", unit: "W/m²" },
  { key: "power_design_load_w", label: "Power design load", unit: "W" },
  { key: "power_design_load_w_per_area", label: "Power intensity", unit: "W/m²" },
  { key: "illumination_lx", label: "Average illumination", unit: "lx" },
  { key: "design_cooling_load_w", label: "Design cooling load", unit: "W" },
  { key: "design_heating_load_w", label: "Design heating load", unit: "W" },
  { key: "air_changes_per_hour", label: "Air changes", unit: "/h" },
  { key: "design_occupancy_people", label: "Design occupancy", unit: "people" },
  { key: "area_per_person_m2", label: "Area per person", unit: "m²/person" },
];

function DesignValues({ spaceId }: { spaceId: string }) {
  const { state } = useApi(() => api.bimDesign(spaceId), [spaceId]);

  if (state.status === "LOADING")
    return (
      <div
        style={{
          marginTop: "0.875rem",
          padding: "0.625rem 0.75rem",
          background: "var(--color-panel-3)",
          borderRadius: "6px",
          fontSize: "0.72rem",
          color: "var(--color-ink-dim)",
        }}
      >
        Loading design values…
      </div>
    );

  if (state.status !== "READY")
    return (
      <div
        style={{
          marginTop: "0.875rem",
          padding: "0.625rem 0.75rem",
          background: "var(--color-panel-3)",
          borderRadius: "6px",
          fontSize: "0.72rem",
          color: "var(--color-ink-dim)",
        }}
      >
        Design values unavailable for this space.
      </div>
    );

  const design = state.data.design;
  const present = DESIGN_LABELS.filter((d) => design[d.key] !== undefined);

  if (present.length === 0)
    return (
      <div
        style={{
          marginTop: "0.875rem",
          padding: "0.625rem 0.75rem",
          background: "var(--color-panel-3)",
          borderRadius: "6px",
          fontSize: "0.72rem",
          color: "var(--color-ink-dim)",
        }}
      >
        No design-load values published for this space.
      </div>
    );

  return (
    <div
      style={{
        marginTop: "0.875rem",
        background: "var(--color-panel-3)",
        border: "1px solid var(--color-line)",
        borderRadius: "8px",
        padding: "0.75rem",
      }}
    >
      <div
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          marginBottom: "0.625rem",
        }}
      >
        <span className="bim-label">Design loads (specification)</span>
        <Badge tone="ok" mono label="IFC design" />
      </div>
      <div>
        {present.map((d) => (
          <Row
            key={d.key}
            label={d.label}
            value={`${fmtNum(design[d.key], 1)} ${d.unit}`}
          />
        ))}
      </div>
    </div>
  );
}

export function BimSpacePanel({
  spaceId,
  spaceName,
  storey,
  area,
  volume,
  height,
  capacity,
  occupiable,
  conditioning,
  ifcGlobalId,
  rawStorey,
}: {
  spaceId: string;
  spaceName?: string | null;
  storey: string | null;
  area: number | null;
  volume: number | null;
  height: number | null;
  capacity: number | null;
  occupiable: boolean;
  conditioning: string | null;
  ifcGlobalId?: string | null;
  rawStorey?: string | null;
}) {
  const [showTechDetails, setShowTechDetails] = useState(false);
  const meta = getSpaceMeta(spaceId);

  const humanRoomName = formatSpaceRoomName(spaceName ?? meta?.ifcName, spaceId);
  const humanStoreyName = formatStoreyName(storey ?? meta?.storeyName);
  const effectiveGlobalId = ifcGlobalId ?? meta?.ifcGlobalId ?? spaceId.replace(/^space_/i, "");
  const effectiveRawStorey = rawStorey ?? meta?.rawStorey ?? storey ?? "—";

  return (
    <div
      style={{
        background: "rgba(11, 15, 28, 0.75)",
        border: "1px solid var(--color-line)",
        borderRadius: "12px",
        overflow: "hidden",
        display: "flex",
        flexDirection: "column",
      }}
    >
      {/* Panel Header */}
      <div
        style={{
          padding: "0.875rem 1rem",
          borderBottom: "1px solid var(--color-line)",
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          background: "rgba(15, 23, 42, 0.6)",
        }}
      >
        <div>
          <div style={{ fontSize: "0.75rem", fontWeight: 800, color: "var(--accent-cyan)", letterSpacing: "0.06em", textTransform: "uppercase" }}>
            SPACE INSPECTOR
          </div>
          <div
            style={{
              fontSize: "0.75rem",
              color: "var(--color-ink-dim)",
              fontFamily: "var(--font-mono)",
              marginTop: "2px",
            }}
          >
            {spaceId}
          </div>
        </div>
        <Badge tone="info" mono label="BIM Space" />
      </div>

      <div style={{ padding: "1rem", display: "flex", flexDirection: "column", gap: "0.75rem" }}>
        {/* Selected Room Header */}
        <div>
          <div
            style={{
              fontSize: "1.2rem",
              fontWeight: 800,
              color: "#ffffff",
              letterSpacing: "-0.01em",
              lineHeight: 1.25,
            }}
          >
            {humanRoomName}
          </div>
          <div
            style={{
              fontSize: "0.8rem",
              color: "var(--color-ink-muted)",
              marginTop: "0.2rem",
            }}
          >
            {humanStoreyName} · TalTech DS3 Ehituse Mäemaja
          </div>
        </div>

        {/* Core BIM Metrics Grid */}
        <div
          style={{
            display: "grid",
            gridTemplateColumns: "1fr 1fr",
            gap: "0.5rem",
            background: "rgba(5, 7, 17, 0.6)",
            padding: "0.75rem",
            borderRadius: "8px",
            border: "1px solid var(--color-line)",
          }}
        >
          <div>
            <div style={{ fontSize: "0.7rem", color: "var(--color-ink-dim)", textTransform: "uppercase", letterSpacing: "0.04em", fontWeight: 700 }}>
              AREA
            </div>
            <div style={{ fontSize: "1rem", fontWeight: 700, color: "#ffffff", fontFamily: "var(--font-mono)", marginTop: "2px" }}>
              {fmtArea(area ?? meta?.areaM2)}
            </div>
          </div>
          <div>
            <div style={{ fontSize: "0.7rem", color: "var(--color-ink-dim)", textTransform: "uppercase", letterSpacing: "0.04em", fontWeight: 700 }}>
              VOLUME
            </div>
            <div style={{ fontSize: "1rem", fontWeight: 700, color: "#ffffff", fontFamily: "var(--font-mono)", marginTop: "2px" }}>
              {fmtVolume(volume)}
            </div>
          </div>
          <div>
            <div style={{ fontSize: "0.7rem", color: "var(--color-ink-dim)", textTransform: "uppercase", letterSpacing: "0.04em", fontWeight: 700 }}>
              HEIGHT
            </div>
            <div style={{ fontSize: "1rem", fontWeight: 700, color: "#ffffff", fontFamily: "var(--font-mono)", marginTop: "2px" }}>
              {height !== null ? `${fmtNum(height, 1)} m` : "—"}
            </div>
          </div>
          <div>
            <div style={{ fontSize: "0.7rem", color: "var(--color-ink-dim)", textTransform: "uppercase", letterSpacing: "0.04em", fontWeight: 700 }}>
              DESIGN CAPACITY
            </div>
            <div style={{ fontSize: "1rem", fontWeight: 700, color: "#ffffff", fontFamily: "var(--font-mono)", marginTop: "2px" }}>
              {capacity !== null ? `${fmtNum(capacity, 0)} persons` : "Not published"}
            </div>
          </div>
        </div>

        {/* Detailed Attribute Rows */}
        <div style={{ display: "flex", flexDirection: "column", gap: "0.15rem" }}>
          <Row label="Floor" value={humanStoreyName} />
          <Row
            label="Occupiable"
            value={
              <Badge
                tone={occupiable ? "ok" : "dim"}
                label={occupiable ? "Yes" : "No"}
                mono
              />
            }
          />
          <Row label="Conditioning" value={conditioning ?? "Unknown"} />
        </div>

        {/* BIM Design Data Notice */}
        <div
          style={{
            padding: "0.65rem 0.75rem",
            background: "rgba(52, 211, 153, 0.05)",
            border: "1px solid rgba(52, 211, 153, 0.2)",
            borderLeft: "3px solid #34d399",
            borderRadius: "0 6px 6px 0",
          }}
        >
          <div style={{ fontSize: "0.72rem", fontWeight: 800, color: "#34d399", letterSpacing: "0.05em", marginBottom: "0.2rem" }}>
            BIM DESIGN DATA
          </div>
          <div style={{ fontSize: "0.78rem", color: "var(--color-ink-2)", lineHeight: 1.5 }}>
            Design/specification values from the IFC model. Not measured operational data.
          </div>
        </div>

        {/* Operational Telemetry Notice */}
        <div
          style={{
            padding: "0.65rem 0.75rem",
            background: "rgba(251, 191, 36, 0.05)",
            border: "1px solid rgba(251, 191, 36, 0.2)",
            borderLeft: "3px solid #fbbf24",
            borderRadius: "0 6px 6px 0",
          }}
        >
          <div style={{ fontSize: "0.72rem", fontWeight: 800, color: "#fbbf24", letterSpacing: "0.05em", marginBottom: "0.2rem" }}>
            OPERATIONAL TELEMETRY
          </div>
          <div style={{ fontSize: "0.78rem", color: "var(--color-ink-2)", lineHeight: 1.5 }}>
            Room-level sensor mapping unavailable. Sensor→space mapping is UNRESOLVED in the current data release — telemetry values are not attributed to individual rooms.
          </div>
        </div>

        {/* Collapsible Technical Details */}
        <div
          style={{
            background: "rgba(5, 7, 17, 0.6)",
            border: "1px solid var(--color-line)",
            borderRadius: "8px",
            overflow: "hidden",
          }}
        >
          <button
            type="button"
            onClick={() => setShowTechDetails((v) => !v)}
            style={{
              width: "100%",
              padding: "0.55rem 0.75rem",
              background: "transparent",
              border: "none",
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
              cursor: "pointer",
              fontSize: "0.78rem",
              fontWeight: 600,
              color: "var(--color-ink-muted)",
              fontFamily: "var(--font-mono)",
            }}
          >
            <span>Technical Details</span>
            <span>{showTechDetails ? "▲ Hide" : "▼ Expand"}</span>
          </button>

          {showTechDetails && (
            <div
              style={{
                padding: "0.65rem 0.75rem",
                borderTop: "1px solid var(--color-line)",
                fontSize: "0.75rem",
                display: "flex",
                flexDirection: "column",
                gap: "0.4rem",
                fontFamily: "var(--font-mono)",
              }}
            >
              <div style={{ display: "flex", justifyContent: "space-between", gap: "0.5rem" }}>
                <span style={{ color: "var(--color-ink-dim)" }}>IfcSpace ID:</span>
                <span style={{ color: "#ffffff", wordBreak: "break-all" }}>{spaceId}</span>
              </div>
              <div style={{ display: "flex", justifyContent: "space-between", gap: "0.5rem" }}>
                <span style={{ color: "var(--color-ink-dim)" }}>GlobalId:</span>
                <span style={{ color: "#ffffff", wordBreak: "break-all" }}>{effectiveGlobalId}</span>
              </div>
              <div style={{ display: "flex", justifyContent: "space-between", gap: "0.5rem" }}>
                <span style={{ color: "var(--color-ink-dim)" }}>IFC Entity:</span>
                <span style={{ color: "var(--accent-cyan)" }}>IfcSpace</span>
              </div>
              <div style={{ display: "flex", justifyContent: "space-between", gap: "0.5rem" }}>
                <span style={{ color: "var(--color-ink-dim)" }}>IFC Space Name:</span>
                <span style={{ color: "#ffffff" }}>{spaceName ?? meta?.ifcName ?? "—"}</span>
              </div>
              <div style={{ display: "flex", justifyContent: "space-between", gap: "0.5rem" }}>
                <span style={{ color: "var(--color-ink-dim)" }}>Storey (Raw IFC):</span>
                <span style={{ color: "#ffffff" }}>{effectiveRawStorey}</span>
              </div>
            </div>
          )}
        </div>

        {/* Design values from API */}
        <DesignValues spaceId={spaceId} />
      </div>
    </div>
  );
}