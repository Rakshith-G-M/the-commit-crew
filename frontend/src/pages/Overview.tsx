import { Link } from "react-router-dom";
import { useApi } from "../hooks/useApi";
import { api } from "../api";
import { ErrorState, LoadingState } from "../components/common";
import { fmtNum } from "../lib/format";
import {
  recTitle,
  recSensorName,
  recReason,
  translateCategory,
} from "../lib/recPresentation";
import type { Recommendation } from "../api/types";
import { TwinViewer } from "../components/TwinViewer";
import {
  IconArrowRight,
  IconSensor,
  IconAlert,
  IconSparkles,
  IconZap,
} from "../components/icons";

// ── De-duplicate recommendations by title ─────────────────────────
function deduplicateRecs(recs: Recommendation[]): Recommendation[] {
  const seen = new Set<string>();
  const out: Recommendation[] = [];
  for (const r of recs) {
    const title = recTitle(r);
    if (!seen.has(title)) {
      seen.add(title);
      out.push(r);
    }
  }
  return out;
}

// ── Featured Recommendation Spotlight ──────────────────────────────
function FeaturedRecSpotlight({ r }: { r: Recommendation }) {
  const title = recTitle(r);
  const sensor = recSensorName(r);
  const reason = recReason(r);

  return (
    <div
      style={{
        background: "linear-gradient(135deg, rgba(244, 63, 94, 0.12) 0%, rgba(11, 15, 28, 0.8) 100%)",
        border: "1px solid rgba(244, 63, 94, 0.3)",
        borderRadius: "16px",
        padding: "2rem",
        display: "flex",
        flexDirection: "column",
        justifyContent: "space-between",
        position: "relative",
        overflow: "hidden",
      }}
    >
      <div style={{ position: "absolute", top: "-30px", right: "-30px", opacity: 0.08, color: "var(--accent-rose)" }}>
        <IconAlert size={200} />
      </div>

      <div>
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: "1rem" }}>
          <span
            style={{
              padding: "0.35rem 0.85rem",
              borderRadius: "9999px",
              fontSize: "0.75rem",
              fontWeight: 800,
              letterSpacing: "0.06em",
              textTransform: "uppercase",
              background: "rgba(244, 63, 94, 0.2)",
              color: "#fda4af",
              border: "1px solid rgba(244, 63, 94, 0.4)",
            }}
          >
            HIGH PRIORITY
          </span>
          <span style={{ fontSize: "0.85rem", color: "var(--color-ink-muted)", fontWeight: 600 }}>
            {translateCategory(r.recommendation_category)}
          </span>
        </div>

        <h2 style={{ fontSize: "1.7rem", fontWeight: 800, color: "#ffffff", marginBottom: "0.6rem", lineHeight: 1.25, letterSpacing: "-0.02em" }}>
          {title}
        </h2>

        <div style={{ fontSize: "1rem", fontWeight: 700, color: "var(--accent-cyan)", marginBottom: "0.85rem" }}>
          {sensor}
        </div>

        <p style={{ fontSize: "0.95rem", color: "var(--color-ink-2)", lineHeight: 1.65, marginBottom: "1.5rem", maxWidth: "680px" }}>
          {reason}
        </p>
      </div>

      <Link
        to={`/intelligence?rec=${encodeURIComponent(r.recommendation_id)}`}
        className="btn-primary"
        style={{
          alignSelf: "flex-start",
          background: "linear-gradient(135deg, #f43f5e 0%, #e11d48 100%)",
          boxShadow: "0 4px 20px rgba(244, 63, 94, 0.45)",
          padding: "0.8rem 1.6rem",
          fontSize: "0.875rem",
        }}
      >
        VIEW RECOMMENDATION <IconArrowRight size={18} />
      </Link>
    </div>
  );
}

// ── Compact Secondary Recommendation Item ────────────────────────────
function CompactRecItem({ r }: { r: Recommendation }) {
  const title = recTitle(r);
  const sensor = recSensorName(r);

  return (
    <Link
      to={`/intelligence?rec=${encodeURIComponent(r.recommendation_id)}`}
      style={{
        textDecoration: "none",
        display: "flex",
        alignItems: "center",
        justifyContent: "space-between",
        padding: "1.25rem 1.5rem",
        background: "rgba(11, 15, 28, 0.4)",
        border: "1px solid var(--color-line)",
        borderRadius: "12px",
        transition: "all 0.2s ease",
      }}
      className="open-surface-hover"
    >
      <div>
        <div style={{ display: "flex", alignItems: "center", gap: "0.6rem", marginBottom: "0.35rem" }}>
          <span style={{ fontSize: "0.75rem", fontWeight: 800, color: "var(--accent-amber)", textTransform: "uppercase" }}>
            {r.priority}
          </span>
          <span style={{ fontSize: "0.8rem", color: "var(--color-ink-dim)" }}>
            {translateCategory(r.recommendation_category)}
          </span>
        </div>
        <div style={{ fontSize: "1.05rem", fontWeight: 700, color: "var(--color-ink)" }}>{title}</div>
        <div style={{ fontSize: "0.875rem", color: "var(--color-ink-muted)", marginTop: "3px" }}>{sensor}</div>
      </div>
      <IconArrowRight size={18} color="var(--accent-cyan)" />
    </Link>
  );
}

// ── Main Cinematic Overview Page ─────────────────────────────────────
export function OverviewPage() {
  const { state, reload } = useApi(() => api.dashboard(), []);
  const { state: recs } = useApi(() => api.recommendations({ limit: 8 }), []);

  if (state.status === "LOADING") return <LoadingState label="Initializing CampusIQ Operational Space..." />;
  if (state.status === "ERROR") return <ErrorState error={state.error} onRetry={reload} />;
  if (state.status === "EMPTY") return null;

  const d = state.data;
  const topRecs = recs.status === "READY" ? deduplicateRecs(recs.data.items) : [];
  const totalRecCount = recs.status === "READY" ? recs.data.total : 0;
  const featuredRec = topRecs.length > 0 ? topRecs[0] : null;
  const secondaryRecs = topRecs.length > 1 ? topRecs.slice(1, 3) : [];

  const critCount = d.anomalies.by_severity?.CRITICAL ?? 0;
  const highCount = d.anomalies.by_severity?.HIGH ?? 0;
  const envCount = (d.anomalies.by_severity?.MEDIUM ?? 0) + (d.anomalies.by_severity?.LOW ?? 0);
  const degradedSensors = d.sensor_health.degraded ?? 0;

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "3.5rem", maxWidth: "1440px", margin: "0 auto", paddingBottom: "3rem" }} className="fade-in">
      {/* ── 1. CINEMATIC HERO SECTION ─────────────────────────────────── */}
      <div style={{ display: "grid", gridTemplateColumns: "1.1fr 1.3fr", gap: "3rem", alignItems: "center", minHeight: "380px" }}>
        {/* Left Hero Narrative */}
        <div>
          <div style={{ display: "inline-flex", alignItems: "center", gap: "0.5rem", fontSize: "0.78rem", fontWeight: 800, color: "var(--accent-cyan)", letterSpacing: "0.08em", textTransform: "uppercase", marginBottom: "1.25rem" }}>
            <IconSparkles size={16} /> CAMPUS OPERATIONAL INTELLIGENCE
          </div>

          <h1 style={{ fontSize: "3.2rem", fontWeight: 900, lineHeight: 1.05, color: "#ffffff", letterSpacing: "-0.04em", marginBottom: "1.25rem" }}>
            SMART CAMPUS<br />
            <span style={{ color: "var(--accent-blue)" }}>OPERATIONS</span>
          </h1>

          <p style={{ fontSize: "1.1rem", color: "var(--color-ink-muted)", lineHeight: 1.6, marginBottom: "2rem", maxWidth: "520px" }}>
            Understand campus conditions, detect real-time anomalies, and optimize operational resource decisions from one spatial view.
          </p>

          <div style={{ display: "flex", alignItems: "center", gap: "1.5rem" }}>
            <Link to="/twin" className="btn-primary">
              EXPLORE DIGITAL TWIN <IconArrowRight size={18} />
            </Link>

            <div style={{ fontSize: "0.9rem", color: "var(--color-ink-muted)", fontWeight: 600 }}>
              TalTech DS3 · <span style={{ color: "var(--color-ink-dim)" }}>Ehituse Mäemaja</span>
            </div>
          </div>
        </div>

        {/* Right floating spatial 3D Digital Twin Viewer */}
        <div
          style={{
            height: "360px",
            borderRadius: "20px",
            overflow: "hidden",
            border: "1px solid var(--color-line-bright)",
            boxShadow: "0 20px 50px rgba(0, 0, 0, 0.5), 0 0 30px rgba(34, 211, 238, 0.15)",
            position: "relative",
            background: "#050711",
          }}
        >
          <TwinViewer />
          <div
            style={{
              position: "absolute",
              bottom: "15px",
              right: "15px",
              padding: "0.4rem 0.85rem",
              background: "rgba(5, 7, 17, 0.85)",
              backdropFilter: "blur(12px)",
              border: "1px solid var(--color-line-bright)",
              borderRadius: "8px",
              fontSize: "0.78rem",
              fontWeight: 700,
              color: "var(--accent-cyan)",
              letterSpacing: "0.04em",
              pointerEvents: "none",
            }}
          >
            REAL IFC MODEL PREVIEW
          </div>
        </div>
      </div>

      {/* ── 2. ELEGANT HORIZONTAL TELEMETRY STRIP ───────────────────── */}
      <div
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          padding: "1.75rem 2.5rem",
          background: "rgba(11, 15, 28, 0.5)",
          backdropFilter: "blur(16px)",
          border: "1px solid var(--color-line)",
          borderRadius: "16px",
        }}
      >
        <div style={{ textAlign: "center" }}>
          <div style={{ fontSize: "2.2rem", fontWeight: 900, color: "#ffffff", lineHeight: 1 }}>
            {fmtNum(d.campus.space_count ?? 115, 0)}
          </div>
          <div style={{ fontSize: "0.78rem", fontWeight: 800, color: "var(--accent-blue)", letterSpacing: "0.06em", textTransform: "uppercase", marginTop: "6px" }}>
            SPACES
          </div>
        </div>

        <div style={{ width: "1px", height: "36px", background: "var(--color-line)" }} />

        <div style={{ textAlign: "center" }}>
          <div style={{ fontSize: "2.2rem", fontWeight: 900, color: "#ffffff", lineHeight: 1 }}>
            {fmtNum(d.campus.storey_count ?? 5, 0)}
          </div>
          <div style={{ fontSize: "0.78rem", fontWeight: 800, color: "var(--accent-cyan)", letterSpacing: "0.06em", textTransform: "uppercase", marginTop: "6px" }}>
            STOREYS
          </div>
        </div>

        <div style={{ width: "1px", height: "36px", background: "var(--color-line)" }} />

        <div style={{ textAlign: "center" }}>
          <div style={{ fontSize: "2.2rem", fontWeight: 900, color: "#ffffff", lineHeight: 1 }}>
            {fmtNum(d.telemetry.sensor_count ?? 36, 0)}
          </div>
          <div style={{ fontSize: "0.78rem", fontWeight: 800, color: "var(--accent-violet)", letterSpacing: "0.06em", textTransform: "uppercase", marginTop: "6px" }}>
            SENSORS
          </div>
        </div>

        <div style={{ width: "1px", height: "36px", background: "var(--color-line)" }} />

        <div style={{ textAlign: "center" }}>
          <div style={{ fontSize: "2.2rem", fontWeight: 900, color: "#ffffff", lineHeight: 1 }}>
            {fmtNum(d.telemetry.channel_count ?? 69, 0)}
          </div>
          <div style={{ fontSize: "0.78rem", fontWeight: 800, color: "var(--accent-emerald)", letterSpacing: "0.06em", textTransform: "uppercase", marginTop: "6px" }}>
            CHANNELS
          </div>
        </div>

        <div style={{ width: "1px", height: "36px", background: "var(--color-line)" }} />

        <div style={{ textAlign: "center" }}>
          <div style={{ fontSize: "2.2rem", fontWeight: 900, color: "#ffffff", lineHeight: 1 }}>
            {( (d.telemetry.total_readings ?? 1390297) / 1000000 ).toFixed(2)}M
          </div>
          <div style={{ fontSize: "0.78rem", fontWeight: 800, color: "var(--accent-amber)", letterSpacing: "0.06em", textTransform: "uppercase", marginTop: "6px" }}>
            READINGS
          </div>
        </div>

        <div style={{ width: "1px", height: "36px", background: "var(--color-line)" }} />

        <div style={{ textAlign: "center" }}>
          <div style={{ fontSize: "2.2rem", fontWeight: 900, color: "#ffffff", lineHeight: 1 }}>
            {fmtNum(d.recommendations.total ?? 98, 0)}
          </div>
          <div style={{ fontSize: "0.78rem", fontWeight: 800, color: "var(--accent-rose)", letterSpacing: "0.06em", textTransform: "uppercase", marginTop: "6px" }}>
            ACTIONS
          </div>
        </div>
      </div>

      {/* ── 3. CAMPUS PULSE DATA SECTION ───────────────────────────── */}
      <div>
        <div style={{ marginBottom: "1.5rem" }}>
          <div style={{ fontSize: "0.78rem", fontWeight: 800, color: "var(--accent-cyan)", letterSpacing: "0.06em", textTransform: "uppercase" }}>
            REAL-TIME DATA STREAMS
          </div>
          <h2 style={{ fontSize: "1.8rem", fontWeight: 800, color: "#ffffff", letterSpacing: "-0.02em", margin: "0.25rem 0" }}>
            CAMPUS PULSE
          </h2>
        </div>

        <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: "2rem" }}>
          {/* Environment */}
          <div style={{ padding: "1.5rem", borderLeft: "3px solid var(--accent-cyan)", background: "rgba(11, 15, 28, 0.3)", borderRadius: "0 12px 12px 0" }}>
            <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: "0.75rem" }}>
              <span style={{ fontSize: "0.9rem", fontWeight: 800, color: "#ffffff", textTransform: "uppercase", letterSpacing: "0.04em" }}>
                ENVIRONMENT
              </span>
              <span className="live-dot" />
            </div>
            <div style={{ fontSize: "1.8rem", fontWeight: 900, color: "var(--accent-cyan)", marginBottom: "0.3rem" }}>
              {fmtNum(envCount, 0)} Signals
            </div>
            <p style={{ fontSize: "0.9rem", color: "var(--color-ink-muted)", lineHeight: 1.55 }}>
              CO₂ elevation, temperature shifts, and humidity telemetry across floor spaces.
            </p>
          </div>

          {/* Energy */}
          <div style={{ padding: "1.5rem", borderLeft: "3px solid var(--accent-amber)", background: "rgba(11, 15, 28, 0.3)", borderRadius: "0 12px 12px 0" }}>
            <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: "0.75rem" }}>
              <span style={{ fontSize: "0.9rem", fontWeight: 800, color: "#ffffff", textTransform: "uppercase", letterSpacing: "0.04em" }}>
                POWER & ENERGY
              </span>
              <IconZap size={16} color="var(--accent-amber)" />
            </div>
            <div style={{ fontSize: "1.8rem", fontWeight: 900, color: "var(--accent-amber)", marginBottom: "0.3rem" }}>
              Active Metering
            </div>
            <p style={{ fontSize: "0.9rem", color: "var(--color-ink-muted)", lineHeight: 1.55 }}>
              Building power consumption baselines and electrical distribution monitoring.
            </p>
          </div>

          {/* Sensor Health */}
          <div style={{ padding: "1.5rem", borderLeft: "3px solid var(--accent-violet)", background: "rgba(11, 15, 28, 0.3)", borderRadius: "0 12px 12px 0" }}>
            <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: "0.75rem" }}>
              <span style={{ fontSize: "0.9rem", fontWeight: 800, color: "#ffffff", textTransform: "uppercase", letterSpacing: "0.04em" }}>
                SENSOR HEALTH
              </span>
              <IconSensor size={16} color="var(--accent-violet)" />
            </div>
            <div style={{ fontSize: "1.8rem", fontWeight: 900, color: "var(--accent-violet)", marginBottom: "0.3rem" }}>
              {fmtNum(degradedSensors, 0)} Degraded
            </div>
            <p style={{ fontSize: "0.9rem", color: "var(--color-ink-muted)", lineHeight: 1.55 }}>
              Stream continuity check, constant reading detection, and sampling gaps.
            </p>
          </div>
        </div>
      </div>

      {/* ── 4. FLOWING INTELLIGENCE PIPELINE SYSTEM ─────────────────── */}
      <div style={{ padding: "2rem 2.5rem", background: "rgba(11, 15, 28, 0.5)", border: "1px solid var(--color-line)", borderRadius: "16px" }}>
        <div style={{ fontSize: "0.78rem", fontWeight: 800, color: "var(--accent-blue)", letterSpacing: "0.06em", textTransform: "uppercase", marginBottom: "1.5rem" }}>
          INTELLIGENCE PIPELINE FLOW
        </div>

        <div style={{ display: "grid", gridTemplateColumns: "1fr auto 1fr auto 1fr auto 1fr", gap: "1rem", alignItems: "center" }}>
          <div>
            <div style={{ fontSize: "0.95rem", fontWeight: 900, color: "#ffffff", letterSpacing: "0.01em" }}>1. OBSERVE</div>
            <div style={{ fontSize: "0.85rem", color: "var(--color-ink-muted)", marginTop: "3px" }}>Sensor telemetry streams</div>
          </div>

          <div style={{ color: "var(--accent-blue)", fontWeight: 800, fontSize: "1.2rem" }}>→</div>

          <div>
            <div style={{ fontSize: "0.95rem", fontWeight: 900, color: "#ffffff", letterSpacing: "0.01em" }}>2. DETECT</div>
            <div style={{ fontSize: "0.85rem", color: "var(--color-ink-muted)", marginTop: "3px" }}>Anomalies & deviations</div>
          </div>

          <div style={{ color: "var(--accent-cyan)", fontWeight: 800, fontSize: "1.2rem" }}>→</div>

          <div>
            <div style={{ fontSize: "0.95rem", fontWeight: 900, color: "#ffffff", letterSpacing: "0.01em" }}>3. UNDERSTAND</div>
            <div style={{ fontSize: "0.85rem", color: "var(--color-ink-muted)", marginTop: "3px" }}>Historical baselines</div>
          </div>

          <div style={{ color: "var(--accent-violet)", fontWeight: 800, fontSize: "1.2rem" }}>→</div>

          <div>
            <div style={{ fontSize: "0.95rem", fontWeight: 900, color: "#ffffff", letterSpacing: "0.01em" }}>4. RECOMMEND</div>
            <div style={{ fontSize: "0.85rem", color: "var(--color-ink-muted)", marginTop: "3px" }}>Operational maintenance</div>
          </div>
        </div>
      </div>

      {/* ── 5. EDITORIAL WHAT NEEDS ATTENTION ───────────────────────── */}
      <div>
        <div style={{ display: "flex", alignItems: "baseline", justifyContent: "space-between", marginBottom: "1.5rem" }}>
          <div>
            <div style={{ fontSize: "0.78rem", fontWeight: 800, color: "var(--accent-rose)", letterSpacing: "0.06em", textTransform: "uppercase" }}>
              OPERATIONAL SIGNALS
            </div>
            <h2 style={{ fontSize: "1.8rem", fontWeight: 800, color: "#ffffff", letterSpacing: "-0.02em", margin: "0.25rem 0" }}>
              WHAT NEEDS ATTENTION
            </h2>
          </div>
          <Link to="/intelligence" style={{ fontSize: "0.9rem", fontWeight: 700, color: "var(--accent-blue)", textDecoration: "none" }}>
            Open Intelligence Workspace →
          </Link>
        </div>

        <div style={{ display: "grid", gridTemplateColumns: "1fr 1.5fr", gap: "2.5rem", alignItems: "center" }}>
          {/* Critical Number Focus */}
          <div>
            <div style={{ fontSize: "4.5rem", fontWeight: 900, color: "var(--accent-rose)", lineHeight: 0.95, letterSpacing: "-0.04em" }}>
              {fmtNum(critCount, 0)}
            </div>
            <div style={{ fontSize: "1.05rem", fontWeight: 800, color: "#ffffff", letterSpacing: "0.04em", textTransform: "uppercase", margin: "0.5rem 0 0.85rem" }}>
              CRITICAL SIGNALS
            </div>
            <p style={{ fontSize: "0.95rem", color: "var(--color-ink-muted)", lineHeight: 1.6 }}>
              Telemetry anomalies needing immediate review across climate and energy channels.
            </p>
          </div>

          {/* Typography Breakdown Bar & Metrics */}
          <div style={{ display: "flex", flexDirection: "column", gap: "1.25rem" }}>
            <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", fontSize: "0.95rem", fontWeight: 700 }}>
              <span style={{ color: "var(--accent-rose)" }}>Critical: {fmtNum(critCount, 0)}</span>
              <span style={{ color: "var(--accent-amber)" }}>High: {fmtNum(highCount, 0)}</span>
              <span style={{ color: "var(--accent-cyan)" }}>Environmental: {fmtNum(envCount, 0)}</span>
              <span style={{ color: "var(--accent-violet)" }}>Sensor Health: {fmtNum(degradedSensors, 0)}</span>
            </div>

            {/* Continuous Multi-Color Bar */}
            <div style={{ width: "100%", height: "8px", borderRadius: "4px", background: "rgba(255, 255, 255, 0.05)", display: "flex", overflow: "hidden" }}>
              <div style={{ width: "25%", background: "var(--accent-rose)" }} />
              <div style={{ width: "25%", background: "var(--accent-amber)" }} />
              <div style={{ width: "35%", background: "var(--accent-cyan)" }} />
              <div style={{ width: "15%", background: "var(--accent-violet)" }} />
            </div>
          </div>
        </div>
      </div>

      {/* ── 6. FEATURED RECOMMENDATION — REDUCED REPETITION ──────────── */}
      <div>
        <div style={{ display: "flex", alignItems: "baseline", justifyContent: "space-between", marginBottom: "1rem" }}>
          <div style={{ fontSize: "0.78rem", fontWeight: 800, color: "var(--accent-rose)", letterSpacing: "0.06em", textTransform: "uppercase" }}>
            FEATURED ACTION
          </div>
          {totalRecCount > 0 && (
            <Link to="/intelligence?tab=recommendations" style={{ fontSize: "0.9rem", fontWeight: 700, color: "var(--accent-blue)", textDecoration: "none" }}>
              View all {totalRecCount} recommendations →
            </Link>
          )}
        </div>

        {recs.status === "READY" && (
          <div style={{ display: "flex", flexDirection: "column", gap: "1.5rem" }}>
            {featuredRec && <FeaturedRecSpotlight r={featuredRec} />}

            {secondaryRecs.length > 0 && (
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "1.25rem", marginTop: "0.5rem" }}>
                {secondaryRecs.map((r) => (
                  <CompactRecItem key={r.recommendation_id} r={r} />
                ))}
              </div>
            )}
          </div>
        )}
      </div>

      {/* ── 7. DIGITAL TWIN SPATIAL SECTION ─────────────────────────── */}
      <div style={{ padding: "2.5rem", background: "rgba(11, 15, 28, 0.5)", border: "1px solid var(--color-line)", borderRadius: "20px" }}>
        <div style={{ display: "flex", alignItems: "baseline", justifyContent: "space-between", marginBottom: "1.5rem" }}>
          <div>
            <div style={{ fontSize: "0.78rem", fontWeight: 800, color: "var(--accent-cyan)", letterSpacing: "0.06em", textTransform: "uppercase" }}>
              SPATIAL BIM GEOMETRY
            </div>
            <h2 style={{ fontSize: "1.8rem", fontWeight: 800, color: "#ffffff", letterSpacing: "-0.02em", margin: "0.25rem 0" }}>
              THE CAMPUS, IN 3D
            </h2>
            <div style={{ fontSize: "0.9rem", color: "var(--color-ink-muted)" }}>
              TalTech DS3 · 115 spaces · 5 storeys
            </div>
          </div>

          <Link to="/twin" className="btn-primary">
            OPEN DIGITAL TWIN <IconArrowRight size={18} />
          </Link>
        </div>

        <div style={{ height: "450px", borderRadius: "16px", overflow: "hidden", border: "1px solid var(--color-line-bright)" }}>
          <TwinViewer />
        </div>
      </div>
    </div>
  );
}
