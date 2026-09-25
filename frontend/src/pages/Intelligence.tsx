import { useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { useApi } from "../hooks/useApi";
import { api } from "../api";
import { ErrorState, LoadingState } from "../components/common";
import {
  anomalyDirection,
  anomalyNarrative,
  measureLabel,
  pickMostSignificant,
  splitSignals,
} from "../lib/anomaly";
import { fmtNum } from "../lib/format";
import { getSensorDisplayName } from "../lib/sensorsData";
import {
  AnomaliesTab,
  CandidatesTab,
  ForecastsTab,
  HealthTab,
  RecommendationsTab,
} from "./intelligenceTabs";
import {
  IconActivity,
  IconAlert,
  IconShield,
  IconTrending,
  IconSensor,
  IconSparkles,
} from "../components/icons";

const TABS = [
  { key: "anomalies", label: "Anomalies", icon: <IconAlert size={16} />, desc: "Detected deviations" },
  { key: "health", label: "Sensor Health", icon: <IconSensor size={16} />, desc: "Stream degradation" },
  { key: "recommendations", label: "Recommendations", icon: <IconShield size={16} />, desc: "AI Action priorities" },
  { key: "forecasts", label: "Forecasts", icon: <IconTrending size={16} />, desc: "Predictive trends" },
  { key: "candidates", label: "Decision Log", icon: <IconActivity size={16} />, desc: "Engine audit trail" },
];

function IntelligenceSummary() {
  const { state } = useApi(() => api.telemetrySummary(), []);
  const { state: health } = useApi(() => api.health({ limit: 1 }), []);

  if (state.status === "LOADING" || health.status === "LOADING") return <LoadingState />;
  if (state.status === "ERROR") return <ErrorState error={state.error} />;
  if (state.status !== "READY" || !state.data) return null;

  const s = state.data;
  const anomalies = s.intelligence.anomalies;
  const signals = splitSignals(anomalies.by_measurement_type);
  const healthSummary = health.status === "READY" ? health.data.summary : undefined;
  const hsd = (healthSummary as Record<string, Record<string, number> | undefined> | undefined)?.health_status_distribution;
  const degradedCount = healthSummary?.degraded ?? hsd?.["DEGRADED"] ?? 0;
  const healthyCount = healthSummary?.healthy ?? hsd?.["HEALTHY"] ?? 0;
  const totalDevices = healthSummary?.devices ?? degradedCount + healthyCount;

  return (
    <div style={{ display: "grid", gridTemplateColumns: "repeat(5, 1fr)", gap: "1rem" }}>
      <div className="glass-panel glass-panel-hover" style={{ padding: "1.15rem 1.25rem", borderTop: "3px solid var(--color-danger)" }}>
        <div style={{ fontSize: "0.78rem", fontWeight: 700, color: "var(--color-ink-muted)", textTransform: "uppercase", letterSpacing: "0.03em" }}>Critical Signals</div>
        <div style={{ fontSize: "1.8rem", fontWeight: 800, color: "var(--color-danger)", margin: "0.2rem 0" }}>
          {fmtNum(anomalies.by_severity?.CRITICAL ?? 0, 0)}
        </div>
        <div style={{ fontSize: "0.8rem", color: "var(--color-ink-dim)" }}>Immediate review</div>
      </div>

      <div className="glass-panel glass-panel-hover" style={{ padding: "1.15rem 1.25rem", borderTop: "3px solid var(--accent-amber)" }}>
        <div style={{ fontSize: "0.78rem", fontWeight: 700, color: "var(--color-ink-muted)", textTransform: "uppercase", letterSpacing: "0.03em" }}>High Priority</div>
        <div style={{ fontSize: "1.8rem", fontWeight: 800, color: "var(--accent-amber)", margin: "0.2rem 0" }}>
          {fmtNum(anomalies.by_severity?.HIGH ?? 0, 0)}
        </div>
        <div style={{ fontSize: "0.8rem", color: "var(--color-ink-dim)" }}>Elevated events</div>
      </div>

      <div className="glass-panel glass-panel-hover" style={{ padding: "1.15rem 1.25rem", borderTop: "3px solid var(--accent-cyan)" }}>
        <div style={{ fontSize: "0.78rem", fontWeight: 700, color: "var(--color-ink-muted)", textTransform: "uppercase", letterSpacing: "0.03em" }}>Environmental</div>
        <div style={{ fontSize: "1.8rem", fontWeight: 800, color: "var(--accent-cyan)", margin: "0.2rem 0" }}>
          {fmtNum(signals.environmental, 0)}
        </div>
        <div style={{ fontSize: "0.8rem", color: "var(--color-ink-dim)" }}>CO₂ · Temp · Humidity</div>
      </div>

      <div className="glass-panel glass-panel-hover" style={{ padding: "1.15rem 1.25rem", borderTop: "3px solid var(--accent-blue)" }}>
        <div style={{ fontSize: "0.78rem", fontWeight: 700, color: "var(--color-ink-muted)", textTransform: "uppercase", letterSpacing: "0.03em" }}>Resource & Power</div>
        <div style={{ fontSize: "1.8rem", fontWeight: 800, color: "var(--accent-blue)", margin: "0.2rem 0" }}>
          {fmtNum(signals.resource, 0)}
        </div>
        <div style={{ fontSize: "0.8rem", color: "var(--color-ink-dim)" }}>Meter deviations</div>
      </div>

      <div className="glass-panel glass-panel-hover" style={{ padding: "1.15rem 1.25rem", borderTop: "3px solid var(--accent-violet)" }}>
        <div style={{ fontSize: "0.78rem", fontWeight: 700, color: "var(--color-ink-muted)", textTransform: "uppercase", letterSpacing: "0.03em" }}>Degraded Sensors</div>
        <div style={{ fontSize: "1.8rem", fontWeight: 800, color: "var(--accent-violet)", margin: "0.2rem 0" }}>
          {fmtNum(degradedCount, 0)}
        </div>
        <div style={{ fontSize: "0.8rem", color: "var(--color-ink-dim)" }}>{healthyCount} of {totalDevices} healthy</div>
      </div>
    </div>
  );
}

function SignificantSignals() {
  const { state } = useApi(
    () => Promise.all([
      api.anomalies({ severity: "CRITICAL", limit: 200 }),
      api.anomalies({ severity: "HIGH", limit: 200 }),
    ]),
    [],
  );

  const picked = useMemo(() => {
    if (state.status !== "READY") return [];
    return pickMostSignificant([...state.data[0].items, ...state.data[1].items]);
  }, [state]);

  if (state.status === "LOADING") return <LoadingState label="Scanning telemetry signals..." />;
  if (state.status === "ERROR") return <ErrorState error={state.error} />;

  if (picked.length === 0) return null;

  return (
    <div>
      <div style={{ fontSize: "0.9rem", fontWeight: 800, color: "var(--color-ink)", marginBottom: "0.85rem", letterSpacing: "0.01em" }}>
        Primary Operational Signals by Measurement Type
      </div>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(300px, 1fr))", gap: "1rem" }}>
        {picked.map((a) => {
          const dir = anomalyDirection(a);
          const isCrit = a.severity === "CRITICAL";

          return (
            <div
              key={`${a.sensor_id}-${a.timestamp}`}
              className="glass-panel glass-panel-hover"
              style={{
                padding: "1.25rem",
                borderLeft: `4px solid ${isCrit ? "var(--color-danger)" : "var(--color-warn)"}`,
              }}
            >
              <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", marginBottom: "0.5rem" }}>
                <div>
                  <div style={{ fontSize: "1rem", fontWeight: 800, color: "var(--color-ink)" }}>
                    {measureLabel(a.measurement_type)}
                  </div>
                  <div style={{ fontSize: "0.85rem", color: "var(--color-ink-muted)", marginTop: "0.15rem", fontWeight: 600 }}>
                    {getSensorDisplayName(a.sensor_id, a.measurement_type)}
                  </div>
                </div>
                <span
                  style={{
                    padding: "0.2rem 0.55rem",
                    borderRadius: "9999px",
                    fontSize: "0.72rem",
                    fontWeight: 800,
                    background: isCrit ? "rgba(244, 63, 94, 0.15)" : "rgba(245, 158, 11, 0.15)",
                    color: isCrit ? "#fda4af" : "#fde047",
                    border: `1px solid ${isCrit ? "rgba(244, 63, 94, 0.3)" : "rgba(245, 158, 11, 0.3)"}`,
                  }}
                >
                  {a.severity}
                </span>
              </div>

              <p style={{ margin: "0.5rem 0 0.85rem", fontSize: "0.9rem", color: "var(--color-ink-muted)", lineHeight: 1.55 }}>
                {anomalyNarrative(a)}
              </p>

              <div style={{ display: "flex", gap: "1.25rem", fontSize: "0.85rem", fontFamily: "var(--font-mono)", color: "var(--color-ink-dim)" }}>
                <span>Current: <strong style={{ color: "var(--color-ink)" }}>{a.value !== null ? `${fmtNum(a.value, 1)}${a.unit ? ` ${a.unit}` : ""}` : "—"}</strong></span>
                <span>Baseline: <strong>{a.expected !== null ? fmtNum(a.expected, 1) : "—"}</strong></span>
                <span>Δ <strong>{a.deviation !== null ? `${fmtNum(a.deviation, 1)}%` : "—"} {dir === "above" ? "↑" : "↓"}</strong></span>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

export function IntelligencePage() {
  const [params] = useSearchParams();
  const focusRec = params.get("rec");
  const initialTab = params.get("tab") ?? (focusRec ? "recommendations" : "anomalies");
  const [tab, setTab] = useState<string>(initialTab);

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "1.75rem", maxWidth: "1440px", margin: "0 auto" }} className="fade-in">
      {/* Workspace Header */}
      <div>
        <div style={{ display: "flex", alignItems: "center", gap: "0.5rem", fontSize: "0.78rem", fontWeight: 800, color: "var(--accent-blue)", textTransform: "uppercase", letterSpacing: "0.06em" }}>
          <IconSparkles size={14} /> SIGNALS → UNDERSTANDING → ACTION
        </div>
        <h1 style={{ fontSize: "2rem", fontWeight: 800, color: "#ffffff", letterSpacing: "-0.02em", margin: "0.25rem 0 0.5rem" }}>
          CAMPUS INTELLIGENCE WORKSPACE
        </h1>
        <p style={{ fontSize: "0.95rem", color: "var(--color-ink-muted)", lineHeight: 1.55 }}>
          AI operations platform monitoring telemetry streams, evaluating anomaly signals, and generating priority maintenance recommendations.
        </p>
      </div>

      {/* Summary KPI Strip */}
      <IntelligenceSummary />

      {/* Significant Signals */}
      <SignificantSignals />

      {/* Navigation Tab Bar */}
      <div
        className="glass-panel"
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(5, 1fr)",
          gap: "0.5rem",
          padding: "0.5rem",
          background: "var(--bg-surface)",
        }}
      >
        {TABS.map((t) => {
          const isActive = tab === t.key;
          return (
            <button
              key={t.key}
              onClick={() => setTab(t.key)}
              style={{
                display: "flex",
                flexDirection: "column",
                alignItems: "center",
                justifyContent: "center",
                gap: "0.3rem",
                padding: "0.8rem 0.5rem",
                borderRadius: "10px",
                border: `1px solid ${isActive ? "var(--color-line-bright)" : "transparent"}`,
                background: isActive ? "linear-gradient(135deg, rgba(56, 189, 248, 0.15) 0%, rgba(139, 92, 246, 0.15) 100%)" : "transparent",
                color: isActive ? "#ffffff" : "var(--color-ink-muted)",
                cursor: "pointer",
                transition: "all 0.2s ease",
              }}
            >
              <div style={{ color: isActive ? "var(--accent-blue)" : "var(--color-ink-dim)" }}>{t.icon}</div>
              <span style={{ fontSize: "0.9rem", fontWeight: isActive ? 700 : 500 }}>{t.label}</span>
              <span style={{ fontSize: "0.75rem", color: isActive ? "var(--accent-cyan)" : "var(--color-ink-dim)" }}>{t.desc}</span>
            </button>
          );
        })}
      </div>

      {/* Tab Content Container */}
      <div className="glass-panel" style={{ padding: "1.5rem" }}>
        {tab === "anomalies" && <AnomaliesTab />}
        {tab === "forecasts" && <ForecastsTab />}
        {tab === "recommendations" && <RecommendationsTab />}
        {tab === "candidates" && <CandidatesTab />}
        {tab === "health" && <HealthTab />}
      </div>
    </div>
  );
}
