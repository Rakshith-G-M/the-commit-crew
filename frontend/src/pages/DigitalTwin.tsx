import { useEffect, useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { useApi } from "../hooks/useApi";
import { api } from "../api";
import { ErrorState, LoadingState } from "../components/common";
import { TwinViewer } from "../components/TwinViewer";
import { BimSpacePanel } from "../components/BimSpacePanel";
import {
  fmtArea,
  formatStoreyName,
  formatSpaceRoomName,
  type TwinManifest,
} from "../lib/format";
import { IconBuilding } from "../components/icons";

type Loadable<T> =
  | { status: "loading" }
  | { status: "error"; message: string }
  | { status: "ready"; data: T };

function useJson(url: string): Loadable<TwinManifest> {
  const [state, setState] = useState<Loadable<TwinManifest>>({ status: "loading" });
  useEffect(() => {
    let alive = true;
    setState({ status: "loading" });
    fetch(url)
      .then((r) => (r.ok ? r.json() : Promise.reject(new Error(`HTTP ${r.status}`))))
      .then((data: TwinManifest) => alive && setState({ status: "ready", data }))
      .catch((e: unknown) =>
        alive && setState({ status: "error", message: String((e as Error).message ?? e) })
      );
    return () => {
      alive = false;
    };
  }, [url]);
  return state;
}

export function DigitalTwinPage() {
  const manifest = useJson("/models/twin_manifest.json");
  const { state: campusState } = useApi(() => api.campus(), []);
  const { state: spacesState } = useApi(() => api.spaces({ limit: 500 }), []);

  const [searchParams, setSearchParams] = useSearchParams();
  const spaceParam = searchParams.get("space");

  const [currentStorey, setCurrentStorey] = useState<string | null>(null);
  const [selectedSpace, setSelectedSpace] = useState<string | null>(null);
  const [hoveredSpace, setHoveredSpace] = useState<string | null>(null);
  const [spaceSearch, setSpaceSearch] = useState("");
  const [spaceNotFoundError, setSpaceNotFoundError] = useState<string | null>(null);

  const [showLeftPanel, setShowLeftPanel] = useState(true);
  const [showRightPanel, setShowRightPanel] = useState(true);

  const [resetTrigger, setResetTrigger] = useState(0);
  const [fitTrigger, setFitTrigger] = useState(0);

  // Handle deep-linked room selection via URL parameter: /twin?space=<id>
  useEffect(() => {
    if (manifest.status === "ready" && spaceParam) {
      const q = spaceParam.trim().toLowerCase();
      const found = manifest.data.spaces.find(
        (s) =>
          s.space_id.toLowerCase() === q ||
          (s.ifc_global_id && s.ifc_global_id.toLowerCase() === q) ||
          (s.ifc_name && s.ifc_name.toLowerCase() === q)
      );

      if (found) {
        setSelectedSpace(found.space_id);
        if (found.storey_id) {
          setCurrentStorey(found.storey_id);
        }
        setSpaceNotFoundError(null);
      } else {
        setSpaceNotFoundError(spaceParam);
      }
    }
  }, [manifest, spaceParam]);

  const spaces = spacesState.status === "READY" ? spacesState.data.items : [];
  const campus = campusState.status === "READY" ? campusState.data : null;

  const storeyName = useMemo(() => {
    const m = new Map<string, string | null>(
      (campus?.storeys ?? []).map((s) => [s.storey_id, s.name])
    );
    if (manifest.status === "ready") {
      for (const s of manifest.data.storeys)
        if (!m.has(s.storey_id)) m.set(s.storey_id, s.name);
    }
    return m;
  }, [campus, manifest]);

  const selected = useMemo(() => {
    if (!selectedSpace) return null;
    const space = spaces.find((s) => s.space_id === selectedSpace) ?? null;
    const ref =
      manifest.status === "ready"
        ? manifest.data.spaces.find((s) => s.space_id === selectedSpace) ?? null
        : null;
    return { space, ref };
  }, [selectedSpace, spaces, manifest]);

  const filteredSpaces = useMemo(() => {
    if (manifest.status !== "ready") return [];
    let list = manifest.data.spaces;
    if (currentStorey) {
      list = list.filter((s) => s.storey_id === currentStorey);
    }
    if (spaceSearch.trim()) {
      const q = spaceSearch.toLowerCase();
      list = list.filter((s) => {
        const roomName = formatSpaceRoomName(s.ifc_name, s.space_id).toLowerCase();
        const rawStorey = storeyName.get(s.storey_id ?? "") ?? "";
        const floorName = formatStoreyName(rawStorey).toLowerCase();
        return (
          (s.ifc_name ?? "").toLowerCase().includes(q) ||
          roomName.includes(q) ||
          floorName.includes(q) ||
          rawStorey.toLowerCase().includes(q) ||
          s.space_id.toLowerCase().includes(q)
        );
      });
    }
    return list;
  }, [manifest, currentStorey, spaceSearch, storeyName]);

  if (manifest.status === "loading")
    return <LoadingState label="Loading TalTech IFC 3D Building Geometry..." />;
  if (manifest.status === "error")
    return (
      <ErrorState
        error={{
          status: 0,
          name: "Error",
          message: `Twin manifest unavailable: ${manifest.message}`,
        }}
      />
    );

  const { data: mf } = manifest;

  return (
    <div
      style={{
        position: "relative",
        width: "100%",
        height: "calc(100vh - 65px)",
        background: "#050711",
        overflow: "hidden",
      }}
    >
      {/* ── 100% FULL-CANVAS 3D VIEWPORT (VISUAL HERO) ── */}
      <div style={{ position: "absolute", inset: 0, zIndex: 1 }}>
        <TwinViewer
          manifest={mf}
          currentStorey={currentStorey}
          selectedSpace={selectedSpace}
          hoveredSpace={hoveredSpace}
          onSelect={(id) => setSelectedSpace(id)}
          onHover={setHoveredSpace}
          externalResetTrigger={resetTrigger}
          externalFitTrigger={fitTrigger}
        />
      </div>

      {/* ── SPACE NOT FOUND BANNER ── */}
      {spaceNotFoundError && (
        <div
          style={{
            position: "absolute",
            top: "1.25rem",
            left: "50%",
            transform: "translateX(-50%)",
            zIndex: 35,
            padding: "0.55rem 1.25rem",
            background: "rgba(248, 113, 113, 0.9)",
            backdropFilter: "blur(16px)",
            border: "1px solid rgba(248, 113, 113, 0.5)",
            borderRadius: "9999px",
            display: "flex",
            alignItems: "center",
            gap: "1rem",
            color: "#ffffff",
            fontSize: "0.85rem",
            fontWeight: 700,
            boxShadow: "0 10px 30px rgba(0,0,0,0.6)",
          }}
        >
          <span>Space not found ("{spaceNotFoundError}")</span>
          <button
            onClick={() => {
              setSpaceNotFoundError(null);
              setSearchParams({});
            }}
            style={{
              background: "#ffffff",
              border: "none",
              color: "#050711",
              padding: "0.25rem 0.75rem",
              borderRadius: "9999px",
              cursor: "pointer",
              fontSize: "0.78rem",
              fontWeight: 800,
            }}
          >
            Show all spaces
          </button>
        </div>
      )}

      {/* ── FLOATING TOP-CENTER FLOOR NAVIGATION TOOLBAR ── */}
      <div
        style={{
          position: "absolute",
          top: "1.25rem",
          left: "50%",
          transform: "translateX(-50%)",
          zIndex: 20,
          display: "flex",
          alignItems: "center",
          gap: "0.35rem",
          padding: "0.4rem 0.65rem",
          background: "rgba(11, 15, 28, 0.78)",
          backdropFilter: "blur(16px)",
          border: "1px solid var(--color-line-bright)",
          borderRadius: "9999px",
          boxShadow: "0 10px 30px rgba(0, 0, 0, 0.6)",
        }}
      >
        <button
          onClick={() => setCurrentStorey(null)}
          style={{
            padding: "0.35rem 0.85rem",
            borderRadius: "9999px",
            fontSize: "0.75rem",
            fontWeight: 700,
            cursor: "pointer",
            border: "none",
            background: currentStorey === null ? "var(--accent-cyan)" : "transparent",
            color: currentStorey === null ? "#050711" : "var(--color-ink-muted)",
            transition: "all 0.15s ease",
          }}
        >
          ALL FLOORS
        </button>
        {mf.storeys.map((s) => {
          const isSelected = currentStorey === s.storey_id;
          return (
            <button
              key={s.storey_id}
              onClick={() => setCurrentStorey(isSelected ? null : s.storey_id)}
              style={{
                padding: "0.35rem 0.85rem",
                borderRadius: "9999px",
                fontSize: "0.75rem",
                fontWeight: 700,
                cursor: "pointer",
                border: "none",
                background: isSelected ? "var(--accent-cyan)" : "transparent",
                color: isSelected ? "#050711" : "var(--color-ink-muted)",
                transition: "all 0.15s ease",
              }}
            >
              {formatStoreyName(s.name).toUpperCase()}
            </button>
          );
        })}
      </div>

      {/* ── FLOATING TOP-RIGHT VIEW CONTROLS (RESET VIEW / TOP VIEW) ── */}
      <div
        style={{
          position: "absolute",
          top: "1.25rem",
          right: "1.25rem",
          zIndex: 20,
          display: "flex",
          gap: "0.5rem",
          alignItems: "center",
        }}
      >
        <button
          id="twin-reset-view-header"
          onClick={() => setResetTrigger((v) => v + 1)}
          style={{
            padding: "0.45rem 0.85rem",
            borderRadius: "8px",
            border: "1px solid var(--color-line-bright)",
            background: "rgba(11, 15, 28, 0.82)",
            backdropFilter: "blur(12px)",
            color: "var(--color-ink-2)",
            fontSize: "0.8rem",
            fontWeight: 600,
            cursor: "pointer",
            transition: "all 0.15s ease",
            boxShadow: "0 8px 24px rgba(0,0,0,0.5)",
          }}
          onMouseEnter={(e) => {
            (e.currentTarget as HTMLButtonElement).style.borderColor = "var(--accent-cyan)";
            (e.currentTarget as HTMLButtonElement).style.color = "#ffffff";
          }}
          onMouseLeave={(e) => {
            (e.currentTarget as HTMLButtonElement).style.borderColor = "var(--color-line-bright)";
            (e.currentTarget as HTMLButtonElement).style.color = "var(--color-ink-2)";
          }}
        >
          ⊡ Reset View
        </button>
        <button
          id="twin-top-view-header"
          onClick={() => setFitTrigger((v) => v + 1)}
          style={{
            padding: "0.45rem 0.85rem",
            borderRadius: "8px",
            border: "1px solid var(--color-line-bright)",
            background: "rgba(11, 15, 28, 0.82)",
            backdropFilter: "blur(12px)",
            color: "var(--color-ink-2)",
            fontSize: "0.8rem",
            fontWeight: 600,
            cursor: "pointer",
            transition: "all 0.15s ease",
            boxShadow: "0 8px 24px rgba(0,0,0,0.5)",
          }}
          onMouseEnter={(e) => {
            (e.currentTarget as HTMLButtonElement).style.borderColor = "var(--accent-cyan)";
            (e.currentTarget as HTMLButtonElement).style.color = "#ffffff";
          }}
          onMouseLeave={(e) => {
            (e.currentTarget as HTMLButtonElement).style.borderColor = "var(--color-line-bright)";
            (e.currentTarget as HTMLButtonElement).style.color = "var(--color-ink-2)";
          }}
        >
          ↑ Top View
        </button>
        <button
          onClick={() => setShowRightPanel((v) => !v)}
          style={{
            padding: "0.45rem 0.65rem",
            borderRadius: "8px",
            border: "1px solid var(--color-line)",
            background: showRightPanel ? "rgba(34, 211, 238, 0.15)" : "rgba(11, 15, 28, 0.82)",
            color: showRightPanel ? "var(--accent-cyan)" : "var(--color-ink-dim)",
            fontSize: "0.8rem",
            fontWeight: 700,
            cursor: "pointer",
          }}
          title="Toggle Space Inspector Panel"
        >
          Inspector {showRightPanel ? "▲" : "▼"}
        </button>
      </div>

      {/* ── FLOATING LEFT PANEL — BUILDING SPACES DIRECTORY OVERLAY ── */}
      {showLeftPanel ? (
        <div
          style={{
            position: "absolute",
            top: "1.25rem",
            left: "1.25rem",
            width: "280px",
            maxHeight: "calc(100vh - 105px)",
            zIndex: 20,
            display: "flex",
            flexDirection: "column",
            background: "rgba(11, 15, 28, 0.78)",
            backdropFilter: "blur(16px)",
            border: "1px solid var(--color-line)",
            borderRadius: "14px",
            padding: "0.875rem",
            boxShadow: "0 20px 40px rgba(0, 0, 0, 0.6)",
            overflow: "hidden",
          }}
        >
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: "0.6rem" }}>
            <div style={{ display: "flex", alignItems: "center", gap: "0.4rem" }}>
              <div style={{ fontSize: "0.78rem", fontWeight: 800, color: "var(--accent-cyan)", letterSpacing: "0.06em", textTransform: "uppercase" }}>
                BUILDING SPACES
              </div>
              <span
                style={{
                  fontSize: "0.75rem",
                  color: "var(--color-ink-dim)",
                  fontFamily: "var(--font-mono)",
                  fontWeight: 700,
                  background: "rgba(255, 255, 255, 0.06)",
                  padding: "0.1rem 0.45rem",
                  borderRadius: "4px",
                }}
              >
                {filteredSpaces.length}
              </span>
            </div>
            <button
              onClick={() => setShowLeftPanel(false)}
              style={{
                background: "transparent",
                border: "none",
                color: "var(--color-ink-dim)",
                cursor: "pointer",
                fontSize: "0.75rem",
              }}
              title="Hide panel"
            >
              ◀
            </button>
          </div>

          <input
            type="text"
            placeholder="Search room..."
            value={spaceSearch}
            onChange={(e) => setSpaceSearch(e.target.value)}
            style={{
              background: "rgba(5, 7, 17, 0.8)",
              border: "1px solid var(--color-line)",
              borderRadius: "8px",
              padding: "0.5rem 0.75rem",
              fontSize: "0.825rem",
              color: "#ffffff",
              outline: "none",
              marginBottom: "0.65rem",
            }}
          />

          <div className="scroll-thin" style={{ flex: 1, overflowY: "auto", display: "flex", flexDirection: "column", gap: "0.3rem" }}>
            {filteredSpaces.map((s) => {
              const isSelected = selectedSpace === s.space_id;
              const roomName = formatSpaceRoomName(s.ifc_name, s.space_id);
              const rawSt = storeyName.get(s.storey_id ?? "");
              return (
                <div
                  key={s.space_id}
                  onClick={() => setSelectedSpace(isSelected ? null : s.space_id)}
                  onMouseEnter={() => setHoveredSpace(s.space_id)}
                  onMouseLeave={() => setHoveredSpace(null)}
                  style={{
                    padding: "0.5rem 0.75rem",
                    borderRadius: "8px",
                    background: isSelected ? "rgba(34, 211, 238, 0.15)" : "rgba(15, 23, 42, 0.4)",
                    border: `1px solid ${isSelected ? "rgba(34, 211, 238, 0.5)" : "transparent"}`,
                    cursor: "pointer",
                    transition: "all 0.15s ease",
                  }}
                >
                  <div style={{ fontSize: "0.875rem", fontWeight: isSelected ? 700 : 500, color: isSelected ? "var(--accent-cyan)" : "#ffffff" }}>
                    {roomName}
                  </div>
                  <div style={{ fontSize: "0.75rem", color: "var(--color-ink-dim)", marginTop: "0.15rem" }}>
                    {formatStoreyName(rawSt)} · {fmtArea(s.area_m2)}
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      ) : (
        <button
          onClick={() => setShowLeftPanel(true)}
          style={{
            position: "absolute",
            top: "1.25rem",
            left: "1.25rem",
            zIndex: 20,
            padding: "0.5rem 0.85rem",
            borderRadius: "8px",
            border: "1px solid var(--color-line-bright)",
            background: "rgba(11, 15, 28, 0.85)",
            backdropFilter: "blur(12px)",
            color: "var(--accent-cyan)",
            fontSize: "0.8rem",
            fontWeight: 700,
            cursor: "pointer",
            boxShadow: "0 10px 25px rgba(0,0,0,0.5)",
          }}
        >
          ▶ Building Spaces
        </button>
      )}

      {/* ── FLOATING RIGHT PANEL — SPACE INSPECTOR OVERLAY ── */}
      {showRightPanel && (
        <div
          className="scroll-thin"
          style={{
            position: "absolute",
            top: "4.5rem",
            right: "1.25rem",
            width: "340px",
            maxHeight: "calc(100vh - 130px)",
            zIndex: 20,
            overflowY: "auto",
            background: "rgba(11, 15, 28, 0.78)",
            backdropFilter: "blur(16px)",
            border: "1px solid var(--color-line)",
            borderRadius: "14px",
            boxShadow: "0 20px 40px rgba(0, 0, 0, 0.6)",
          }}
        >
          {selected ? (
            <BimSpacePanel
              spaceId={selectedSpace ?? ""}
              spaceName={selected.ref?.ifc_name ?? null}
              storey={storeyName.get(selected.ref?.storey_id ?? "") ?? null}
              area={selected.space?.area_m2 ?? selected.ref?.area_m2 ?? null}
              volume={selected.space?.volume_m3 ?? selected.ref?.volume_m3 ?? null}
              height={selected.ref?.height_m ?? null}
              capacity={selected.space?.capacity_occupants ?? null}
              occupiable={selected.space?.occupiable ?? true}
              conditioning={selected.space?.conditioning ?? null}
              ifcGlobalId={selected.ref?.ifc_global_id ?? null}
              rawStorey={selected.ref?.storey_id ? storeyName.get(selected.ref.storey_id) : null}
            />
          ) : (
            <div
              style={{
                padding: "2rem 1.5rem",
                textAlign: "center",
                color: "var(--color-ink-muted)",
              }}
            >
              <IconBuilding size={36} color="var(--accent-cyan)" style={{ marginBottom: "0.85rem", opacity: 0.85 }} />
              <div style={{ fontSize: "0.95rem", fontWeight: 800, color: "#ffffff", marginBottom: "0.4rem" }}>
                SPACE INSPECTOR
              </div>
              <p style={{ fontSize: "0.825rem", color: "var(--color-ink-2)", margin: 0, lineHeight: 1.55 }}>
                Select a room from the 3D model or building directory to inspect its BIM properties.
              </p>
            </div>
          )}
        </div>
      )}
    </div>
  );
}