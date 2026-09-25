import { useState } from "react";
import { useSearchParams } from "react-router-dom";
import { useApi } from "../hooks/useApi";
import { api } from "../api";
import {
  EmptyState,
  ErrorState,
  LoadingState,
  Pager,
} from "../components/common";
import { fmtDateTime, fmtNum, resolveSpaceDisplayName } from "../lib/format";
import {
  getSensorDisplayName,
  formatIssueName,
  formatLocation,
  getSensorRecommendation,
} from "../lib/sensorsData";
import {
  recTitle,
  recSensorName,
  recReason,
  translateCategory,
  translateProblemType,
} from "../lib/recPresentation";
import { RecDetail } from "./RecDetail";

const PAGE = 12;

// ── Shared table wrapper ──────────────────────────────────────────
function TableWrap({ children }: { children: React.ReactNode }) {
  return (
    <div style={{ overflowX: "auto" }}>
      <table className="data-table">{children}</table>
    </div>
  );
}

// ── Severity label → human readable ──────────────────────────────
function sevLabel(k: string | null): string {
  if (k === "CRITICAL") return "Critical";
  if (k === "HIGH") return "High";
  if (k === "MEDIUM") return "Medium";
  if (k === "LOW") return "Low";
  return "All";
}

// ── Anomalies Tab ─────────────────────────────────────────────────
export function AnomaliesTab() {
  const [offset, setOffset] = useState(0);
  const [sev, setSev] = useState<string | null>(null);

  const { state } = useApi(
    () => api.anomalies({ limit: PAGE, offset, severity: sev ?? undefined }),
    [offset, sev],
  );

  if (state.status === "LOADING") return <LoadingState />;
  if (state.status === "ERROR") return <ErrorState error={state.error} />;
  if (state.status === "EMPTY")
    return <EmptyState message="No anomaly events recorded in this dataset." />;

  const data = state.data;

  return (
    <div>
      {/* Severity filter — human-readable labels */}
      <div style={{ display: "flex", gap: "0.4rem", marginBottom: "1.25rem", flexWrap: "wrap", alignItems: "center" }}>
        {([null, "CRITICAL", "HIGH", "MEDIUM", "LOW"] as (string | null)[]).map(k => (
          <button
            key={k ?? "all"}
            onClick={() => { setSev(k); setOffset(0); }}
            style={{
              padding: "0.35rem 0.85rem",
              borderRadius: "20px",
              fontSize: "0.82rem",
              fontWeight: 600,
              cursor: "pointer",
              border: `1px solid ${sev === k ? "rgba(56,189,248,0.4)" : "var(--color-line)"}`,
              background: sev === k ? "rgba(56,189,248,0.1)" : "var(--color-panel-2)",
              color: sev === k ? "var(--accent-blue)" : "var(--color-ink-muted)",
              transition: "all 150ms",
            }}
          >
            {sevLabel(k)}
          </button>
        ))}
        <span style={{ marginLeft: "auto", fontSize: "0.82rem", color: "var(--color-ink-dim)", alignSelf: "center" }}>
          {fmtNum(data.total, 0)} total events
        </span>
      </div>

      <TableWrap>
        <thead>
          <tr>
            {["Sensor", "Measurement", "Observed", "Baseline", "Deviation", "Severity"].map(h => (
              <th key={h}>{h}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {data.items.map(a => (
            <tr key={`${a.sensor_id}-${a.timestamp}`}>
              <td>
                <div style={{ fontWeight: 700, color: "var(--color-ink)", fontSize: "0.9rem" }}>
                  {getSensorDisplayName(a.sensor_id, a.measurement_type)}
                </div>
                <div style={{ fontSize: "0.78rem", color: "var(--color-ink-dim)", marginTop: "0.15rem" }}>
                  {fmtDateTime(a.timestamp)}
                </div>
              </td>
              <td style={{ color: "var(--color-ink-2)", fontSize: "0.88rem" }}>
                {a.measurement_type?.replace(/_/g, " ").replace(/\b\w/g, c => c.toUpperCase())}
              </td>
              <td>
                <span style={{ fontFamily: "var(--font-mono)", fontWeight: 600, fontSize: "0.9rem" }}>
                  {a.value !== null ? fmtNum(a.value, 1) : "—"}
                  {a.unit && <span style={{ color: "var(--color-ink-dim)", fontWeight: 400 }}> {a.unit}</span>}
                </span>
              </td>
              <td>
                <span style={{ fontFamily: "var(--font-mono)", color: "var(--color-ink-dim)", fontSize: "0.88rem" }}>
                  {a.expected !== null ? fmtNum(a.expected, 1) : "—"}
                </span>
              </td>
              <td>
                <span style={{ fontFamily: "var(--font-mono)", fontSize: "0.88rem" }}>
                  {a.deviation !== null ? `${fmtNum(a.deviation, 1)}%` : "—"}
                </span>
              </td>
              <td>
                <span style={{
                  padding: "0.2rem 0.55rem",
                  borderRadius: "20px",
                  fontSize: "0.75rem",
                  fontWeight: 700,
                  background: a.severity === "CRITICAL" ? "rgba(248,113,113,0.1)"
                    : a.severity === "HIGH" ? "rgba(251,146,60,0.1)"
                    : a.severity === "MEDIUM" ? "rgba(251,191,36,0.1)"
                    : "rgba(52,211,153,0.1)",
                  color: a.severity === "CRITICAL" ? "var(--color-danger)"
                    : a.severity === "HIGH" ? "#fb923c"
                    : a.severity === "MEDIUM" ? "var(--color-warn)"
                    : "var(--color-ok)",
                }}>
                  {sevLabel(a.severity ?? null)}
                </span>
              </td>
            </tr>
          ))}
        </tbody>
      </TableWrap>
      <Pager total={data.total} limit={data.limit} offset={data.offset} onChange={setOffset} />
    </div>
  );
}

// ── Forecasts Tab ─────────────────────────────────────────────────
export function ForecastsTab() {
  const [offset, setOffset] = useState(0);
  const { state } = useApi(() => api.forecasts({ limit: PAGE, offset }), [offset]);

  if (state.status === "LOADING") return <LoadingState />;
  if (state.status === "ERROR") return <ErrorState error={state.error} />;
  if (state.status === "EMPTY")
    return <EmptyState message="No forecasts available for this data release." />;

  const data = state.data;

  return (
    <div>
      <div style={{ marginBottom: "1rem", fontSize: "0.85rem", color: "var(--color-ink-dim)" }}>
        {fmtNum(data.total, 0)} forecast channels available · values are model predictions, not confirmed future readings.
      </div>
      <TableWrap>
        <thead>
          <tr>
            {["Sensor", "Measurement", "Predicted", "Baseline", "Forecast horizon", "Confidence"].map(h => (
              <th key={h}>{h}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {data.items.map(f => (
            <tr key={`${f.sensor_id}-${f.horizon_hours}`}>
              <td>
                <span style={{ fontWeight: 700, color: "var(--color-ink)", fontSize: "0.9rem" }}>
                  {getSensorDisplayName(f.sensor_id, f.measurement_type)}
                </span>
              </td>
              <td style={{ color: "var(--color-ink-2)", fontSize: "0.88rem" }}>
                {f.measurement_type?.replace(/_/g, " ").replace(/\b\w/g, c => c.toUpperCase())}
              </td>
              <td>
                <span style={{ fontFamily: "var(--font-mono)", fontWeight: 600, fontSize: "0.9rem" }}>
                  {f.predicted_value !== null ? fmtNum(f.predicted_value, 1) : "—"}
                  {f.unit && <span style={{ color: "var(--color-ink-dim)", fontWeight: 400 }}> {f.unit}</span>}
                </span>
              </td>
              <td>
                <span style={{ fontFamily: "var(--font-mono)", color: "var(--color-ink-dim)", fontSize: "0.88rem" }}>
                  {f.baseline_value !== null ? fmtNum(f.baseline_value, 1) : "—"}
                </span>
              </td>
              <td>
                <span style={{ fontFamily: "var(--font-mono)", fontSize: "0.88rem" }}>
                  {f.horizon_hours}h
                </span>
              </td>
              <td>
                <span style={{
                  padding: "0.2rem 0.55rem",
                  borderRadius: "20px",
                  fontSize: "0.75rem",
                  fontWeight: 600,
                  background: f.coverage?.confidence_intervals_calculated ? "rgba(52,211,153,0.1)" : "rgba(148,163,184,0.08)",
                  color: f.coverage?.confidence_intervals_calculated ? "var(--color-ok)" : "var(--color-ink-dim)",
                }}>
                  {f.coverage?.confidence_intervals_calculated ? "95% CI" : "Historical baseline"}
                </span>
              </td>
            </tr>
          ))}
        </tbody>
      </TableWrap>
      <Pager total={data.total} limit={data.limit} offset={data.offset} onChange={setOffset} />
    </div>
  );
}

// ── Decision Candidates Tab (renamed "Decision Log") ──────────────
export function CandidatesTab() {
  const [offset, setOffset] = useState(0);
  const { state } = useApi(() => api.decisionCandidates({ limit: PAGE, offset }), [offset]);

  if (state.status === "LOADING") return <LoadingState />;
  if (state.status === "ERROR") return <ErrorState error={state.error} />;
  if (state.status === "EMPTY") return <EmptyState message="No decision candidates." />;

  const data = state.data;

  return (
    <div>
      <div style={{ marginBottom: "1rem", fontSize: "0.85rem", color: "var(--color-ink-dim)" }}>
        {fmtNum(data.total, 0)} action candidates evaluated from telemetry data.
      </div>
      <TableWrap>
        <thead>
          <tr>
            {["Category", "Issue type", "Monitored source", "Proposed action", "Severity"].map(h => (
              <th key={h}>{h}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {data.items.map(c => (
            <tr key={c.candidate_id}>
              <td>
                <span style={{ fontSize: "0.88rem", fontWeight: 600, color: "var(--color-ink)" }}>
                  {translateCategory(c.candidate_type)}
                </span>
              </td>
              <td style={{ color: "var(--color-ink-2)", fontSize: "0.88rem" }}>
                {translateProblemType(c.problem_type)}
              </td>
              <td>
                <span style={{ fontSize: "0.88rem", color: "var(--color-ink-muted)" }}>
                  {c.affected_entity.space_id
                    ? resolveSpaceDisplayName(c.affected_entity.space_id)
                    : getSensorDisplayName(c.affected_entity.sensor_id)}
                </span>
              </td>
              <td style={{ maxWidth: "300px" }}>
                <span style={{ fontSize: "0.88rem", display: "block", color: "var(--color-ink)", lineHeight: 1.5 }}>
                  {/* Strip UUIDs from proposed_action */}
                  {(c.proposed_action ?? "").replace(
                    /[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}/gi,
                    "this sensor"
                  ).replace(/\(issues?:[^)]*\)/gi, "").trim()}
                </span>
              </td>
              <td>
                <span style={{
                  padding: "0.2rem 0.55rem",
                  borderRadius: "20px",
                  fontSize: "0.75rem",
                  fontWeight: 700,
                  background: c.severity === "CRITICAL" ? "rgba(248,113,113,0.1)"
                    : c.severity === "HIGH" ? "rgba(251,146,60,0.1)"
                    : "rgba(251,191,36,0.1)",
                  color: c.severity === "CRITICAL" ? "var(--color-danger)"
                    : c.severity === "HIGH" ? "#fb923c"
                    : "var(--color-warn)",
                }}>
                  {sevLabel(c.severity)}
                </span>
              </td>
            </tr>
          ))}
        </tbody>
      </TableWrap>
      <Pager total={data.total} limit={data.limit} offset={data.offset} onChange={setOffset} />
    </div>
  );
}

// ── Sensor Health Tab ─────────────────────────────────────────────
export function HealthTab() {
  const [offset, setOffset] = useState(0);
  const { state } = useApi(() => api.health({ limit: 50 }), []);

  if (state.status === "LOADING") return <LoadingState />;
  if (state.status === "ERROR") return <ErrorState error={state.error} />;
  if (state.status === "EMPTY") return <EmptyState message="No sensor health records." />;

  const data = state.data;
  const s = data.summary;
  const degradedItems = data.items.filter(h => h.health_status === "DEGRADED");
  const healthyItems = data.items.filter(h => h.health_status !== "DEGRADED");
  const degradedCount = (s?.degraded as number) ?? degradedItems.length;
  const healthyCount = (s?.healthy as number) ?? healthyItems.length;
  const totalCount = (s?.devices as number) ?? degradedCount + healthyCount;

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "1.5rem" }}>
      {/* Accurate summary header */}
      <div style={{
        display: "flex",
        alignItems: "center",
        justifyContent: "space-between",
        padding: "1rem 1.25rem",
        background: "var(--color-panel-2)",
        borderRadius: "10px",
        border: "1px solid var(--color-line)",
      }}>
        <div>
          <div style={{ fontSize: "1.1rem", fontWeight: 800, color: "#ffffff", letterSpacing: "-0.01em" }}>
            Sensor Health
          </div>
          <div style={{ fontSize: "0.85rem", color: "var(--color-ink-muted)", marginTop: "0.2rem" }}>
            {totalCount} monitored
          </div>
        </div>
        <div style={{ display: "flex", gap: "1.5rem", alignItems: "center" }}>
          <div style={{ textAlign: "center" }}>
            <div style={{ fontSize: "1.5rem", fontWeight: 800, color: degradedCount > 0 ? "var(--color-warn)" : "var(--color-ink-dim)" }}>
              {degradedCount}
            </div>
            <div style={{ fontSize: "0.78rem", color: "var(--color-ink-dim)", fontWeight: 600 }}>degraded</div>
          </div>
          <div style={{ width: "1px", height: "28px", background: "var(--color-line)" }} />
          <div style={{ textAlign: "center" }}>
            <div style={{ fontSize: "1.5rem", fontWeight: 800, color: healthyCount > 0 ? "var(--color-ok)" : "var(--color-ink-dim)" }}>
              {healthyCount}
            </div>
            <div style={{ fontSize: "0.78rem", color: "var(--color-ink-dim)", fontWeight: 600 }}>healthy</div>
          </div>
        </div>
      </div>

      {/* Degraded sensor cards */}
      {degradedItems.length > 0 && (
        <div>
          <div style={{ fontSize: "0.9rem", fontWeight: 700, color: "var(--color-ink)", marginBottom: "0.85rem" }}>
            Sensors requiring maintenance
            <span style={{ marginLeft: "0.5rem", fontSize: "0.8rem", color: "var(--color-ink-dim)", fontWeight: 500 }}>
              ({degradedItems.length})
            </span>
          </div>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(300px, 1fr))", gap: "0.85rem" }}>
            {degradedItems.slice(offset, offset + PAGE).map(h => (
              <div key={h.sensor_id} style={{
                background: "var(--color-panel-2)",
                border: "1px solid rgba(251,191,36,0.15)",
                borderRadius: "12px",
                padding: "1.15rem",
                display: "flex",
                flexDirection: "column",
                gap: "0.75rem",
              }}>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
                  <div>
                    <div style={{ fontSize: "0.95rem", fontWeight: 700, color: "var(--color-ink)" }}>
                      {getSensorDisplayName(h.sensor_id)}
                    </div>
                    <div style={{ fontSize: "0.8rem", color: "var(--color-ink-dim)", marginTop: "0.15rem" }}>
                      Sensor reliability issue
                    </div>
                  </div>
                  <span style={{
                    padding: "0.2rem 0.55rem",
                    borderRadius: "20px",
                    fontSize: "0.72rem",
                    fontWeight: 700,
                    background: "rgba(251,191,36,0.1)",
                    border: "1px solid rgba(251,191,36,0.2)",
                    color: "var(--color-warn)",
                  }}>
                    Degraded
                  </span>
                </div>

                <div>
                  <div style={{ fontSize: "0.78rem", fontWeight: 600, color: "var(--color-ink-dim)", marginBottom: "0.3rem", textTransform: "uppercase", letterSpacing: "0.03em" }}>
                    {h.issues.length} detected issue{h.issues.length !== 1 ? "s" : ""}
                  </div>
                  {h.issues.length > 0 ? (
                    <ul style={{ margin: 0, paddingLeft: "1.2rem", lineHeight: 1.65 }}>
                      {h.issues.map(i => (
                        <li key={i.type} style={{ fontSize: "0.88rem", color: "var(--color-ink-2)" }}>{formatIssueName(i.type)}</li>
                      ))}
                    </ul>
                  ) : (
                    <div style={{ fontSize: "0.88rem", color: "var(--color-ink-dim)" }}>Sampling gap identified</div>
                  )}
                </div>

                <div style={{
                  fontSize: "0.85rem",
                  color: "var(--color-ink-2)",
                  background: "rgba(56,189,248,0.06)",
                  border: "1px solid rgba(56,189,248,0.12)",
                  padding: "0.55rem 0.75rem",
                  borderRadius: "8px",
                  lineHeight: 1.55,
                }}>
                  <strong style={{ color: "var(--accent-cyan)" }}>Recommended: </strong>{getSensorRecommendation(h.issues.map(i => i.type), h.health_status)}
                </div>

                <div style={{ fontSize: "0.8rem", color: "var(--color-ink-dim)" }}>
                  {formatLocation("UNKNOWN_LOCATION")}
                </div>

                <details>
                  <summary style={{ cursor: "pointer", fontSize: "0.78rem", fontFamily: "var(--font-mono)", color: "var(--color-ink-dim)" }}>
                    Technical details
                  </summary>
                  <div style={{ fontSize: "0.78rem", fontFamily: "var(--font-mono)", color: "var(--color-ink-dim)", marginTop: "0.4rem", display: "flex", gap: "0.85rem", background: "var(--color-panel)", padding: "0.5rem 0.65rem", borderRadius: "6px" }}>
                    <span>Coverage: {h.coverage_fraction !== null ? `${fmtNum(h.coverage_fraction * 100, 0)}%` : "—"}</span>
                    <span>Valid: {fmtNum(h.valid_readings, 0)}</span>
                    <span>Missing: {fmtNum(h.missing_readings, 0)}</span>
                    <span style={{ color: "var(--color-ink-faint)" }}>ID: {h.sensor_id.slice(0, 8)}…</span>
                  </div>
                </details>
              </div>
            ))}
          </div>
          <Pager total={degradedItems.length} limit={PAGE} offset={offset} onChange={setOffset} />
        </div>
      )}

      {/* Healthy summary — collapsed */}
      {healthyItems.length > 0 && (
        <details>
          <summary style={{ cursor: "pointer", fontSize: "0.85rem", fontWeight: 600, color: "var(--color-ink-muted)", padding: "0.5rem 0" }}>
            View {healthyItems.length} healthy sensor{healthyItems.length !== 1 ? "s" : ""}
          </summary>
          <div style={{ marginTop: "0.5rem" }}>
            <TableWrap>
              <thead>
                <tr>
                  {["Sensor", "Status", "Data coverage", "Valid readings", "Issues"].map(h => <th key={h}>{h}</th>)}
                </tr>
              </thead>
              <tbody>
                {data.items.map(h => (
                  <tr key={h.sensor_id}>
                    <td><span style={{ fontWeight: 700, color: "var(--color-ink)", fontSize: "0.9rem" }}>{getSensorDisplayName(h.sensor_id)}</span></td>
                    <td>
                      <span style={{
                        padding: "0.15rem 0.5rem",
                        borderRadius: "20px",
                        fontSize: "0.72rem",
                        fontWeight: 700,
                        background: h.health_status === "HEALTHY" ? "rgba(52,211,153,0.1)" : "rgba(251,191,36,0.1)",
                        color: h.health_status === "HEALTHY" ? "var(--color-ok)" : "var(--color-warn)",
                      }}>
                        {h.health_status === "HEALTHY" ? "Healthy" : "Degraded"}
                      </span>
                    </td>
                    <td><span style={{ fontFamily: "var(--font-mono)", fontSize: "0.88rem" }}>{h.coverage_fraction !== null ? `${fmtNum(h.coverage_fraction * 100, 0)}%` : "—"}</span></td>
                    <td><span style={{ fontFamily: "var(--font-mono)", fontSize: "0.88rem" }}>{fmtNum(h.valid_readings, 0)}</span></td>
                    <td style={{ color: "var(--color-ink-dim)", fontSize: "0.85rem" }}>
                      {h.issues.length ? h.issues.map(i => formatIssueName(i.type)).join(", ") : "None"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </TableWrap>
          </div>
        </details>
      )}
    </div>
  );
}

// ── Recommendations Tab ───────────────────────────────────────────
export function RecommendationsTab() {
  const [offset, setOffset] = useState(0);
  const [params] = useSearchParams();
  const focused = params.get("rec");
  const { state } = useApi(() => api.recommendations({ limit: PAGE, offset }), [offset]);

  if (focused) return <RecDetail id={focused} />;
  if (state.status === "LOADING") return <LoadingState />;
  if (state.status === "ERROR") return <ErrorState error={state.error} />;
  if (state.status === "EMPTY") return <EmptyState message="No recommendations available." />;

  const data = state.data;

  return (
    <div>
      <div style={{ marginBottom: "1rem", fontSize: "0.85rem", color: "var(--color-ink-dim)" }}>
        {fmtNum(data.total, 0)} recommendations · {data.data_status?.sensor_location_mapping === "RESOLVED" ? "Location verified" : "Sensor-to-room mapping not yet verified for this dataset"} · Updated {fmtDateTime(data.generated_at)}
      </div>

      <div style={{ display: "flex", flexDirection: "column", gap: "0.6rem" }}>
        {data.items.map(r => {
          const accent =
            r.priority === "CRITICAL" ? "var(--color-danger)"
            : r.priority === "HIGH" ? "#fb923c"
            : r.priority === "MEDIUM" ? "var(--color-warn)"
            : "var(--color-ok)";

          const title = recTitle(r);
          const sensor = recSensorName(r);
          const reason = recReason(r);

          return (
            <a
              key={r.recommendation_id}
              href={`/intelligence?rec=${encodeURIComponent(r.recommendation_id)}`}
              style={{ textDecoration: "none" }}
            >
              <div style={{
                display: "flex",
                alignItems: "stretch",
                background: "var(--color-panel-2)",
                border: "1px solid var(--color-line)",
                borderRadius: "10px",
                overflow: "hidden",
                transition: "border-color 200ms, background 200ms",
                cursor: "pointer",
              }}
                onMouseEnter={e => {
                  const el = e.currentTarget as HTMLElement;
                  el.style.borderColor = "rgba(56,189,248,0.25)";
                  el.style.background = "var(--color-panel-3)";
                }}
                onMouseLeave={e => {
                  const el = e.currentTarget as HTMLElement;
                  el.style.borderColor = "var(--color-line)";
                  el.style.background = "var(--color-panel-2)";
                }}
              >
                {/* Priority stripe */}
                <div style={{ width: "3px", background: accent, flexShrink: 0 }} />

                <div style={{ flex: 1, padding: "0.9rem 1.15rem", minWidth: 0 }}>
                  <div style={{ display: "flex", alignItems: "center", gap: "0.5rem", marginBottom: "0.35rem", flexWrap: "wrap" }}>
                    <span style={{
                      fontSize: "0.72rem", fontWeight: 700,
                      padding: "0.12rem 0.5rem", borderRadius: "20px",
                      background: `${accent}18`, border: `1px solid ${accent}50`, color: accent,
                    }}>
                      {r.priority === "CRITICAL" ? "Critical" : r.priority === "HIGH" ? "High" : r.priority === "MEDIUM" ? "Medium" : "Low"} priority
                    </span>
                    <span style={{ fontSize: "0.8rem", color: "var(--color-ink-dim)" }}>
                      {translateCategory(r.recommendation_category)}
                    </span>
                  </div>
                  <div style={{ fontSize: "0.95rem", fontWeight: 700, color: "var(--color-ink)", marginBottom: "0.25rem", lineHeight: 1.35 }}>
                    {title}
                  </div>
                  <div style={{ fontSize: "0.85rem", color: "var(--color-ink-muted)", lineHeight: 1.5 }}>
                    <span>{sensor}</span>
                    {" · "}
                    {reason.length > 90 ? reason.slice(0, 87) + "…" : reason}
                  </div>
                </div>

                <div style={{ display: "flex", alignItems: "center", padding: "0 1rem", color: "var(--accent-cyan)", fontSize: "0.85rem", flexShrink: 0 }}>
                  →
                </div>
              </div>
            </a>
          );
        })}
      </div>
      <Pager total={data.total} limit={data.limit} offset={data.offset} onChange={setOffset} />
    </div>
  );
}
