import { existsSync, readFileSync } from "node:fs";
import path from "node:path";
import type {
  DemoSeedResult,
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

export type ApiFailure = {
  ok: false;
  error: string;
  /** True when the backend did not answer at all (not running, wrong port, refused). */
  unreachable: boolean;
  api: ApiBase;
};

type ApiResult<T> = { ok: true; data: T } | ApiFailure;

export class ApiError extends Error {
  constructor(
    message: string,
    public readonly status: number,
  ) {
    super(message);
  }
}

export class ApiUnreachableError extends Error {
  constructor(
    public readonly api: ApiBase,
    cause: unknown,
  ) {
    super(`The API did not answer at ${api.url} (${describeCause(cause)}).`);
  }
}

export type ApiBase = {
  url: string;
  /** Where the URL came from, shown on the setup screen. */
  source: "API_BASE_URL" | "NEXT_PUBLIC_API_BASE_URL" | "data/api-url" | "default";
};

const DEFAULT_API_URL = "http://127.0.0.1:8000";
const REQUEST_TIMEOUT_MS = 10_000;

function readApiUrlFile(): string | null {
  // `python -m api` writes the port it actually bound to here (the frontend runs
  // from frontend/ in dev and from the repo root in some deployments).
  for (const candidate of [path.join(process.cwd(), "..", "data", "api-url"), path.join(process.cwd(), "data", "api-url")]) {
    try {
      if (existsSync(candidate)) {
        const value = readFileSync(candidate, "utf8").trim();
        if (/^https?:\/\//.test(value)) return value;
      }
    } catch {
      // unreadable file: fall through to the default
    }
  }
  return null;
}

function stripTrailingSlash(url: string) {
  return url.replace(/\/+$/, "");
}

export function describeApiBase(): ApiBase {
  if (process.env.API_BASE_URL) return { url: stripTrailingSlash(process.env.API_BASE_URL), source: "API_BASE_URL" };
  if (process.env.NEXT_PUBLIC_API_BASE_URL) {
    return { url: stripTrailingSlash(process.env.NEXT_PUBLIC_API_BASE_URL), source: "NEXT_PUBLIC_API_BASE_URL" };
  }
  const discovered = readApiUrlFile();
  if (discovered) return { url: stripTrailingSlash(discovered), source: "data/api-url" };
  return { url: DEFAULT_API_URL, source: "default" };
}

export function getApiBaseUrl() {
  return describeApiBase().url;
}

function describeCause(cause: unknown): string {
  if (cause instanceof Error) {
    const inner = (cause as Error & { cause?: unknown }).cause;
    if (inner instanceof Error && inner.message) return inner.message;
    if (cause.name === "TimeoutError") return `no response within ${REQUEST_TIMEOUT_MS / 1000}s`;
    return cause.message;
  }
  return String(cause);
}

function writeHeaders(): Record<string, string> {
  // Server-only: forwarded to the FastAPI write endpoints when INGEST_API_KEY is set.
  const key = process.env.INGEST_API_KEY;
  return key ? { "X-API-Key": key } : {};
}

async function fetchJson<T>(path: string, init?: RequestInit): Promise<T> {
  const api = describeApiBase();
  let response: Response;
  try {
    response = await fetch(`${api.url}${path}`, {
      cache: "no-store",
      signal: AbortSignal.timeout(REQUEST_TIMEOUT_MS),
      ...init,
      headers: {
        Accept: "application/json",
        ...(init?.body ? { "Content-Type": "application/json" } : {}),
        ...(init?.headers ?? {}),
      },
    });
  } catch (error) {
    throw new ApiUnreachableError(api, error);
  }

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
    if (error instanceof ApiUnreachableError) {
      return { ok: false, error: error.message, unreachable: true, api: error.api };
    }
    return {
      ok: false,
      error: error instanceof Error ? error.message : "Unknown API error",
      unreachable: false,
      api: describeApiBase(),
    };
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

export function seedDemoData(limit = 12) {
  return fetchJson<DemoSeedResult>(`/demo/seed?limit=${limit}`, {
    method: "POST",
    headers: writeHeaders(),
  });
}

export function postmortemUrl(incidentId: string) {
  // Browser-reachable base: the public URL wins over the server-side one.
  const base = process.env.NEXT_PUBLIC_API_BASE_URL ?? getApiBaseUrl();
  return `${base}/incidents/${incidentId}/postmortem.md`;
}
