export type Severity = "P1" | "P2" | "P3" | "P4";

export type EventStatus =
  | "ignored"
  | "analysis_pending"
  | "analysis_in_progress"
  | "analysis_complete"
  | "analysis_failed";

export type IncidentStatus = "open" | "acknowledged" | "resolved";

export type Hypothesis = {
  rank: number;
  cause: string;
  confidence: number;
};

export type IncidentAnalysis = {
  severity: Severity;
  summary: string;
  user_impact: string[];
  hypotheses: Hypothesis[];
  suggested_actions: string[];
  slack_update: string;
  postmortem_draft: string;
  source: "gradient" | "fallback";
};

export type IncidentNote = {
  id: string;
  author: string;
  text: string;
  created_at: string;
};

export type StoredIncident = {
  id: string;
  event_id: string;
  service: string;
  environment: string;
  created_at: string;
  updated_at: string;
  resolved_at: string | null;
  status: IncidentStatus;
  notes: IncidentNote[];
  analysis: IncidentAnalysis;
};

export type IncidentDetail = StoredIncident & {
  related_incidents: StoredIncident[];
};

export type EventSummary = {
  id: string;
  service: string;
  environment: string;
  timestamp: string;
  status: EventStatus;
  last_error: string | null;
  signal_preview: string;
  log_count: number;
  incident_id: string | null;
  incident_severity: Severity | null;
  incident_summary: string | null;
};

export type EventDetail = {
  id: string;
  service: string;
  environment: string;
  timestamp: string;
  status: EventStatus;
  last_error: string | null;
  incident_id: string | null;
  incident_severity: Severity | null;
  incident_summary: string | null;
  log_entries: Array<{
    timestamp: string;
    message: string;
  }>;
};

export type HealthResponse = {
  ok: boolean;
  environment: string;
  gradient_enabled: boolean;
  slack_enabled: boolean;
  ingest_auth_enabled: boolean;
  database_path: string;
  database_ok: boolean;
  queue_depth: number;
  in_progress: number;
};

export type Paginated<K extends string, T> = { [key in K]: T[] } & {
  total: number;
  limit: number;
  offset: number;
};

export type SeriesPoint = {
  bucket: string;
  total: number;
  P1: number;
  P2: number;
  P3: number;
  P4: number;
};

export type MetricsSummary = {
  generated_at: string;
  window_hours: number;
  incidents_total: number;
  incidents_by_severity: Record<Severity, number>;
  incidents_by_status: Record<IncidentStatus, number>;
  events_by_status: Partial<Record<EventStatus, number>>;
  top_services: Array<{ service: string; environment: string; count: number }>;
  resolved_count: number;
  mean_time_to_resolve_sec: number | null;
  incidents_per_hour: SeriesPoint[];
};

export type IncidentFilters = {
  service?: string;
  environment?: string;
  severity?: Severity;
  status?: IncidentStatus;
};
