import { NavLink, Outlet, useLocation } from "react-router-dom";
import { useEffect, useState } from "react";
import { api } from "../api";
import type { DashboardSummary } from "../api/types";
import {
  IconOverview,
  IconTwin,
  IconIntelligence,
  IconPlanning,
  IconCommand,
} from "./icons";

const NAV_ITEMS = [
  { to: "/", label: "Overview", icon: <IconOverview size={17} /> },
  { to: "/twin", label: "Digital Twin", icon: <IconTwin size={17} /> },
  { to: "/intelligence", label: "Intelligence", icon: <IconIntelligence size={17} /> },
  { to: "/what-if", label: "Space Planning", icon: <IconPlanning size={17} /> },
];

export function AppLayout({ dashData }: { dashData?: DashboardSummary | null }) {
  const location = useLocation();
  const [isApiUp, setIsApiUp] = useState<boolean | null>(null);

  useEffect(() => {
    let alive = true;
    api
      .dashboard()
      .then(() => alive && setIsApiUp(true))
      .catch(() => alive && setIsApiUp(false));
    return () => {
      alive = false;
    };
  }, []);

  const totalReadings = dashData?.telemetry?.total_readings ?? 1390297;

  return (
    <div style={{ display: "flex", height: "100vh", background: "var(--bg-dark)", color: "var(--color-ink)", overflow: "hidden", position: "relative" }}>
      {/* Subtle Atmospheric Gradient Background Glows */}
      <div className="ambient-glow-cyan" style={{ top: "-100px", left: "15%" }} />
      <div className="ambient-glow-violet" style={{ bottom: "-150px", right: "10%" }} />

      {/* ── MINIMAL SIDEBAR NAVIGATION ───────────────────────────── */}
      <aside
        style={{
          width: "230px",
          flexShrink: 0,
          display: "flex",
          flexDirection: "column",
          background: "rgba(5, 7, 17, 0.8)",
          backdropFilter: "blur(20px)",
          borderRight: "1px solid var(--color-line)",
          zIndex: 20,
        }}
      >
        {/* Brand Mark Header */}
        <div style={{ padding: "1.75rem 1.5rem 1.25rem" }}>
          <div style={{ display: "flex", alignItems: "center", gap: "0.75rem" }}>
            <div
              style={{
                width: "32px",
                height: "32px",
                background: "linear-gradient(135deg, #38bdf8 0%, #22d3ee 100%)",
                borderRadius: "8px",
                display: "grid",
                placeItems: "center",
                color: "#050711",
                boxShadow: "0 0 20px rgba(56, 189, 248, 0.4)",
              }}
            >
              <IconCommand size={18} />
            </div>
            <div>
              <div style={{ fontSize: "1.1rem", fontWeight: 900, letterSpacing: "0.02em", color: "#ffffff", lineHeight: 1 }}>
                CAMPUSIQ
              </div>
              <div style={{ fontSize: "0.65rem", fontWeight: 700, color: "var(--accent-cyan)", letterSpacing: "0.08em", textTransform: "uppercase", marginTop: "4px" }}>
                AI CAMPUS OPERATIONS
              </div>
            </div>
          </div>
        </div>

        {/* Clean Borderless Navigation Links */}
        <nav style={{ padding: "1rem 0.85rem", flex: 1, display: "flex", flexDirection: "column", gap: "0.25rem" }}>
          {NAV_ITEMS.map((item) => {
            const isActive = item.to === "/" ? location.pathname === "/" : location.pathname.startsWith(item.to);
            return (
              <NavLink
                key={item.to}
                to={item.to}
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: "0.85rem",
                  padding: "0.65rem 0.85rem",
                  borderRadius: "8px",
                  textDecoration: "none",
                  transition: "all 0.2s ease",
                  color: isActive ? "#ffffff" : "var(--color-ink-muted)",
                  fontWeight: isActive ? 700 : 500,
                  fontSize: "0.875rem",
                  background: isActive ? "linear-gradient(90deg, rgba(34, 211, 238, 0.12) 0%, rgba(56, 189, 248, 0.04) 100%)" : "transparent",
                  position: "relative",
                }}
              >
                {isActive && (
                  <div
                    style={{
                      position: "absolute",
                      left: "0",
                      width: "3px",
                      height: "16px",
                      background: "var(--accent-cyan)",
                      borderRadius: "0 2px 2px 0",
                      boxShadow: "0 0 10px var(--accent-cyan)",
                    }}
                  />
                )}
                <div style={{ color: isActive ? "var(--accent-cyan)" : "var(--color-ink-dim)" }}>
                  {item.icon}
                </div>
                <span>{item.label}</span>
              </NavLink>
            );
          })}
        </nav>

        {/* Sidebar Status Footer */}
        <div style={{ padding: "1.25rem 1.5rem", borderTop: "1px solid var(--color-line)" }}>
          <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
            <span className="live-dot" style={{ background: isApiUp ? "var(--accent-emerald)" : "var(--accent-amber)" }} />
            <span style={{ fontSize: "0.725rem", fontWeight: 700, color: isApiUp ? "var(--color-ink-muted)" : "var(--color-warn)", letterSpacing: "0.04em", textTransform: "uppercase" }}>
              {isApiUp === null ? "Connecting..." : isApiUp ? "SYSTEM OPERATIONAL" : "API DISCONNECTED"}
            </span>
          </div>
        </div>
      </aside>

      {/* ── MAIN CONTENT AREA ────────────────────────────────────── */}
      <main style={{ flex: 1, display: "flex", flexDirection: "column", minWidth: 0, zIndex: 10, position: "relative" }}>
        {/* Minimal Top Header Line */}
        <header
          style={{
            height: "50px",
            padding: "0 2rem",
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            flexShrink: 0,
            borderBottom: "1px solid var(--color-line)",
          }}
        >
          {/* Left Title */}
          <div style={{ fontSize: "0.8rem", fontWeight: 800, letterSpacing: "0.08em", color: "var(--color-ink-muted)", textTransform: "uppercase" }}>
            CAMPUSIQ <span style={{ color: "var(--color-ink-dim)", margin: "0 0.4rem" }}>·</span> <span style={{ color: "#ffffff" }}>SMART CAMPUS OPERATIONS</span>
          </div>

          {/* Right Data Specs */}
          <div style={{ display: "flex", alignItems: "center", gap: "1rem", fontSize: "0.775rem", color: "var(--color-ink-muted)" }}>
            <span style={{ fontWeight: 600, color: "#ffffff" }}>TalTech DS3</span>
            <span style={{ color: "var(--color-ink-dim)" }}>·</span>
            <span style={{ display: "inline-flex", alignItems: "center", gap: "0.4rem" }}>
              <span className="live-dot" />
              <strong style={{ color: "var(--accent-cyan)" }}>{(totalReadings / 1000000).toFixed(2)}M</strong> Telemetry Readings
            </span>
          </div>
        </header>

        {/* Viewport Content */}
        <div
          style={{
            flex: 1,
            overflow: location.pathname.startsWith("/twin") ? "hidden" : "auto",
            padding: location.pathname.startsWith("/twin") ? "0" : "2rem",
          }}
        >
          <Outlet />
        </div>
      </main>
    </div>
  );
}
