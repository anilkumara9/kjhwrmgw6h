const API_BASE: string =
  (import.meta as unknown as { env: Record<string, string | undefined> }).env
    .VITE_API_BASE ?? "http://localhost:8000";

export interface Metrics {
  n: number;
  mae: number | null;
  rmse: number | null;
  bias: number | null;
  nmae: number | null;
  mape: number | null;
  correlation: number | null;
  meanActual: number | null;
  meanForecast: number | null;
  overForecastHours: number;
  underForecastHours: number;
  exactHours: number;
  cumulativeEnergyErrorGWh: number;
}

export interface DailyRow {
  date: string;
  mae: number | null;
  rmse: number | null;
  bias: number | null;
  meanActual: number | null;
  n: number;
  correlation: number | null;
}

export interface LeadBucket {
  bucket: string;
  n: number;
  mae: number | null;
  rmse: number | null;
  bias: number | null;
  meanLeadHours: number | null;
}

export interface SummaryResponse {
  cutoff: string;
  period: { from: string; to: string; days: number };
  overall: Metrics;
  leakyOverall: Metrics;
  daily: DailyRow[];
  leadBuckets: LeadBucket[];
  worstDays: DailyRow[];
  bestDays: DailyRow[];
  dataSource?: string;
}

export interface HourRow {
  hour: string;
  hourLabel: string;
  actual: number | null;
  forecast: number | null;
  publishTime: string | null;
  leadHours: number | null;
  error: number | null;
  errorPct: number | null;
  leakyForecast: number | null;
  leakyPublishTime: string | null;
  leakyError: number | null;
}

export interface DayResponse {
  date: string;
  cutoff: string;
  deadline: string;
  hours: HourRow[];
  summary: Metrics;
  leakySummary: Metrics;
  dataSource?: string;
}

export interface RunRow {
  publishTime: string;
  hoursCovered: number;
  eligible: boolean;
  selected: boolean;
}

export interface RunsResponse {
  date: string;
  cutoff: string;
  deadline: string;
  selectedPublishTime: string | null;
  runs: RunRow[];
  dataSource?: string;
}

async function getJson<T>(path: string): Promise<T> {
  const resp = await fetch(`${API_BASE}${path}`);
  if (!resp.ok) {
    const body = await resp.text();
    throw new Error(`API ${resp.status}: ${body}`);
  }
  return (await resp.json()) as T;
}

export const fetchSummary = (cutoff: string) =>
  getJson<SummaryResponse>(`/api/summary?cutoff=${encodeURIComponent(cutoff)}`);
export const fetchDay = (date: string, cutoff: string) =>
  getJson<DayResponse>(`/api/day/${date}?cutoff=${encodeURIComponent(cutoff)}`);
export const fetchRuns = (date: string, cutoff: string) =>
  getJson<RunsResponse>(`/api/runs/${date}?cutoff=${encodeURIComponent(cutoff)}`);
