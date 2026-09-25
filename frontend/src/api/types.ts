// CampusIQ product API response types.
// These mirror the actual FastAPI response shapes (scripts/api_app.py). Do
// not invent fields; "unknown" states come back as null/missing from the API.

export interface Page<T> {
  items: T[];
  total: number;
  limit: number;
  offset: number;
}

// GET /api/campus
export interface CampusSummary {
  campus: { campus_id: string | null; name: string | null };
  buildings: Array<{
    building_id: string;
    name: string;
    space_count: number;
    storey_ids: string[];
  }>;
  storeys: Array<{ storey_id: string; name: string | null; space_count: number }>;
  building_count: number;
  storey_count: number;
}

// GET /api/spaces
export interface SpaceListItem {
  space_id: string;
  building_id: string | null;
  storey_id: string | null;
  area_m2: number | null;
  volume_m3: number | null;
  capacity_occupants: number | null;
  occupiable: boolean;
  conditioning: string | null;
}

// GET /api/resources
export interface ResourceSummary {
  building_count: number;
  space_count: number;
  storey_count: number;
  storey_count_registry: number;
  occupiable_count: number;
  total_area_m2: number;
  total_volume_m3: number;
  total_capacity_occupants: number;
  [key: string]: unknown;
}

export interface ResourceStateResponse {
  summary: ResourceSummary;
  availability?: {
    present: boolean;
    [key: string]: unknown;
  };
  design_metrics?: { metric_origin: string } | null;
  storeys?: Array<Record<string, unknown>>;
  items: Array<{
    space_id: string;
    area_m2: number | null;
    capacity_occupants: number | null;
    metric_origin: string | null;
  }>;
  total: number;
  limit: number;
  offset: number;
}

// GET /api/telemetry/summary
export interface TelemetrySummary {
  dataset: {
    devices: number;
    channels: number;
    total_readings: number;
    channels_by_type: Record<string, number>;
    time_span: { first: string; last: string } | null;
    [key: string]: unknown;
  };
  intelligence: {
    anomalies: {
      total_candidates: number;
      recorded_detail: number;
      channels_with_anomalies: number;
      by_severity: Record<string, number>;
      by_measurement_type: Record<string, number>;
      [key: string]: unknown;
    };
  };
  sensor_count: number;
  generated_at: string;
}

// GET /api/anomalies (slim projection)
export interface AnomalyItem {
  sensor_id: string;
  timestamp: string;
  measurement_type: string;
  unit: string | null;
  value: number | null;
  expected: number | null;
  deviation: number | null;
  score: number | null;
  severity: string | null;
  category: string | null;
  method: string | null;
  persistence: number | null;
  location_status: string | null;
}

// GET /api/forecasts
export interface ForecastItem {
  sensor_id: string;
  measurement_type: string;
  unit: string | null;
  as_of_timestamp: string;
  forecast_timestamp: string;
  horizon_hours: number;
  predicted_value: number | null;
  baseline_value: number | null;
  prediction_method: string;
  location_status: string | null;
  confidence_interval_95: unknown;
  coverage?: {
    confidence_intervals_calculated: boolean;
    recent_sample_count: number;
    seasonal_bucket_sample_count: number;
    seasonal_spread_estimate: number | null;
    total_history_samples: number;
  } | null;
}

// GET /api/decision-candidates
export interface DecisionCandidate {
  candidate_id: string;
  candidate_type: string;
  problem_type: string;
  source: string;
  severity: string;
  affected_entity: { type: string; sensor_id?: string; space_id?: string };
  proposed_action: string;
  reason: string;
  evidence: Record<string, unknown>;
  constraints: string[];
  location_status: string;
  location: { status: string; space_id: string | null };
  confidence: number | null;
}

// GET /api/recommendations and /api/recommendations/{id}
export interface Recommendation {
  recommendation_id: string;
  candidate_id: string;
  priority: string;
  priority_score: number;
  priority_factors: Record<string, number>;
  ranking: {
    priority_score: number;
    weights: Record<string, number>;
    factors: Record<string, number>;
    factor_basis: Record<string, string>;
    formula_version: string;
    explanation: string;
  };
  recommendation_category: string;
  problem_type: string;
  source: string;
  affected_entity: { type: string; sensor_id?: string; space_id?: string };
  location_status: string;
  location: { status: string; space_id: string | null };
  recommended_action: string;
  reason: string;
  evidence: Record<string, unknown>;
  evidence_chain: Array<{
    step: string;
    entity: string | null;
    value: unknown;
    note: string;
  }>;
  constraints: string[];
  expected_impact: Array<{
    type: string;
    value: number | null;
    unit: string | null;
    status: string;
    method: string | null;
    reason: string;
  }>;
  confidence: { value: number | null; basis: string };
  data_quality: Record<string, unknown>;
}

export interface RecommendationsResponse extends Page<Recommendation> {
  generated_at: string;
  data_status: { sensor_location_mapping: string };
}

// GET /api/health
export interface HealthItem {
  sensor_id: string;
  health_status: string;
  coverage_fraction: number | null;
  missing_ratio: number | null;
  valid_readings: number | null;
  missing_readings: number | null;
  issues: Array<{ type: string; max_severity?: string }>;
}

export interface HealthResponse extends Page<HealthItem> {
  summary?: {
    devices?: number;
    healthy?: number;
    degraded?: number;
    overall?: string;
    [key: string]: unknown;
  };
}

// POST /api/allocation/evaluate request + response
export interface AllocationRequest {
  required_capacity: number;
  equipment?: string[];
  availability?: Record<string, boolean> | null;
  request_id?: string | null;
}

export interface AllocationSpaceResult {
  space_id: string;
  capacity_occupants: number | null;
  occupiable: boolean;
  availability_known: boolean;
  capacity_suitable?: boolean;
  equipment_status?: string;
  unverified_equipment?: string[];
  reason_qualified?: string[];
  reason_excluded?: string[];
}

export interface AllocationResponse {
  schema_version: string;
  request_id: string | null;
  required_capacity: number;
  equipment: string[];
  equipment_status?: {
    status: string;
    verified_items: string[];
    unverified_items: string[];
    note: string;
  };
  availability: {
    present: boolean;
    declared_space_count: number;
    note: string;
  };
  summary_counts?: {
    total_evaluated: number;
    capacity_matches: number;
    equipment_verified: number;
    unverified_equipment_matches: number;
    excluded: number;
  };
  qualified: AllocationSpaceResult[];
  excluded: AllocationSpaceResult[];
  satisfied: boolean;
  exclusion_reasons: string[];
  note: string;
  generated_at: string;
}

// GET /api/spaces/{space_id}/bim-design
export interface BimDesignResponse {
  space_id: string;
  origin: "IFC_DESIGN";
  measured: false;
  note: string;
  space: {
    ifc_name: string | null;
    storey_id: string | null;
    area_m2: number | null;
    volume_m3: number | null;
    height_m: number | null;
    capacity_occupants: number | null;
    occupiable: boolean | null;
  };
  design: Record<string, number>;
  conditioning: string | null;
}

// GET /api/dashboard/summary
export interface DashboardSummary {
  campus: {
    campus_id: string | null;
    campus_name?: string | null;
    building_count: number;
    storey_count: number | null;
    space_count: number | null;
  };
  telemetry: {
    sensor_count: number | null;
    channel_count: number | null;
    total_readings: number | null;
    channels_by_type: Record<string, number> | null;
    time_span: { first: string; last: string } | null;
  };
  anomalies: {
    channels_with_anomalies: number | null;
    by_severity: Record<string, number>;
    high_critical_total: number;
  };
  decision_candidates: {
    total: number | null;
    by_severity: Record<string, number>;
    high_critical_total: number;
  };
  sensor_health: {
    devices: number | null;
    healthy: number | null;
    degraded: number | null;
    status: string | null;
  };
  forecasts: {
    channels_forecasted: number | null;
    channels_total: number | null;
    available: boolean;
  };
  recommendations: {
    total: number | null;
    by_priority: Record<string, number>;
  };
  mapping: {
    total: number | null;
    resolved: number | null;
    confirmed: number | null;
    provisional: number | null;
    unresolved: number | null;
    verified_locations: number | null;
    status: string;
  };
  data_status: {
    sensor_location_mapping: string;
    availability_present: boolean;
    measured_energy_available: boolean;
    recommendation_records: number | null;
  };
  generated_at: string;
}

// ── Replay / Simulation Types ──────────────────────────────────────────────────

export interface ReplayStatus {
  running: boolean;
  speed: number;
  sim_timestamp: string;
  readings_replayed: number;
  anomalies_detected: number;
  channels_active: number;
}

export interface ReplayChannel {
  sensor_id: string;
  measurement_type: string;
  unit: string;
  value: number;
  timestamp: string;
  baseline_mean?: number | null;
  baseline_std?: number | null;
  z_score?: number | null;
  severity?: "WARN" | "HIGH" | "CRITICAL" | null;
  location_status: string;
}

export interface ReplayState {
  sim_timestamp: string;
  running: boolean;
  speed: number;
  readings_replayed: number;
  anomalies_detected: number;
  channels: ReplayChannel[];
  summaries: Record<string, { count: number; mean: number; min: number; max: number }>;
  active_anomalies: ReplayChannel[];
  location_note: string;
}

export interface ReplayHistoryItem {
  ts: string;
  value: number;
}

export interface ReplayHistoryResponse {
  sensor_id: string;
  measurement_type: string;
  count: number;
  history: ReplayHistoryItem[];
}