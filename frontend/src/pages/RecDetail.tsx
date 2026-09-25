import { Link } from "react-router-dom";
import { useApi } from "../hooks/useApi";
import { api } from "../api";
import { EmptyState, ErrorState, LoadingState } from "../components/common";
import { fmtNum } from "../lib/format";
import {
  recTitle,
  recSensorName,
  recReason,
  recImportance,
  recAction,
  recImpactItems,
  recLocationText,
  buildEvidenceSteps,
  extractIssues,
  translateCategory,
} from "../lib/recPresentation";
import {
  IconShield,
  IconAlert,
  IconBuilding,
  IconSparkles,
} from "../components/icons";

export function RecDetail({ id, onBack }: { id: string; onBack?: () => void }) {
  const { state, reload } = useApi(() => api.recommendation(id), [id]);

  if (state.status === "LOADING") return <LoadingState label="Analyzing recommendation brief..." />;
  if (state.status === "ERROR") return <ErrorState error={state.error} onRetry={reload} />;
  if (state.status === "EMPTY" || !state.data) return <EmptyState message="Recommendation record not found." />;

  const r = state.data;
  const title = recTitle(r);
  const sensor = recSensorName(r);
  const reason = recReason(r);
  const importance = recImportance(r);
  const action = recAction(r, sensor);
  const impact = recImpactItems(r);
  const location = recLocationText(r);
  const issues = extractIssues(r);
  const steps = buildEvidenceSteps(r);

  const priorityColor =
    r.priority === "CRITICAL" || r.priority === "HIGH" ? "var(--color-danger)" : r.priority === "MEDIUM" ? "var(--color-warn)" : "var(--color-ok)";

  const priorityLabel =
    r.priority === "CRITICAL" ? "Critical" : r.priority === "HIGH" ? "High" : r.priority === "MEDIUM" ? "Medium" : "Low";

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "1.5rem" }} className="fade-in">
      {/* Navigation & Header */}
      <div>
        {onBack ? (
          <button onClick={onBack} className="btn-secondary" style={{ marginBottom: "1rem" }}>
            ← Back to Recommendations
          </button>
        ) : (
          <Link to="/intelligence?tab=recommendations" className="btn-secondary" style={{ marginBottom: "1rem" }}>
            ← Back to Recommendations
          </Link>
        )}

        <div className="glass-panel" style={{ padding: "1.75rem 2rem", borderLeft: `5px solid ${priorityColor}` }}>
          <div style={{ display: "flex", alignItems: "center", gap: "0.75rem", marginBottom: "0.6rem" }}>
            <span
              style={{
                padding: "0.3rem 0.75rem",
                borderRadius: "9999px",
                fontSize: "0.78rem",
                fontWeight: 800,
                textTransform: "uppercase",
                letterSpacing: "0.04em",
                background: "rgba(244, 63, 94, 0.15)",
                color: priorityColor,
                border: `1px solid ${priorityColor}`,
              }}
            >
              {priorityLabel} Priority
            </span>
            <span style={{ fontSize: "0.85rem", color: "var(--color-ink-muted)", fontWeight: 600 }}>
              {translateCategory(r.recommendation_category)}
            </span>
          </div>

          <h1 style={{ fontSize: "1.8rem", fontWeight: 800, color: "#ffffff", letterSpacing: "-0.02em", margin: "0.25rem 0 0.5rem" }}>
            {title}
          </h1>

          <div style={{ fontSize: "1rem", fontWeight: 700, color: "var(--accent-cyan)" }}>
            {sensor}
          </div>
        </div>
      </div>

      {/* 2-Column Operational Brief Grid */}
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "1.25rem" }}>
        {/* WHAT HAPPENED */}
        <div className="glass-panel" style={{ padding: "1.5rem" }}>
          <div style={{ display: "flex", alignItems: "center", gap: "0.5rem", color: "var(--accent-cyan)", marginBottom: "0.85rem", fontWeight: 800, fontSize: "0.9rem", textTransform: "uppercase", letterSpacing: "0.03em" }}>
            <IconAlert size={18} /> WHAT HAPPENED?
          </div>
          <p style={{ fontSize: "0.95rem", color: "var(--color-ink-2)", lineHeight: 1.65, marginBottom: "1rem" }}>
            {reason}
          </p>
          {issues.length > 0 && (
            <div style={{ background: "rgba(16, 26, 49, 0.6)", padding: "0.85rem 1rem", borderRadius: "10px", border: "1px solid var(--color-line)" }}>
              <div style={{ fontSize: "0.8rem", fontWeight: 700, color: "var(--color-ink-muted)", textTransform: "uppercase", marginBottom: "0.45rem", letterSpacing: "0.03em" }}>
                Detected Issues
              </div>
              <ul style={{ paddingLeft: "1.25rem", margin: 0 }}>
                {issues.map((iss, i) => (
                  <li key={i} style={{ fontSize: "0.9rem", color: "var(--color-ink-2)", marginBottom: "0.2rem", lineHeight: 1.6 }}>
                    {iss}
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>

        {/* WHAT SHOULD I DO */}
        <div className="glass-panel" style={{ padding: "1.5rem" }}>
          <div style={{ display: "flex", alignItems: "center", gap: "0.5rem", color: "var(--accent-blue)", marginBottom: "0.85rem", fontWeight: 800, fontSize: "0.9rem", textTransform: "uppercase", letterSpacing: "0.03em" }}>
            <IconShield size={18} /> WHAT SHOULD I DO?
          </div>
          <div style={{ background: "rgba(56, 189, 248, 0.08)", border: "1px solid rgba(56, 189, 248, 0.2)", borderRadius: "10px", padding: "1.1rem 1.25rem", fontSize: "0.95rem", fontWeight: 600, color: "#ffffff", lineHeight: 1.55, marginBottom: "0.85rem" }}>
            {action}
          </div>
        </div>

        {/* WHY DOES IT MATTER */}
        <div className="glass-panel" style={{ padding: "1.5rem" }}>
          <div style={{ display: "flex", alignItems: "center", gap: "0.5rem", color: "var(--accent-amber)", marginBottom: "0.85rem", fontWeight: 800, fontSize: "0.9rem", textTransform: "uppercase", letterSpacing: "0.03em" }}>
            <IconSparkles size={18} /> WHY DOES IT MATTER?
          </div>
          <p style={{ fontSize: "0.95rem", color: "var(--color-ink-2)", lineHeight: 1.65 }}>
            {importance}
          </p>
        </div>

        {/* WHERE IS IT & EXPECTED IMPACT */}
        <div className="glass-panel" style={{ padding: "1.5rem" }}>
          <div style={{ display: "flex", alignItems: "center", gap: "0.5rem", color: "var(--color-ok)", marginBottom: "0.85rem", fontWeight: 800, fontSize: "0.9rem", textTransform: "uppercase", letterSpacing: "0.03em" }}>
            <IconBuilding size={18} /> LOCATION & EXPECTED IMPACT
          </div>

          <div style={{ marginBottom: "1rem" }}>
            <div style={{ fontSize: "0.8rem", fontWeight: 700, color: "var(--color-ink-muted)", textTransform: "uppercase", letterSpacing: "0.03em" }}>Location</div>
            <div style={{ fontSize: "0.95rem", color: "var(--color-ink)", marginTop: "0.2rem" }}>{location.primary}</div>
            {location.note && <div style={{ fontSize: "0.82rem", color: "var(--color-ink-dim)", marginTop: "0.15rem" }}>{location.note}</div>}
          </div>

          <div>
            <div style={{ fontSize: "0.8rem", fontWeight: 700, color: "var(--color-ink-muted)", textTransform: "uppercase", marginBottom: "0.45rem", letterSpacing: "0.03em" }}>Expected Impact</div>
            <ul style={{ paddingLeft: "1.25rem", margin: 0 }}>
              {impact.map((imp, i) => (
                <li key={i} style={{ fontSize: "0.9rem", color: "var(--color-ok)", marginBottom: "0.25rem", lineHeight: 1.55 }}>
                  <strong>{imp.label}:</strong>{" "}
                  <span style={{ color: "var(--color-ink-2)" }}>{imp.detail}</span>
                </li>
              ))}
            </ul>
          </div>
        </div>
      </div>

      {/* Collapsible Evidence Traceability & Technical Details */}
      <details className="glass-panel" style={{ padding: "1rem 1.5rem", cursor: "pointer" }}>
        <summary style={{ fontSize: "0.9rem", fontWeight: 700, color: "var(--color-ink-muted)", outline: "none" }}>
          Evidence Traceability Chain ({steps.length} steps)
        </summary>
        <div style={{ marginTop: "1rem", display: "flex", flexDirection: "column", gap: "0.5rem" }}>
          {steps.map((st, i) => (
            <div key={i} style={{ padding: "0.6rem 0.85rem", background: "rgba(16, 26, 49, 0.6)", borderRadius: "8px", fontSize: "0.88rem", color: "var(--color-ink-muted)" }}>
              <strong>Step {i + 1}:</strong> {st.label} — <span style={{ color: "var(--color-ink-dim)" }}>{st.detail}</span>
            </div>
          ))}
        </div>
      </details>

      <details className="glass-panel" style={{ padding: "1rem 1.5rem", cursor: "pointer" }}>
        <summary style={{ fontSize: "0.9rem", fontWeight: 700, color: "var(--color-ink-muted)", outline: "none" }}>
          Technical Diagnostic Details (Engine Metadata)
        </summary>
        <div style={{ marginTop: "1rem", fontFamily: "var(--font-mono)", fontSize: "0.82rem", color: "var(--color-ink-dim)", display: "flex", flexDirection: "column", gap: "0.35rem" }}>
          <div>Recommendation ID: {r.recommendation_id}</div>
          <div>Candidate ID: {r.candidate_id}</div>
          <div>Category: {r.recommendation_category}</div>
          <div>Priority Score: {fmtNum(r.priority_score, 3)}</div>
        </div>
      </details>
    </div>
  );
}
