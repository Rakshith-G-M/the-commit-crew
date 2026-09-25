import { useState } from "react";
import { useReplay } from "../hooks/useReplay";
import { fmtDateTime, fmtNum } from "../lib/format";

export function ReplayBar() {
  const {
    state,
    isRunning,
    speed,
    simTimestamp,
    readingsCount,
    anomaliesCount,
    start,
    pause,
    reset,
    setSpeed,
    isConnected,
    mode,
  } = useReplay();

  const [expanded, setExpanded] = useState(false);

  const activeChannels = state?.channels ?? [];
  const activeAnomalies = state?.active_anomalies ?? [];

  return (
    <div
      style={{
        background: "var(--color-panel)",
        border: "1px solid var(--color-line)",
        borderRadius: "10px",
        padding: "0.625rem 1rem",
        marginBottom: "1rem",
        display: "flex",
        flexDirection: "column",
        gap: "0.5rem",
        boxShadow: "0 2px 8px rgba(0,0,0,0.15)",
      }}
    >
      <div
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          flexWrap: "wrap",
          gap: "0.75rem",
        }}
      >
        {/* Left: Indicator & Status */}
        <div style={{ display: "flex", alignItems: "center", gap: "0.75rem" }}>
          <div
            style={{
              display: "flex",
              alignItems: "center",
              gap: "0.375rem",
              background: isRunning ? "rgba(34,197,94,0.1)" : "rgba(148,163,184,0.1)",
              border: `1px solid ${isRunning ? "rgba(34,197,94,0.3)" : "rgba(148,163,184,0.2)"}`,
              padding: "0.2rem 0.5rem",
              borderRadius: "4px",
            }}
          >
            <span
              className={`status-dot ${isRunning ? "ok pulse" : "dim"}`}
              style={{ width: "7px", height: "7px" }}
            />
            <span
              style={{
                fontSize: "0.68rem",
                fontWeight: 700,
                letterSpacing: "0.06em",
                textTransform: "uppercase",
                color: isRunning ? "var(--color-ok)" : "var(--color-ink-dim)",
                fontFamily: "var(--font-mono)",
              }}
            >
              {isRunning ? "Simulating Live Feed" : "Replay Paused"}
            </span>
          </div>

          {/* Simulated Timestamp */}
          <div style={{ display: "flex", alignItems: "baseline", gap: "0.375rem" }}>
            <span
              style={{
                fontSize: "0.65rem",
                color: "var(--color-ink-faint)",
                fontFamily: "var(--font-mono)",
                textTransform: "uppercase",
              }}
            >
              Sim Clock:
            </span>
            <span
              style={{
                fontSize: "0.78rem",
                fontFamily: "var(--font-mono)",
                fontWeight: 600,
                color: "var(--color-accent-3)",
              }}
            >
              {simTimestamp ? fmtDateTime(simTimestamp) : "2025-06-01 00:00:00"}
            </span>
          </div>
        </div>

        {/* Center: Controls (Play/Pause, Speed, Reset) */}
        <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
          {isRunning ? (
            <button
              onClick={() => pause()}
              style={{
                display: "inline-flex",
                alignItems: "center",
                gap: "0.375rem",
                background: "rgba(245,158,11,0.15)",
                border: "1px solid rgba(245,158,11,0.3)",
                color: "#fbbf24",
                padding: "0.25rem 0.65rem",
                borderRadius: "4px",
                fontSize: "0.72rem",
                fontWeight: 600,
                cursor: "pointer",
              }}
            >
              <svg width="10" height="10" viewBox="0 0 24 24" fill="currentColor">
                <rect x="6" y="4" width="4" height="16" rx="1" />
                <rect x="14" y="4" width="4" height="16" rx="1" />
              </svg>
              Pause
            </button>
          ) : (
            <button
              onClick={() => start()}
              style={{
                display: "inline-flex",
                alignItems: "center",
                gap: "0.375rem",
                background: "rgba(34,197,94,0.15)",
                border: "1px solid rgba(34,197,94,0.3)",
                color: "#4ade80",
                padding: "0.25rem 0.65rem",
                borderRadius: "4px",
                fontSize: "0.72rem",
                fontWeight: 600,
                cursor: "pointer",
              }}
            >
              <svg width="10" height="10" viewBox="0 0 24 24" fill="currentColor">
                <path d="M5 3l14 9-14 9V3z" />
              </svg>
              Start Replay
            </button>
          )}

          {/* Speed Selectors */}
          <div
            style={{
              display: "flex",
              border: "1px solid var(--color-line)",
              borderRadius: "4px",
              overflow: "hidden",
            }}
          >
            {[1, 5, 10, 50].map((s) => (
              <button
                key={s}
                onClick={() => setSpeed(s)}
                style={{
                  background: speed === s ? "var(--color-accent-3)" : "transparent",
                  color: speed === s ? "#000" : "var(--color-ink-dim)",
                  border: "none",
                  padding: "0.2rem 0.45rem",
                  fontSize: "0.68rem",
                  fontFamily: "var(--font-mono)",
                  fontWeight: speed === s ? 700 : 500,
                  cursor: "pointer",
                }}
              >
                {s}×
              </button>
            ))}
          </div>

          <button
            onClick={() => reset()}
            title="Reset replay to beginning"
            style={{
              background: "transparent",
              border: "1px solid var(--color-line)",
              color: "var(--color-ink-dim)",
              padding: "0.25rem 0.5rem",
              borderRadius: "4px",
              fontSize: "0.7rem",
              cursor: "pointer",
            }}
          >
            ↺ Reset
          </button>
        </div>

        {/* Right: Metrics & Protocol */}
        <div style={{ display: "flex", alignItems: "center", gap: "0.625rem" }}>
          <div
            style={{
              fontSize: "0.7rem",
              fontFamily: "var(--font-mono)",
              color: "var(--color-ink-dim)",
            }}
          >
            <span style={{ color: "var(--color-ink)" }}>{fmtNum(readingsCount, 0)}</span> readings
          </div>

          {anomaliesCount > 0 && (
            <div
              style={{
                fontSize: "0.68rem",
                fontFamily: "var(--font-mono)",
                background: "rgba(239,68,68,0.15)",
                color: "var(--color-danger)",
                border: "1px solid rgba(239,68,68,0.3)",
                padding: "0.15rem 0.4rem",
                borderRadius: "3px",
                fontWeight: 600,
              }}
            >
              {anomaliesCount} anomalies
            </div>
          )}

          <div
            style={{
              fontSize: "0.62rem",
              fontFamily: "var(--font-mono)",
              color: isConnected ? "var(--color-accent)" : "var(--color-warn)",
              border: "1px solid var(--color-line)",
              padding: "0.15rem 0.35rem",
              borderRadius: "3px",
            }}
          >
            {isConnected ? (mode === "websocket" ? "WS LIVE" : "POLL LIVE") : "DISCONNECTED"}
          </div>

          {/* Toggle Live Drawer */}
          <button
            onClick={() => setExpanded(!expanded)}
            style={{
              background: "transparent",
              border: "none",
              color: "var(--color-accent-3)",
              fontSize: "0.7rem",
              cursor: "pointer",
              padding: "0.2rem 0.4rem",
              textDecoration: "underline",
            }}
          >
            {expanded ? "Hide telemetry feed ▲" : `Live channels (${activeChannels.length}) ▼`}
          </button>
        </div>
      </div>

      {/* Expanded Live Telemetry Drawer */}
      {expanded && (
        <div
          style={{
            borderTop: "1px solid var(--color-line)",
            paddingTop: "0.625rem",
            marginTop: "0.25rem",
          }}
        >
          <div
            style={{
              display: "flex",
              justifyContent: "space-between",
              alignItems: "center",
              marginBottom: "0.5rem",
            }}
          >
            <span
              style={{
                fontSize: "0.65rem",
                fontFamily: "var(--font-mono)",
                color: "var(--color-ink-dim)",
                letterSpacing: "0.08em",
                textTransform: "uppercase",
              }}
            >
              Active Sensor Stream ({activeChannels.length} channels transmitting)
            </span>
            <span
              style={{
                fontSize: "0.62rem",
                color: "var(--color-ink-faint)",
                fontFamily: "var(--font-mono)",
              }}
            >
              Note: Unresolved sensor→space mapping (hardware sensor IDs shown)
            </span>
          </div>

          {/* Active Anomalies Alert Banner */}
          {activeAnomalies.length > 0 && (
            <div
              style={{
                background: "rgba(239,68,68,0.12)",
                border: "1px solid rgba(239,68,68,0.3)",
                borderRadius: "6px",
                padding: "0.4rem 0.75rem",
                marginBottom: "0.5rem",
                display: "flex",
                alignItems: "center",
                gap: "0.5rem",
                fontSize: "0.7rem",
                color: "var(--color-danger)",
              }}
            >
              <span style={{ fontWeight: 700 }}>⚠ {activeAnomalies.length} Active Simulated Anomalies:</span>
              <span style={{ color: "var(--color-ink-dim)" }}>
                {activeAnomalies.map((a) => `${a.measurement_type.toUpperCase()} (${a.value.toFixed(1)} ${a.unit})`).join(", ")}
              </span>
            </div>
          )}

          {/* Live cards grid */}
          <div
            style={{
              display: "grid",
              gridTemplateColumns: "repeat(auto-fill, minmax(180px, 1fr))",
              gap: "0.5rem",
              maxHeight: "220px",
              overflowY: "auto",
              paddingRight: "0.25rem",
            }}
            className="scroll-thin"
          >
            {activeChannels.map((ch) => {
              const isAnomaly = ch.severity === "HIGH" || ch.severity === "CRITICAL";
              return (
                <div
                  key={`${ch.sensor_id}_${ch.measurement_type}`}
                  style={{
                    background: isAnomaly
                      ? "rgba(239,68,68,0.08)"
                      : "rgba(255,255,255,0.02)",
                    border: `1px solid ${
                      isAnomaly ? "rgba(239,68,68,0.4)" : "var(--color-line)"
                    }`,
                    borderRadius: "6px",
                    padding: "0.4rem 0.6rem",
                    display: "flex",
                    flexDirection: "column",
                    gap: "0.2rem",
                  }}
                >
                  <div
                    style={{
                      display: "flex",
                      justifyContent: "space-between",
                      alignItems: "center",
                      fontSize: "0.65rem",
                    }}
                  >
                    <span
                      style={{
                        fontFamily: "var(--font-mono)",
                        color: "var(--color-ink-dim)",
                        textTransform: "uppercase",
                      }}
                    >
                      {ch.measurement_type}
                    </span>
                    {ch.severity && (
                      <span
                        style={{
                          fontSize: "0.58rem",
                          fontWeight: 700,
                          color:
                            ch.severity === "CRITICAL"
                              ? "var(--color-danger)"
                              : ch.severity === "HIGH"
                              ? "#fb923c"
                              : "var(--color-warn)",
                        }}
                      >
                        {ch.severity}
                      </span>
                    )}
                  </div>
                  <div
                    style={{
                      fontSize: "0.95rem",
                      fontWeight: 700,
                      fontFamily: "var(--font-mono)",
                      color: isAnomaly ? "var(--color-danger)" : "var(--color-ink)",
                    }}
                  >
                    {ch.value.toFixed(1)}{" "}
                    <span style={{ fontSize: "0.65rem", fontWeight: 400, color: "var(--color-ink-dim)" }}>
                      {ch.unit}
                    </span>
                  </div>
                  <div
                    style={{
                      display: "flex",
                      justifyContent: "space-between",
                      fontSize: "0.58rem",
                      color: "var(--color-ink-faint)",
                      fontFamily: "var(--font-mono)",
                    }}
                  >
                    <span title={ch.sensor_id}>
                      {ch.sensor_id.length > 10 ? `${ch.sensor_id.slice(0, 10)}…` : ch.sensor_id}
                    </span>
                    {ch.z_score !== null && ch.z_score !== undefined && (
                      <span>z={ch.z_score.toFixed(1)}</span>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}
