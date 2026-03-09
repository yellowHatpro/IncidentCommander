import type { EventDetail, EventSummary, HealthResponse, StoredIncident } from "./types";

type ApiResult<T> = { ok: true; data: T } | { ok: false; error: string };

function getApiBaseUrl() {
  return (
    process.env.API_BASE_URL ??
    process.env.NEXT_PUBLIC_API_BASE_URL ??
    "http://127.0.0.1:8000"
  );
}

async function fetchJson<T>(path: string): Promise<T> {
  const response = await fetch(`${getApiBaseUrl()}${path}`, {
    cache: "no-store",
    headers: {
      Accept: "application/json",
    },
  });

  if (!response.ok) {
    throw new Error(`Request failed for ${path}: ${response.status} ${response.statusText}`);
  }

  return (await response.json()) as T;
}

export async function fetchDashboardData(): Promise<
  ApiResult<{
    health: HealthResponse;
    incidents: StoredIncident[];
    events: EventSummary[];
  }>
> {
  try {
    const [health, incidentsPayload, eventsPayload] = await Promise.all([
      fetchJson<HealthResponse>("/health"),
      fetchJson<{ incidents: StoredIncident[] }>("/incidents"),
      fetchJson<{ events: EventSummary[] }>("/events"),
    ]);

    return {
      ok: true,
      data: {
        health,
        incidents: incidentsPayload.incidents,
        events: eventsPayload.events,
      },
    };
  } catch (error) {
    return {
      ok: false,
      error: error instanceof Error ? error.message : "Unknown API error",
    };
  }
}

export async function fetchIncidentDetail(
  incidentId: string,
): Promise<ApiResult<{ incident: StoredIncident; event: EventDetail }>> {
  try {
    const incident = await fetchJson<StoredIncident>(`/incidents/${incidentId}`);
    const event = await fetchJson<EventDetail>(`/events/${incident.event_id}`);
    return { ok: true, data: { incident, event } };
  } catch (error) {
    return {
      ok: false,
      error: error instanceof Error ? error.message : "Unknown API error",
    };
  }
}

export async function fetchEventDetail(
  eventId: string,
): Promise<ApiResult<{ event: EventDetail }>> {
  try {
    const event = await fetchJson<EventDetail>(`/events/${eventId}`);
    return { ok: true, data: { event } };
  } catch (error) {
    return {
      ok: false,
      error: error instanceof Error ? error.message : "Unknown API error",
    };
  }
}
