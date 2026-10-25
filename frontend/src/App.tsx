import { useEffect, useMemo, useState } from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import {
  DayResponse,
  RunsResponse,
  SummaryResponse,
  fetchDay,
  fetchRuns,
  fetchSummary,
} from "./api";

const CUTOFFS = [
  { value: "09:50", label: "09:50 — Nord Pool N2EX day-ahead gate (default)" },
  { value: "11:00", label: "11:00 — EPEX SPOT day-ahead gate (sensitivity)" },
  { value: "17:30", label: "17:30 — Intraday IDA1 gate (sensitivity)" },
];

const JAN_DAYS: string[] = Array.from({ length: 31 }, (_, i) =>
  `2026-01-${String(i + 1).padStart(2, "0")}`,
);

type Tab = "overview" | "day" | "runs" | "method";

const fmt = (v: number | null | undefined, digits = 0): string =>
  v === null || v === undefined
    ? "—"
    : v.toLocaleString("en-GB", {
        minimumFractionDigits: digits,
        maximumFractionDigits: digits,
      });

const fmtTs = (iso: string | null): string =>
  iso ? iso.replace("T", " ").replace("Z", " UTC") : "—";

function Kpi(props: { label: string; value: string; hint: string; tone?: string }) {
  return (
    <div className="kpi">
      <div className="label">{props.label}</div>
      <div className={`value ${props.tone ?? ""}`}>{props.value}</div>
      <div className="hint">{props.hint}</div>
    </div>
  );
}

export default function App() {
  const [tab, setTab] = useState<Tab>("overview");
  const [cutoff, setCutoff] = useState("09:50");
  const [day, setDay] = useState("2026-01-15");
  const [summary, setSummary] = useState<SummaryResponse | null>(null);
  const [dayData, setDayData] = useState<DayResponse | null>(null);
  const [runsData, setRunsData] = useState<RunsResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    setLoading(true);
    setError(null);
    fetchSummary(cutoff)
      .then(setSummary)
      .catch((e: Error) => setError(e.message))
      .finally(() => setLoading(false));
  }, [cutoff]);

  useEffect(() => {
    fetchDay(day, cutoff)
      .then(setDayData)
      .catch((e: Error) => setError(e.message));
    fetchRuns(day, cutoff)
      .then(setRunsData)
      .catch((e: Error) => setError(e.message));
  }, [day, cutoff]);

  const dailyChart = useMemo(
    () =>
      (summary?.daily ?? []).map((d) => ({
        date: d.date.slice(5),
        MAE: d.mae,
      })),
    [summary],
  );

  const dayChart = useMemo(
    () =>
      (dayData?.hours ?? []).map((h) => ({
        hour: h.hourLabel,
        Actual: h.actual,
        "Decision forecast": h.forecast,
        "Latest-ever (leaky)": h.leakyForecast,
      })),
    [dayData],
  );

  const bucketChart = useMemo(
    () =>
      (summary?.leadBuckets ?? [])
        .filter((b) => b.n > 0)
        .map((b) => ({ bucket: b.bucket, MAE: b.mae, Bias: b.bias })),
    [summary],
  );

  const o = summary?.overall;
  const leaky = summary?.leakyOverall;

  return (
    <div className="app">
      <header className="hero">
        <span className="badge">Elexon BMRS only · FUELHH actuals + WINDFOR forecasts</span>
        <h1>Day-Ahead Wind Forecast: What You Knew, When You Had to Decide</h1>
        <p className="sub">
          For the day-ahead buying desk: the latest wind forecast genuinely available at the
          purchase deadline — and an honest, point-in-time measure of how accurate it was
          across January 2026 (delivery days 1–31 January, decisions taken on D-1).
        </p>
      </header>

      <div className="controls">
        <div className="control">
          <label htmlFor="cutoff">Decision deadline (D-1, UK time)</label>
          <select id="cutoff" value={cutoff} onChange={(e) => setCutoff(e.target.value)}>
            {CUTOFFS.map((c) => (
              <option key={c.value} value={c.value}>
                {c.label}
              </option>
            ))}
          </select>
        </div>
        <div className="control">
          <label htmlFor="daypick">Delivery day (Day Explorer &amp; Runs)</label>
          <select id="daypick" value={day} onChange={(e) => setDay(e.target.value)}>
            {JAN_DAYS.map((d) => (
              <option key={d} value={d}>
                {d}
              </option>
            ))}
          </select>
        </div>
      </div>

      <nav className="tabs">
        <button className={tab === "overview" ? "active" : ""} onClick={() => setTab("overview")}>
          Overview — January 2026
        </button>
        <button className={tab === "day" ? "active" : ""} onClick={() => setTab("day")}>
          Day Explorer
        </button>
        <button className={tab === "runs" ? "active" : ""} onClick={() => setTab("runs")}>
          Forecast Runs / Decision Timeline
        </button>
        <button className={tab === "method" ? "active" : ""} onClick={() => setTab("method")}>
          Method &amp; Accuracy
        </button>
      </nav>

      {error && (
        <div className="error-box">
          <strong>Could not load data from the API.</strong>
          <p>{error}</p>
          <p className="muted">
            Check the backend is running (default http://localhost:8000) or set VITE_API_BASE.
          </p>
        </div>
      )}
      {loading && <p className="muted">Loading January 2026 data…</p>}

      {tab === "overview" && summary && o && leaky && (
        <>
          <div className="kpis">
            <Kpi label="MAE (decision forecast)" value={`${fmt(o.mae)} MW`} tone="teal"
              hint="On average, the forecast you had to trade on missed actual wind output by this much each hour." />
            <Kpi label="RMSE" value={`${fmt(o.rmse)} MW`}
              hint="Like MAE but penalises big misses more — the gap vs MAE shows large errors matter here." />
            <Kpi label="Bias (forecast − actual)" value={`+${fmt(o.bias)} MW`} tone="red"
              hint="Strongly positive: the forecast systematically OVER-predicted wind. Wind shortfalls vs plan were the norm, not bad luck." />
            <Kpi label="Normalised MAE" value={o.nmae !== null ? `${(o.nmae * 100).toFixed(1)}%` : "—"}
              hint="MAE as a share of mean actual generation — comparable across months and fleets." />
            <Kpi label="Mean actual wind" value={`${fmt(o.meanActual)} MW`}
              hint={`Averaged over ${o.n} delivery hours in January 2026.`} />
            <Kpi label="Correlation" value={o.correlation !== null ? o.correlation.toFixed(2) : "—"} tone="amber"
              hint="The forecast tracked the shape of the day well — the problem is level (bias), not timing." />
          </div>

          <div className="panel trap">
            <h2>The look-ahead trap — why honest accuracy looks worse</h2>
            <p>
              Judged only on forecasts published <strong>before the {cutoff} D-1 deadline</strong>,
              January's MAE was <strong>{fmt(o.mae)} MW</strong>. If we cheat and grade the{" "}
              <em>latest forecast ever published</em> for each hour (including runs issued after —
              even during — the delivery day), MAE appears to improve to{" "}
              <strong>{fmt(leaky.mae)} MW</strong>.
            </p>
            <p>
              That improvement is an illusion: those later forecasts did not exist when the
              purchase decision had to be made. Any accuracy number that uses them flatters the
              forecast and would mislead the desk about the risk it actually carried. This app
              keeps the two strictly separate everywhere.
            </p>
          </div>

          <div className="panel">
            <h2>Daily MAE — decision forecast (MW)</h2>
            <p className="muted">Error varied enormously by day: calm, predictable days vs storm-driven misses.</p>
            <div className="chart-wrap">
              <ResponsiveContainer>
                <BarChart data={dailyChart}>
                  <CartesianGrid stroke="#24405f" />
                  <XAxis dataKey="date" stroke="#9db2c8" />
                  <YAxis stroke="#9db2c8" />
                  <Tooltip contentStyle={{ background: "#16263f", border: "1px solid #24405f" }} />
                  <Bar dataKey="MAE" fill="#2dd4bf" />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </div>

          <div className="panel">
            <h2>Worst days at decision time</h2>
            <ul className="tight">
              {summary.worstDays.map((d) => (
                <li key={d.date}>
                  <strong>{d.date}</strong> — MAE {fmt(d.mae)} MW, bias {d.bias !== null && d.bias >= 0 ? "+" : ""}
                  {fmt(d.bias)} MW against mean actual {fmt(d.meanActual)} MW.{" "}
                  <a href="#" onClick={(e) => { e.preventDefault(); setDay(d.date); setTab("day"); }}>
                    Inspect this day →
                  </a>
                </li>
              ))}
            </ul>
            <p className="muted">
              On the worst days the desk planned around several GW of wind that never arrived —
              replacement power had to be bought at short notice, typically at intraday prices.
            </p>
          </div>

          <div className="panel">
            <h2>Daily breakdown</h2>
            <table>
              <thead>
                <tr><th>Date</th><th>MAE (MW)</th><th>RMSE (MW)</th><th>Bias (MW)</th><th>Mean actual (MW)</th><th>Hours</th></tr>
              </thead>
              <tbody>
                {summary.daily.map((d) => (
                  <tr key={d.date} className={summary.worstDays.some((w) => w.date === d.date) ? "worst" : ""}>
                    <td>{d.date}</td><td>{fmt(d.mae)}</td><td>{fmt(d.rmse)}</td><td>{fmt(d.bias)}</td>
                    <td>{fmt(d.meanActual)}</td><td>{d.n}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}

      {tab === "day" && dayData && (
        <>
          <div className="kpis">
            <Kpi label={`Day MAE — ${dayData.date}`} value={`${fmt(dayData.summary.mae)} MW`} tone="teal"
              hint="Average hourly miss of the decision forecast for this delivery day." />
            <Kpi label="Day bias" value={`${dayData.summary.bias !== null && dayData.summary.bias >= 0 ? "+" : ""}${fmt(dayData.summary.bias)} MW`} tone="red"
              hint="Positive = wind over-forecast = shortfall vs plan = extra power to buy at short notice." />
            <Kpi label="Over-forecast hours" value={`${dayData.summary.overForecastHours} / ${dayData.summary.n}`}
              hint="Hours where forecast wind exceeded what actually generated." />
            <Kpi label="Net energy error" value={`${fmt(dayData.summary.cumulativeEnergyErrorGWh, 2)} GWh`}
              hint="Signed sum of hourly errors over the day (positive = planned wind that never arrived)." />
          </div>

          <div className="panel">
            <h2>Actual vs forecast you had to trade on — {dayData.date}</h2>
            <p className="muted">
              Decision deadline: {fmtTs(dayData.deadline)}. Every forecast point below comes from a
              run published before that deadline. The dashed line is the latest-ever forecast,
              shown only to expose the leakage gap — it was not available at decision time.
            </p>
            <div className="chart-wrap">
              <ResponsiveContainer>
                <LineChart data={dayChart}>
                  <CartesianGrid stroke="#24405f" />
                  <XAxis dataKey="hour" stroke="#9db2c8" />
                  <YAxis stroke="#9db2c8" />
                  <Tooltip contentStyle={{ background: "#16263f", border: "1px solid #24405f" }} />
                  <Legend />
                  <Line type="monotone" dataKey="Actual" stroke="#2dd4bf" strokeWidth={2.5} dot={false} />
                  <Line type="monotone" dataKey="Decision forecast" stroke="#f5a623" strokeWidth={2.5} dot={false} />
                  <Line type="monotone" dataKey="Latest-ever (leaky)" stroke="#9db2c8" strokeWidth={1.5} strokeDasharray="6 4" dot={false} />
                </LineChart>
              </ResponsiveContainer>
            </div>
            <p>
              <strong>How to read a shortfall:</strong> in any hour where the amber line sits above
              the teal line, the plan assumed more wind than arrived. The gap had to be covered by
              buying replacement power at short notice. Where amber sits below teal, there was
              surplus wind versus plan.
            </p>
          </div>

          <div className="panel">
            <h2>Hour by hour</h2>
            <table>
              <thead>
                <tr>
                  <th>Hour</th><th>Actual (MW)</th><th>Decision forecast (MW)</th>
                  <th>Forecast published</th><th>Lead (h)</th><th>Error (MW)</th><th>Error %</th>
                </tr>
              </thead>
              <tbody>
                {dayData.hours.map((h) => (
                  <tr key={h.hour}>
                    <td>{h.hourLabel}</td><td>{fmt(h.actual)}</td><td>{fmt(h.forecast)}</td>
                    <td>{fmtTs(h.publishTime)}</td><td>{h.leadHours ?? "—"}</td>
                    <td>{h.error !== null && h.error >= 0 ? "+" : ""}{fmt(h.error)}</td>
                    <td>{h.errorPct !== null && h.errorPct >= 0 ? "+" : ""}{h.errorPct ?? "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}

      {tab === "runs" && runsData && (
        <div className="panel">
          <h2>Decision timeline — delivery day {runsData.date}</h2>
          <p>
            WINDFOR is published roughly eight times a day (02:30, 04:30, 07:30, 09:30, 11:30,
            15:30, 18:30, 22:30 UTC). Only runs published <strong>before</strong> the gate could
            inform the purchase.
          </p>
          <div className="gate-line">
            ⏰ Decision gate: {fmtTs(runsData.deadline)} (cutoff {runsData.cutoff} on D-1) —
            selected run: {fmtTs(runsData.selectedPublishTime)}
          </div>
          <table>
            <thead>
              <tr><th>Forecast published</th><th>Hours covering this day</th><th>Available at decision time?</th><th>Used?</th></tr>
            </thead>
            <tbody>
              {runsData.runs.map((r) => (
                <tr key={r.publishTime} className={r.selected ? "selected-row" : r.eligible ? "" : "after-gate"}>
                  <td>{fmtTs(r.publishTime)}</td>
                  <td>{r.hoursCovered}</td>
                  <td>
                    {r.eligible
                      ? <span className="pill ok">Yes — before gate</span>
                      : <span className="pill no">No — after gate</span>}
                  </td>
                  <td>{r.selected ? <span className="pill sel">★ Selected decision forecast</span> : ""}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <p className="muted">
            At the default 09:50 gate the selected run is the 09:30 D-1 publication — giving lead
            times of 14.5 hours for the 00:00 delivery hour up to 37.5 hours for 23:00.
          </p>
        </div>
      )}

      {tab === "method" && summary && (
        <>
          <div className="panel">
            <h2>Metric definitions</h2>
            <ul className="tight">
              <li><strong>Error</strong> per hour: <span className="formula">e = forecast − actual</span> (MW). Positive = over-forecast.</li>
              <li><strong>MAE</strong>: <span className="formula">mean(|e|)</span> — average size of the miss, direction ignored.</li>
              <li><strong>RMSE</strong>: <span className="formula">sqrt(mean(e²))</span> — penalises large misses; RMSE ≥ MAE always.</li>
              <li><strong>Bias</strong>: <span className="formula">mean(e)</span> — systematic direction. January's large positive bias is the headline risk.</li>
              <li><strong>nMAE</strong>: <span className="formula">MAE / mean(actual)</span> — scale-free accuracy.</li>
              <li><strong>MAPE</strong>: <span className="formula">mean(|e| / actual) × 100%</span> — percentage miss per hour.</li>
              <li><strong>Correlation</strong>: Pearson correlation between forecast and actual — shape agreement, blind to bias.</li>
              <li><strong>Cumulative energy error</strong>: <span className="formula">Σe × 1 h / 1000</span> in GWh — net planned-but-undelivered wind energy.</li>
            </ul>
          </div>

          <div className="panel">
            <h2>Accuracy by forecast lead time</h2>
            <p className="muted">
              Lead time = hours between the selected run's publication and the delivery hour.
              Longer leads are expected to be less accurate — the table shows how much of
              January's error is a lead-time effect versus a level (bias) effect.
            </p>
            <div className="chart-wrap">
              <ResponsiveContainer>
                <BarChart data={bucketChart}>
                  <CartesianGrid stroke="#24405f" />
                  <XAxis dataKey="bucket" stroke="#9db2c8" />
                  <YAxis stroke="#9db2c8" />
                  <Tooltip contentStyle={{ background: "#16263f", border: "1px solid #24405f" }} />
                  <Legend />
                  <Bar dataKey="MAE" fill="#2dd4bf" />
                  <Bar dataKey="Bias" fill="#f5a623" />
                </BarChart>
              </ResponsiveContainer>
            </div>
            <table>
              <thead>
                <tr><th>Lead bucket</th><th>Hours</th><th>Mean lead (h)</th><th>MAE (MW)</th><th>RMSE (MW)</th><th>Bias (MW)</th></tr>
              </thead>
              <tbody>
                {summary.leadBuckets.map((b) => (
                  <tr key={b.bucket}>
                    <td>{b.bucket}</td><td>{b.n}</td><td>{b.meanLeadHours ?? "—"}</td>
                    <td>{fmt(b.mae)}</td><td>{fmt(b.rmse)}</td><td>{fmt(b.bias)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <div className="panel">
            <h2>Method, assumptions &amp; caveats</h2>
            <ul className="tight">
              <li><strong>Scope interpretation:</strong> "purchase decisions in January 2026" = delivery days 1–31 January 2026, each decided on D-1. Documented here and in the README.</li>
              <li><strong>Point-in-time rule:</strong> the decision forecast for a delivery day is, per hour, the forecast with the greatest publishTime strictly before the deadline (default 09:50 on D-1 — the Nord Pool N2EX GB day-ahead auction gate closure). Forecasts published after the deadline are never used in the decision view.</li>
              <li><strong>Resolution alignment:</strong> WINDFOR is hourly; FUELHH is half-hourly. Each hourly actual is the mean of the two half-hours starting at :00 and :30. Every January hour has exactly two half-hourly records (744 hours).</li>
              <li><strong>Timezones:</strong> January in the UK is GMT, so UK time = UTC; no DST adjustment is needed for this month.</li>
              <li><strong>Scope caveat (to investigate, not a proven claim):</strong> WINDFOR may cover a wider wind scope than the transmission-metered wind in FUELHH. If so, part of the systematic positive bias could be a coverage difference rather than pure forecast error. This app reports the numbers as published; reconciling the two scopes is a recommended follow-up.</li>
              <li><strong>Data sources (Elexon BMRS only):</strong>{" "}
                <a href="https://data.elexon.co.uk/bmrs/api/v1/datasets/FUELHH/stream" target="_blank" rel="noreferrer">FUELHH stream</a>{" · "}
                <a href="https://data.elexon.co.uk/bmrs/api/v1/datasets/WINDFOR/stream" target="_blank" rel="noreferrer">WINDFOR stream</a>
              </li>
              <li><strong>Reproducibility:</strong> the backend bundles a snapshot of the exact January 2026 data used, so every number on this page can be reproduced offline.</li>
            </ul>
          </div>
        </>
      )}

      <footer>
        Data: Elexon BMRS (FUELHH + WINDFOR) only. Data source for current view:{" "}
        {summary?.dataSource ?? dayData?.dataSource ?? "—"}. Built with React + FastAPI.
        AI-tools disclosure: built with assistance from an AI coding assistant (Muse) — see README.
      </footer>
    </div>
  );
}
