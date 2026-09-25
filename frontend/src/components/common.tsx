import type { ReactNode } from "react";
import type { ApiError } from "../api/client";
import { toneFor, tonePalette, type Tone } from "../lib/format";
import { IconAlert, IconInfo, IconRefresh } from "./icons";

// ── Panel ─────────────────────────────────────────────────────
export function Panel({
  title,
  hint,
  actions,
  children,
  className = "",
  noPad = false,
}: {
  title?: string;
  hint?: string;
  actions?: ReactNode;
  children: ReactNode;
  className?: string;
  noPad?: boolean;
}) {
  return (
    <div
      className={`glass-panel ${className}`}
      data-testid={title ? `panel-${title}` : undefined}
      style={{
        background: "var(--bg-glass)",
        border: "1px solid var(--color-line)",
        borderRadius: "14px",
        overflow: "hidden",
      }}
    >
      {(title || actions) && (
        <div
          style={{
            padding: "1rem 1.25rem",
            borderBottom: "1px solid var(--color-line)",
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            gap: "0.75rem",
            background: "rgba(16, 26, 49, 0.4)",
          }}
        >
          <div style={{ display: "flex", alignItems: "baseline", gap: "0.5rem", minWidth: 0 }}>
            <h2 style={{ fontSize: "0.95rem", fontWeight: 700, color: "var(--color-ink)", letterSpacing: "-0.01em" }}>
              {title}
            </h2>
            {hint && <span style={{ fontSize: "0.75rem", color: "var(--color-ink-muted)" }}>{hint}</span>}
          </div>
          {actions && <div style={{ flexShrink: 0 }}>{actions}</div>}
        </div>
      )}
      <div style={noPad ? {} : { padding: "1.25rem" }}>{children}</div>
    </div>
  );
}

// ── Stat Card ──────────────────────────────────────────────────
export function Stat({
  label,
  value,
  sub,
  tone = "info",
  large = false,
  sparkline,
  icon,
}: {
  label: string;
  value: ReactNode;
  sub?: ReactNode;
  tone?: Tone;
  large?: boolean;
  sparkline?: ReactNode;
  icon?: ReactNode;
}) {
  const accentColors: Record<Tone, string> = {
    info: "var(--accent-blue)",
    ok: "var(--color-ok)",
    warn: "var(--color-warn)",
    danger: "var(--color-danger)",
    dim: "var(--color-ink-muted)",
  };

  return (
    <div
      className="glass-panel glass-panel-hover"
      style={{
        padding: "1.1rem 1.25rem",
        display: "flex",
        flexDirection: "column",
        justifyContent: "space-between",
        position: "relative",
        minHeight: large ? "130px" : "100px",
      }}
    >
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: "0.5rem" }}>
        <span style={{ fontSize: "0.7rem", fontWeight: 700, color: "var(--color-ink-muted)", textTransform: "uppercase", letterSpacing: "0.05em" }}>
          {label}
        </span>
        {icon && <div style={{ color: accentColors[tone], opacity: 0.85 }}>{icon}</div>}
      </div>

      <div style={{ display: "flex", alignItems: "baseline", gap: "0.5rem", margin: "0.25rem 0" }}>
        <span style={{ fontSize: large ? "2.2rem" : "1.6rem", fontWeight: 800, color: accentColors[tone], lineHeight: 1, letterSpacing: "-0.02em" }}>
          {value}
        </span>
      </div>

      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginTop: "0.25rem" }}>
        {sub && <span style={{ fontSize: "0.725rem", color: "var(--color-ink-dim)" }}>{sub}</span>}
        {sparkline && <div>{sparkline}</div>}
      </div>
    </div>
  );
}

// ── Badge ─────────────────────────────────────────────────────
export function Badge({
  label,
  tone = "info",
  mono = false,
}: {
  label: ReactNode;
  tone?: Tone;
  mono?: boolean;
}) {
  const badgeStyles: Record<Tone, { bg: string; color: string; border: string }> = {
    info: { bg: "rgba(56, 189, 248, 0.12)", color: "#7dd3fc", border: "rgba(56, 189, 248, 0.3)" },
    ok: { bg: "rgba(52, 211, 153, 0.12)", color: "#6ee7b7", border: "rgba(52, 211, 153, 0.3)" },
    warn: { bg: "rgba(245, 158, 11, 0.12)", color: "#fde047", border: "rgba(245, 158, 11, 0.3)" },
    danger: { bg: "rgba(244, 63, 94, 0.12)", color: "#fda4af", border: "rgba(244, 63, 94, 0.3)" },
    dim: { bg: "rgba(148, 163, 184, 0.12)", color: "#cbd5e1", border: "rgba(148, 163, 184, 0.2)" },
  };

  const current = badgeStyles[tone] ?? badgeStyles.info;

  return (
    <span
      className="badge-pill"
      style={{
        background: current.bg,
        color: current.color,
        border: `1px solid ${current.border}`,
        fontFamily: mono ? "var(--font-mono)" : "var(--font-sans)",
      }}
    >
      {label}
    </span>
  );
}

export function SeverityBadge({ value }: { value: string | null | undefined }) {
  return <Badge label={value ?? "UNKNOWN"} tone={toneFor(value)} mono />;
}

export function PriorityBadge({ value }: { value: string | null | undefined }) {
  const tone =
    value === "CRITICAL" ? "danger"
    : value === "HIGH" ? "danger"
    : value === "MEDIUM" ? "warn"
    : "ok";
  return <Badge label={value ?? "UNKNOWN"} tone={tone} mono />;
}

// ── Status Pill ───────────────────────────────────────────────
export function StatusPill({ ok, text }: { ok: boolean; text: string }) {
  return (
    <span
      style={{
        display: "inline-flex",
        alignItems: "center",
        gap: "0.4rem",
        fontSize: "0.75rem",
        fontWeight: 600,
        color: ok ? "var(--color-ok)" : "var(--color-warn)",
        background: ok ? "rgba(52, 211, 153, 0.08)" : "rgba(245, 158, 11, 0.08)",
        border: `1px solid ${ok ? "rgba(52, 211, 153, 0.25)" : "rgba(245, 158, 11, 0.25)"}`,
        padding: "0.2rem 0.6rem",
        borderRadius: "9999px",
      }}
    >
      <span className="status-dot-live" style={{ background: ok ? "var(--color-ok)" : "var(--color-warn)" }} />
      {text}
    </span>
  );
}

// ── Loading State ─────────────────────────────────────────────
export function LoadingState({ label = "Processing telemetry intelligence…" }: { label?: string }) {
  return (
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
        gap: "1rem",
        padding: "4rem 2rem",
        color: "var(--color-ink-muted)",
      }}
      data-testid="loading-state"
    >
      <div
        style={{
          width: "36px",
          height: "36px",
          border: "3px solid rgba(56, 189, 248, 0.15)",
          borderTopColor: "var(--accent-blue)",
          borderRadius: "50%",
          animation: "spin 0.8s linear infinite",
        }}
      />
      <span style={{ fontSize: "0.85rem", fontWeight: 500, color: "var(--color-ink-muted)" }}>{label}</span>
      <style>{`@keyframes spin { 0% { transform: rotate(0deg); } 100% { transform: rotate(360deg); } }`}</style>
    </div>
  );
}

// ── Error State ───────────────────────────────────────────────
export function ErrorState({
  error,
  onRetry,
}: {
  error: ApiError;
  onRetry?: () => void;
}) {
  const unreachable = error.status === 0;
  const message = unreachable
    ? "Cannot connect to CampusIQ Backend API. Please start the backend service."
    : `Request failed (${error.status}): ${error.message}`;

  return (
    <div
      style={{
        background: "rgba(244, 63, 94, 0.08)",
        border: "1px solid rgba(244, 63, 94, 0.25)",
        borderRadius: "12px",
        padding: "1.25rem 1.5rem",
        color: "#fda4af",
      }}
      data-testid="error-state"
    >
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: "1rem" }}>
        <div style={{ display: "flex", alignItems: "center", gap: "0.5rem", fontWeight: 700, fontSize: "0.9rem" }}>
          <IconAlert size={18} color="var(--color-danger)" />
          {unreachable ? "CampusIQ API Unavailable" : "Telemetry Request Failure"}
        </div>
        {onRetry && (
          <button
            onClick={onRetry}
            className="btn-secondary"
            style={{ fontSize: "0.75rem", padding: "0.3rem 0.75rem" }}
            data-testid="retry-button"
          >
            <IconRefresh size={14} /> Retry
          </button>
        )}
      </div>
      <div style={{ marginTop: "0.5rem", fontFamily: "var(--font-mono)", fontSize: "0.75rem", opacity: 0.9 }}>
        {message}
      </div>
    </div>
  );
}

// ── Empty State ───────────────────────────────────────────────
export function EmptyState({ message }: { message: string }) {
  return (
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
        gap: "0.75rem",
        padding: "3.5rem 2rem",
        textAlign: "center",
        color: "var(--color-ink-muted)",
        background: "rgba(11, 18, 36, 0.4)",
        borderRadius: "12px",
        border: "1px stroke var(--color-line)",
      }}
      data-testid="empty-state"
    >
      <IconInfo size={28} color="var(--color-ink-dim)" />
      <span style={{ fontSize: "0.85rem", color: "var(--color-ink-muted)" }}>{message}</span>
    </div>
  );
}

// ── Pager ─────────────────────────────────────────────────────
export function Pager({
  total,
  limit,
  offset,
  onChange,
}: {
  total: number;
  limit: number;
  offset: number;
  onChange: (offset: number) => void;
}) {
  const pages = Math.max(1, Math.ceil(total / limit));
  const current = Math.floor(offset / limit);
  if (pages <= 1) return null;

  return (
    <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", paddingTop: "1rem", marginTop: "1rem", borderTop: "1px solid var(--color-line)" }}>
      <span style={{ fontSize: "0.75rem", color: "var(--color-ink-dim)", fontFamily: "var(--font-mono)" }}>
        Showing {Math.min(total, offset + 1)}–{Math.min(total, offset + limit)} of {total} records
      </span>
      <div style={{ display: "flex", gap: "0.5rem", alignItems: "center" }}>
        <button
          className="btn-secondary"
          disabled={current <= 0}
          onClick={() => onChange((current - 1) * limit)}
          style={{ padding: "0.3rem 0.75rem", opacity: current <= 0 ? 0.35 : 1, fontSize: "0.75rem" }}
        >
          Previous
        </button>
        <span style={{ color: "var(--color-ink-muted)", fontSize: "0.75rem", padding: "0 0.25rem" }}>
          Page {current + 1} of {pages}
        </span>
        <button
          className="btn-secondary"
          disabled={current >= pages - 1}
          onClick={() => onChange((current + 1) * limit)}
          style={{ padding: "0.3rem 0.75rem", opacity: current >= pages - 1 ? 0.35 : 1, fontSize: "0.75rem" }}
        >
          Next
        </button>
      </div>
    </div>
  );
}

export const tonePaletteExport = tonePalette;