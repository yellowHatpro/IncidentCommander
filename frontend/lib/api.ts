import type {
  EventDetail,
  EventSummary,
  HealthResponse,
  IncidentDetail,
  IncidentFilters,
  IncidentStatus,
  MetricsSummary,
  Paginated,
  StoredIncident,
} from "./types";

type ApiResult<T> = { ok: true; data: T } | { ok: false; error: string };

export class ApiError extends Error {
  constructor(
    message: string,
    public readonly status: number,
  ) {
    super(message);
  }
}

export function getApiBaseUrl() {
  return (
    process.env.API_BASE_URL ??
    process.env.NEXT_PUBLIC_API_BASE_URL ??
    "http://127.0.0.1:8000"
  );
}

function writeHeaders(): Record<string, string> {
  // Server-only: forwarded to the FastAPI write endpoints when INGEST_API_KEY is set.
  const key = process.env.INGEST_API_KEY;
  return key ? { "X-API-Key": key } : {};
}

async function fetchJson<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${getApiBaseUrl()}${path}`, {
    cache: "no-store",
    ...init,
    headers: {
      Accept: "application/json",
      ...(init?.body ? { "Content-Type": "application/json" } : {}),
      ...(init?.headers ?? {}),
    },
  });

  if (!response.ok) {
    let detail = response.statusText;
    try {
      const body = (await response.json()) as { detail?: string };
      if (body.detail) detail = body.detail;
    } catch {
      // keep statusText
    }
    throw new ApiError(`Request failed for ${path}: ${response.status} ${detail}`, response.status);
  }

  return (await response.json()) as T;
}

function toQuery(params: Record<string, string | number | undefined>) {
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== "") search.set(key, String(value));
  }
  const text = search.toString();
  return text ? `?${text}` : "";
}

async function wrap<T>(work: () => Promise<T>): Promise<ApiResult<T>> {
  try {
    return { ok: true, data: await work() };
  } catch (error) {
    return { ok: false, error: error instanceof Error ? error.message : "Unknown API error" };
  }
}

export function fetchDashboardData(filters: IncidentFilters = {}) {
  return wrap(async () => {
    const [health, incidentsPayload, eventsPayload, metrics] = await Promise.all([
      fetchJson<HealthResponse>("/health"),
      fetchJson<Paginated<"incidents", StoredIncident>>(`/incidents${toQuery({ limit: 50, ...filters })}`),
      fetchJson<Paginated<"events", EventSummary>>(
        `/events${toQuery({ limit: 50, service: filters.service, environment: filters.environment })}`,
      ),
      fetchJson<MetricsSummary>("/metrics/summary?window_hours=24"),
    ]);

    return {
      health,
      incidents: incidentsPayload.incidents,
      incidentsTotal: incidentsPayload.total,
      events: eventsPayload.events,
      eventsTotal: eventsPayload.total,
      metrics,
    };
  });
}

export function fetchIncidentDetail(incidentId: string) {
  return wrap(async () => {
    const incident = await fetchJson<IncidentDetail>(`/incidents/${incidentId}`);
    const event = await fetchJson<EventDetail>(`/events/${incident.event_id}`);
    return { incident, event };
  });
}

export function fetchEventDetail(eventId: string) {
  return wrap(async () => ({ event: await fetchJson<EventDetail>(`/events/${eventId}`) }));
}

export function updateIncidentStatus(incidentId: string, status: IncidentStatus) {
  return fetchJson<StoredIncident>(`/incidents/${incidentId}/status`, {
    method: "PATCH",
    body: JSON.stringify({ status }),
    headers: writeHeaders(),
  });
}

export function addIncidentNote(incidentId: string, author: string, text: string) {
  return fetchJson<StoredIncident>(`/incidents/${incidentId}/notes`, {
    method: "POST",
    body: JSON.stringify({ author, text }),
    headers: writeHeaders(),
  });
}

export function postmortemUrl(incidentId: string) {
  // Browser-reachable base: the public URL wins over the server-side one.
  const base = process.env.NEXT_PUBLIC_API_BASE_URL ?? getApiBaseUrl();
  return `${base}/incidents/${incidentId}/postmortem.md`;
}
