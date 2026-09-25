// Typed endpoint functions. Every endpoint needed by the UI lives here; pages
// never call fetch() directly.

import { request, qs } from "./client";
import type {
  AllocationRequest,
  AllocationResponse,
  AnomalyItem,
  BimDesignResponse,
  CampusSummary,
  DashboardSummary,
  DecisionCandidate,
  ForecastItem,
  HealthResponse,
  Page,
  Recommendation,
  RecommendationsResponse,
  ReplayHistoryResponse,
  ReplayState,
  ReplayStatus,
  ResourceStateResponse,
  SpaceListItem,
  TelemetrySummary,
} from "./types";

export interface FilterParams {
  limit?: number;
  offset?: number;
  severity?: string;
  measurement_type?: string;
  sensor_id?: string;
  location_status?: string;
  priority?: string;
  category?: string;
  problem_type?: string;
  storey_id?: string;
  horizon_hours?: number;
  candidate_type?: string;
  health_status?: string;
  min_capacity?: number;
  occupiable?: boolean;
}

export const api = {
  campus: () => request<CampusSummary>("/api/campus"),

  spaces: (p: FilterParams = {}) =>
    request<Page<SpaceListItem>>(
      `/api/spaces${qs({
        storey_id: p.storey_id,
        occupiable: p.occupiable,
        min_capacity: p.min_capacity,
        limit: p.limit,
        offset: p.offset,
      })}`,
    ),

  resources: (p: { limit?: number; offset?: number } = {}) =>
    request<ResourceStateResponse>(
      `/api/resources${qs({ limit: p.limit, offset: p.offset })}`,
    ),

  bimDesign: (spaceId: string) =>
    request<BimDesignResponse>(
      `/api/spaces/${encodeURIComponent(spaceId)}/bim-design`,
    ),

  telemetrySummary: () => request<TelemetrySummary>("/api/telemetry/summary"),

  anomalies: (p: FilterParams = {}) =>
    request<Page<AnomalyItem>>(
      `/api/anomalies${qs({
        severity: p.severity,
        measurement_type: p.measurement_type,
        sensor_id: p.sensor_id,
        location_status: p.location_status,
        limit: p.limit,
        offset: p.offset,
      })}`,
    ),

  forecasts: (p: FilterParams = {}) =>
    request<Page<ForecastItem>>(
      `/api/forecasts${qs({
        sensor_id: p.sensor_id,
        measurement_type: p.measurement_type,
        horizon_hours: p.horizon_hours,
        location_status: p.location_status,
        limit: p.limit,
        offset: p.offset,
      })}`,
    ),

  recommendations: (p: FilterParams = {}) =>
    request<RecommendationsResponse>(
      `/api/recommendations${qs({
        priority: p.priority,
        category: p.category,
        problem_type: p.problem_type,
        location_status: p.location_status,
        sensor_id: p.sensor_id,
        limit: p.limit,
        offset: p.offset,
      })}`,
    ),

  recommendation: (id: string) =>
    request<Recommendation>(`/api/recommendations/${encodeURIComponent(id)}`),

  health: (p: FilterParams = {}) =>
    request<HealthResponse>(
      `/api/health${qs({
        health_status: p.health_status,
        sensor_id: p.sensor_id,
        limit: p.limit,
        offset: p.offset,
      })}`,
    ),

  decisionCandidates: (p: FilterParams = {}) =>
    request<Page<DecisionCandidate>>(
      `/api/decision-candidates${qs({
        candidate_type: p.candidate_type,
        severity: p.severity,
        problem_type: p.problem_type,
        location_status: p.location_status,
        limit: p.limit,
        offset: p.offset,
      })}`,
    ),

  dashboard: () => request<DashboardSummary>("/api/dashboard/summary"),

  evaluateAllocation: (req: AllocationRequest) =>
    request<AllocationResponse>(
      "/api/allocation/evaluate",
      {
        method: "POST",
        body: JSON.stringify(req),
      },
    ),

  replayStatus: () => request<ReplayStatus>("/api/replay/status"),
  replayStart: () => request<ReplayStatus>("/api/replay/start", { method: "POST" }),
  replayPause: () => request<ReplayStatus>("/api/replay/pause", { method: "POST" }),
  replayReset: () => request<ReplayStatus>("/api/replay/reset", { method: "POST" }),
  replaySpeed: (speed: number) =>
    request<{ speed: number; running: boolean }>("/api/replay/speed", {
      method: "POST",
      body: JSON.stringify({ speed }),
    }),
  replayCurrent: () => request<ReplayState>("/api/replay/current"),
  replayHistory: (sensorId: string, measurementType: string, limit: number = 100) =>
    request<ReplayHistoryResponse>(
      `/api/replay/history${qs({
        sensor_id: sensorId,
        measurement_type: measurementType,
        limit,
      })}`,
    ),
};