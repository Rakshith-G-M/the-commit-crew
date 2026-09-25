/**
 * TwinViewer — Real IFC 3D Digital Twin Viewer
 *
 * Renders the actual TalTech DS3 building geometry extracted from
 * DS3_TalTech_V4.ifc via ifcopenshell:
 *   - Walls, slabs, columns, doors, windows, stairs, roofs (merged per storey)
 *   - 115 individual IfcSpace room volumes (selectable/hoverable)
 *
 * Node naming in GLB:
 *   campus_root                        — scene root
 *   └── storey-<storey_id>             — per-storey group
 *       ├── arch_wall_<storey_id>       — merged walls
 *       ├── arch_slab_<storey_id>       — merged slabs
 *       ├── arch_column_<storey_id>     — merged columns
 *       ├── arch_window_<storey_id>     — merged windows + mullions
 *       ├── arch_door_<storey_id>       — merged doors
 *       ├── arch_stair_<storey_id>      — merged stairs
 *       ├── arch_roof_<storey_id>       — merged roofs
 *       └── space_<guid>               — individual IfcSpace volumes (interactive)
 */

import { Suspense, useMemo, useRef, useState, useEffect } from "react";
import * as THREE from "three";
import { Canvas, useFrame, useThree } from "@react-three/fiber";
import { OrbitControls, useGLTF } from "@react-three/drei";
import {
  formatStoreyName,
  resolveSpaceDisplayName,
  type TwinManifest,
} from "../lib/format";

// ──────────────────────────────────────────────────────────────────
// Types
// ──────────────────────────────────────────────────────────────────

interface SceneState {
  currentStorey: string | null;
  selectedSpace: string | null;
  hoveredSpace: string | null;
  onSelect: (id: string | null) => void;
  onHover: (id: string | null) => void;
}

type Gltf = {
  nodes: Record<string, THREE.Mesh | THREE.Group | THREE.Object3D>;
  scene: THREE.Group;
};

// ──────────────────────────────────────────────────────────────────
// Materials — cached, premium architectural palette
// ──────────────────────────────────────────────────────────────────

const MAT_WALL = new THREE.MeshStandardMaterial({
  color: 0xb8bec9,
  roughness: 0.72,
  metalness: 0.04,
  side: THREE.FrontSide,
});

const MAT_SLAB = new THREE.MeshStandardMaterial({
  color: 0x4d5566,
  roughness: 0.88,
  metalness: 0.06,
});

const MAT_COLUMN = new THREE.MeshStandardMaterial({
  color: 0x7c8499,
  roughness: 0.68,
  metalness: 0.08,
});

const MAT_WINDOW = new THREE.MeshStandardMaterial({
  color: 0x62b8f0,
  roughness: 0.12,
  metalness: 0.15,
  transparent: true,
  opacity: 0.38,
  side: THREE.DoubleSide,
});

const MAT_DOOR = new THREE.MeshStandardMaterial({
  color: 0x6c7488,
  roughness: 0.62,
  metalness: 0.22,
});

const MAT_STAIR = new THREE.MeshStandardMaterial({
  color: 0x96a0b4,
  roughness: 0.66,
  metalness: 0.1,
});

const MAT_ROOF = new THREE.MeshStandardMaterial({
  color: 0x576070,
  roughness: 0.82,
  metalness: 0.06,
});

function getArchMaterial(cat: string): THREE.Material {
  if (cat === "slab") return MAT_SLAB;
  if (cat === "column") return MAT_COLUMN;
  if (cat === "window") return MAT_WINDOW;
  if (cat === "door") return MAT_DOOR;
  if (cat === "stair") return MAT_STAIR;
  if (cat === "roof") return MAT_ROOF;
  return MAT_WALL;
}

// Space materials — semi-transparent room volumes by storey
const STOREY_SPACE_COLORS: Record<string, THREE.Color> = {
  storey_0SLmhMRV95B9NPlMAzXhZv: new THREE.Color("#38bdf8"), // +Kelder — sky
  storey_0XZfgApoH76vdPViCcsT6m: new THREE.Color("#22d3ee"), // 1. korrus — cyan
  storey_0IEk6ObD54bwMLfrOXff7W: new THREE.Color("#2dd4bf"), // 2. korrus — teal
  storey_1mnZnZ29v9QRze4pjg0g3S: new THREE.Color("#a78bfa"), // 3. korrus — violet
  storey_15ZSjFyOz3g9926Y5YSybv: new THREE.Color("#fbbf24"), // Katus — amber
};
const DEFAULT_SPACE_COLOR = new THREE.Color("#38bdf8");

function getSpaceBaseColor(storeyId: string | null): THREE.Color {
  if (!storeyId) return DEFAULT_SPACE_COLOR;
  return STOREY_SPACE_COLORS[storeyId] ?? DEFAULT_SPACE_COLOR;
}

// ──────────────────────────────────────────────────────────────────
// Space material cache — persistent per spaceId
// ──────────────────────────────────────────────────────────────────

const spaceMaterialCache = new Map<string, THREE.MeshStandardMaterial>();

function getSpaceMaterial(spaceId: string, storeyId: string | null): THREE.MeshStandardMaterial {
  if (!spaceMaterialCache.has(spaceId)) {
    const base = getSpaceBaseColor(storeyId);
    spaceMaterialCache.set(
      spaceId,
      new THREE.MeshStandardMaterial({
        color: base,
        roughness: 0.38,
        metalness: 0.0,
        transparent: true,
        opacity: 0.14,
        side: THREE.DoubleSide,
        depthWrite: false,
      })
    );
  }
  return spaceMaterialCache.get(spaceId)!;
}

// ──────────────────────────────────────────────────────────────────
// Camera reset helper component
// ──────────────────────────────────────────────────────────────────

function CameraController({
  resetTrigger,
  fitTrigger,
  focusTarget,
}: {
  resetTrigger: number;
  fitTrigger: number;
  focusTarget: [number, number, number] | null;
}) {
  const { camera } = useThree();
  const controls = useRef<any>(null);

  // Focus camera ONCE per selected space target change
  const lastTargetKey = useRef<string | null>(null);

  useEffect(() => {
    if (focusTarget) {
      const key = `${focusTarget[0].toFixed(2)},${focusTarget[1].toFixed(2)},${focusTarget[2].toFixed(2)}`;
      if (lastTargetKey.current !== key) {
        lastTargetKey.current = key;
        const [cx, cy, cz] = focusTarget;
        // Position camera at a comfortable distance so surrounding architecture and floor context are visible
        camera.position.set(cx + 28, cy + 22, cz + 28);
        camera.lookAt(cx, cy, cz);
        if (controls.current) {
          controls.current.target.set(cx, cy, cz);
          controls.current.update();
        }
      }
    }
  }, [focusTarget, camera]);

  // Listen for external reset/fit triggers
  useEffect(() => {
    if (resetTrigger > 0) {
      camera.position.set(55, 38, 55);
      camera.lookAt(0, 11, 0);
      if (controls.current) {
        controls.current.target.set(0, 11, 0);
        controls.current.update();
      }
    }
  }, [resetTrigger, camera]);

  useEffect(() => {
    if (fitTrigger > 0) {
      camera.position.set(0, 65, 0);
      camera.lookAt(0, 0, 0);
      if (controls.current) {
        controls.current.target.set(0, 0, 0);
        controls.current.update();
      }
    }
  }, [fitTrigger, camera]);

  return (
    <OrbitControls
      ref={controls}
      makeDefault
      enableDamping
      dampingFactor={0.07}
      enablePan
      enableZoom
      minDistance={4}
      maxDistance={280}
      target={[0, 11, 0]}
      minPolarAngle={0.1}
      maxPolarAngle={1.5}
    />
  );
}

// ──────────────────────────────────────────────────────────────────
// Main scene — renders the real IFC building
// ──────────────────────────────────────────────────────────────────

function TwinScene({
  state,
  manifest,
  resetTrigger,
  fitTrigger,
}: {
  state: SceneState;
  manifest: TwinManifest;
  resetTrigger: number;
  fitTrigger: number;
}) {
  const gltf = useGLTF("/models/campus_twin.glb") as unknown as Gltf;

  // Build lookup maps from manifest
  const spaceStoreyMap = useMemo(() => {
    const m = new Map<string, string | null>();
    for (const s of manifest.spaces) {
      m.set(s.space_id, s.storey_id ?? null);
    }
    return m;
  }, [manifest.spaces]);

  // Parse GLB nodes into typed buckets
  const { archNodes, spaceNodes } = useMemo(() => {
    const archNodes: Array<{
      name: string;
      storeyId: string;
      cat: string;
      geom: THREE.BufferGeometry;
    }> = [];
    const spaceNodes: Array<{
      spaceId: string;
      storeyId: string | null;
      geom: THREE.BufferGeometry;
    }> = [];

    const traverse = (obj: THREE.Object3D) => {
      const name = obj.name || "";
      if (name === "campus_root" || name.startsWith("storey-")) {
        obj.children.forEach(traverse);
        return;
      }

      const mesh = obj as THREE.Mesh;
      if (!mesh.isMesh || !mesh.geometry) return;

      // arch_<cat>_<storeyId>
      if (name.startsWith("arch_")) {
        const parts = name.split("_");
        const cat = parts[1]; // wall, slab, column, …
        const storeyId = parts.slice(2).join("_"); // storey_<guid>
        archNodes.push({ name, storeyId, cat, geom: mesh.geometry });
        return;
      }

      // space_<guid>  (individual room volumes)
      if (name.startsWith("space_")) {
        const storeyId = spaceStoreyMap.get(name) ?? null;
        spaceNodes.push({ spaceId: name, storeyId, geom: mesh.geometry });
      }
    };

    gltf.scene.children.forEach(traverse);
    return { archNodes, spaceNodes };
  }, [gltf.scene, spaceStoreyMap]);

  const storeyIds = useMemo(
    () => manifest.storeys.map((s) => s.storey_id),
    [manifest.storeys]
  );

  // Determine which storeys to render
  const visibleStoreys = useMemo(() => {
    if (!state.currentStorey) return new Set(storeyIds);
    return new Set([state.currentStorey]);
  }, [state.currentStorey, storeyIds]);

  // Update space materials on hover/select
  useFrame(() => {
    for (const { spaceId, storeyId } of spaceNodes) {
      const mat = getSpaceMaterial(spaceId, storeyId);
      const isHovered = state.hoveredSpace === spaceId;
      const isSelected = state.selectedSpace === spaceId;

      const baseColor = getSpaceBaseColor(storeyId);
      if (isSelected) {
        mat.color.set(baseColor).multiplyScalar(3.5);
        mat.opacity = 0.72;
        mat.emissive.set(baseColor).multiplyScalar(0.45);
        mat.emissiveIntensity = 1;
      } else if (isHovered) {
        mat.color.set(baseColor).multiplyScalar(2.5);
        mat.opacity = 0.55;
        mat.emissive.set(baseColor).multiplyScalar(0.2);
        mat.emissiveIntensity = 1;
      } else {
        mat.color.set(baseColor);
        mat.opacity = 0.12;
        mat.emissive.set(0, 0, 0);
        mat.emissiveIntensity = 0;
      }
      mat.needsUpdate = false;
    }
  });

  return (
    <>
      {/* Architectural structure — walls, slabs, columns, etc. */}
      {archNodes.map(({ name, storeyId, cat, geom }) => {
        const visible = visibleStoreys.has(storeyId);
        if (!visible) return null;
        const mat = getArchMaterial(cat);
        // Fade non-selected storey slightly when filtering
        const opacity = state.currentStorey && storeyId !== state.currentStorey ? 0.15 : 1;

        return (
          <mesh
            key={name}
            geometry={geom}
            material={
              opacity < 1
                ? new THREE.MeshStandardMaterial({
                    ...mat,
                    transparent: true,
                    opacity,
                    color: (mat as THREE.MeshStandardMaterial).color,
                    roughness: (mat as THREE.MeshStandardMaterial).roughness,
                    metalness: (mat as THREE.MeshStandardMaterial).metalness,
                  })
                : mat
            }
            receiveShadow
            castShadow
          />
        );
      })}

      {/* Space volumes — interactive room geometry */}
      {spaceNodes.map(({ spaceId, storeyId, geom }) => {
        const visible = !state.currentStorey || storeyId === state.currentStorey;
        if (!visible) return null;
        const mat = getSpaceMaterial(spaceId, storeyId);

        return (
          <mesh
            key={spaceId}
            geometry={geom}
            material={mat}
            onPointerOver={(e) => {
              e.stopPropagation();
              state.onHover(spaceId);
              document.body.style.cursor = "pointer";
            }}
            onPointerOut={() => {
              state.onHover(null);
              document.body.style.cursor = "";
            }}
            onClick={(e) => {
              e.stopPropagation();
              state.onSelect(spaceId === state.selectedSpace ? null : spaceId);
            }}
          />
        );
      })}

      {/* Lighting */}
      <ambientLight intensity={0.55} />
      <directionalLight
        position={[60, 90, 40]}
        intensity={1.4}
        castShadow
        shadow-mapSize={[2048, 2048]}
      />
      <directionalLight position={[-40, 60, -30]} intensity={0.5} color="#9cc8e8" />
      <hemisphereLight args={["#8fb8de", "#1a2030", 0.35]} />
      <pointLight position={[0, 30, 0]} intensity={0.2} color="#38bdf8" />

      {/* Calculate bounding box centroid of selected room for camera targeting */}
      {(() => {
        let focusTarget: [number, number, number] | null = null;
        if (state.selectedSpace) {
          const node = spaceNodes.find((s) => s.spaceId === state.selectedSpace);
          if (node && node.geom) {
            if (!node.geom.boundingBox) {
              node.geom.computeBoundingBox();
            }
            if (node.geom.boundingBox) {
              const center = new THREE.Vector3();
              node.geom.boundingBox.getCenter(center);
              focusTarget = [center.x, center.y, center.z];
            }
          }
        }
        return (
          <CameraController
            resetTrigger={resetTrigger}
            fitTrigger={fitTrigger}
            focusTarget={focusTarget}
          />
        );
      })()}
    </>
  );
}

// ──────────────────────────────────────────────────────────────────
// Loading fallback while GLB streams
// ──────────────────────────────────────────────────────────────────

function TwinLoadingPlaceholder() {
  return (
    <mesh>
      <boxGeometry args={[0.001, 0.001, 0.001]} />
      <meshBasicMaterial transparent opacity={0} />
    </mesh>
  );
}

// ──────────────────────────────────────────────────────────────────
// TwinViewer — exported component
// ──────────────────────────────────────────────────────────────────

export function TwinViewer({
  manifest: externalManifest,
  currentStorey = null,
  selectedSpace = null,
  hoveredSpace = null,
  onSelect = () => {},
  onHover = () => {},
  externalResetTrigger = 0,
  externalFitTrigger = 0,
}: {
  manifest?: TwinManifest;
  currentStorey?: string | null;
  selectedSpace?: string | null;
  hoveredSpace?: string | null;
  onSelect?: (id: string | null) => void;
  onHover?: (id: string | null) => void;
  externalResetTrigger?: number;
  externalFitTrigger?: number;
}) {
  const [internalManifest, setInternalManifest] = useState<TwinManifest | null>(null);

  useEffect(() => {
    if (!externalManifest) {
      fetch("/models/twin_manifest.json")
        .then((r) => r.json())
        .then((d) => setInternalManifest(d))
        .catch(() => {});
    }
  }, [externalManifest]);

  const manifest = externalManifest ?? internalManifest;

  const [resetTrigger, setResetTrigger] = useState(0);
  const [fitTrigger, setFitTrigger] = useState(0);
  const [loadProgress, setLoadProgress] = useState<string>("Loading IFC geometry…");
  const [loaded, setLoaded] = useState(false);

  useEffect(() => {
    if (externalResetTrigger > 0) {
      setResetTrigger((v) => v + 1);
    }
  }, [externalResetTrigger]);

  useEffect(() => {
    if (externalFitTrigger > 0) {
      setFitTrigger((v) => v + 1);
    }
  }, [externalFitTrigger]);

  const state: SceneState = {
    currentStorey,
    selectedSpace,
    hoveredSpace,
    onSelect,
    onHover,
  };

  // Determine storey label
  const storeyLabel = useMemo(() => {
    if (!currentStorey) return "ALL FLOORS";
    const s = manifest?.storeys?.find((s) => s.storey_id === currentStorey);
    return formatStoreyName(s?.name);
  }, [currentStorey, manifest?.storeys]);

  if (!manifest) {
    return (
      <div style={{ height: "100%", display: "grid", placeItems: "center", background: "#060c14", color: "var(--color-ink-dim)", fontSize: "0.8rem" }}>
        Loading 3D IFC Building Model...
      </div>
    );
  }

  return (
    <div
      style={{
        position: "relative",
        width: "100%",
        height: "100%",
        minHeight: "450px",
        overflow: "hidden",
        borderRadius: "12px",
        border: "1px solid var(--color-line)",
        background: "#060c14",
        boxShadow: "inset 0 0 80px rgba(0,0,0,0.8), 0 0 0 1px rgba(56,189,248,0.05)",
      }}
    >
      <Canvas
        camera={{ position: [55, 38, 55], fov: 40, near: 0.5, far: 800 }}
        dpr={[1, 1.5]}
        shadows
        gl={{ antialias: true, alpha: false, powerPreference: "high-performance" }}
        onCreated={() => {
          setLoaded(true);
          setLoadProgress("DS3 TalTech Building — Real IFC Geometry");
        }}
      >
        <color attach="background" args={["#060c14"]} />
        <fog attach="fog" args={["#060c14", 200, 400]} />

        <Suspense fallback={<TwinLoadingPlaceholder />}>
          <TwinScene
            state={state}
            manifest={manifest}
            resetTrigger={resetTrigger}
            fitTrigger={fitTrigger}
          />
        </Suspense>
      </Canvas>

      {/* ── Top-left HUD ── */}
      <div
        style={{
          position: "absolute",
          top: "0.75rem",
          left: "0.75rem",
          pointerEvents: "none",
          display: "flex",
          alignItems: "center",
          gap: "0.5rem",
          background: "rgba(6,12,20,0.88)",
          backdropFilter: "blur(8px)",
          border: "1px solid rgba(56,189,248,0.15)",
          padding: "0.3rem 0.75rem",
          borderRadius: "7px",
          fontFamily: "var(--font-mono)",
          fontSize: "0.68rem",
          color: "var(--color-ink)",
        }}
      >
        <span
          style={{
            width: "6px",
            height: "6px",
            borderRadius: "50%",
            background: loaded ? "#34d399" : "#fbbf24",
            boxShadow: loaded ? "0 0 8px #34d39980" : "0 0 8px #fbbf2480",
            flexShrink: 0,
          }}
        />
        <span style={{ color: "var(--color-accent)", fontWeight: 600 }}>IFC</span>
        <span style={{ color: "var(--color-ink-dim)" }}>|</span>
        <span>{loadProgress}</span>
        <span style={{ color: "var(--color-ink-dim)" }}>|</span>
        <span style={{ color: storeyLabel === "ALL FLOORS" ? "var(--color-ink-dim)" : "var(--color-accent-3)" }}>
          {storeyLabel}
        </span>
      </div>

      {/* ── Bottom-left overlay HUD ── */}
      <div
        style={{
          position: "absolute",
          bottom: "0.75rem",
          left: "0.75rem",
          pointerEvents: "none",
          padding: "0.35rem 0.75rem",
          borderRadius: "6px",
          border: "1px solid rgba(30,47,66,0.6)",
          background: "rgba(6,12,20,0.85)",
          backdropFilter: "blur(6px)",
          fontFamily: "var(--font-mono)",
          fontSize: "0.72rem",
          color: "var(--color-ink-dim)",
          display: "flex",
          gap: "0.5rem",
          alignItems: "center",
        }}
      >
        <span>LMB Orbit</span>
        <span style={{ opacity: 0.4 }}>·</span>
        <span>RMB Pan</span>
        <span style={{ opacity: 0.4 }}>·</span>
        <span>Scroll Zoom</span>
        <span style={{ opacity: 0.4 }}>·</span>
        <span style={{ color: "var(--accent-cyan)", fontWeight: 600 }}>Click Room: Inspect</span>
      </div>

      {/* ── Hover tooltip ── */}
      {hoveredSpace && !selectedSpace && (
        <div
          style={{
            position: "absolute",
            bottom: "0.75rem",
            right: "0.75rem",
            pointerEvents: "none",
            padding: "0.375rem 0.75rem",
            borderRadius: "6px",
            border: "1px solid var(--color-accent)",
            background: "rgba(6,12,20,0.92)",
            backdropFilter: "blur(8px)",
            fontFamily: "var(--font-mono)",
            fontSize: "0.68rem",
            color: "var(--color-accent-3)",
          }}
        >
          {resolveSpaceDisplayName(hoveredSpace)}
        </div>
      )}
    </div>
  );
}