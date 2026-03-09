export type Severity = "P1" | "P2" | "P3" | "P4";

export type EventStatus =
  | "ignored"
  | "analysis_pending"
  | "analysis_in_progress"
  | "analysis_complete"
  | "analysis_failed";

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

export type StoredIncident = {
  id: string;
  event_id: string;
  service: string;
  environment: string;
  created_at: string;
  analysis: IncidentAnalysis;
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
  database_path: string;
};
