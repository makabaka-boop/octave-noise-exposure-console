import { useState } from "react";

const FREQUENCIES = [63, 125, 250, 500, 1000, 2000, 4000, 8000];
const MAX_PERIODS = 24;

// Two plausible shop-floor periods so the page demonstrates a full
// exceedance conclusion out of the box.
const DEFAULT_PERIODS = [
  {
    duration: "1200",
    bands: { 63: "78", 125: "80", 250: "82", 500: "84", 1000: "85", 2000: "83", 4000: "80", 8000: "75" },
  },
  {
    duration: "600",
    bands: { 63: "85", 125: "88", 250: "90", 500: "92", 1000: "94", 2000: "95", 4000: "90", 8000: "84" },
  },
];

function blankPeriod() {
  return { duration: "", bands: Object.fromEntries(FREQUENCIES.map((f) => [f, ""])) };
}

// Empty inputs are omitted so the backend sees a genuinely incomplete
// request and answers 422 — the page never pre-validates or computes.
function buildPayload(limit, periods) {
  const body = {
    periods: periods.map((p) => {
      const period = { bands: {} };
      if (p.duration !== "") period.duration = Number(p.duration);
      for (const f of FREQUENCIES) {
        if (p.bands[f] !== "") period.bands[f] = Number(p.bands[f]);
      }
      return period;
    }),
  };
  if (limit !== "") body.limit = Number(limit);
  return body;
}

function formatValidationErrors(detail) {
  if (!Array.isArray(detail)) return ["请求被拒绝（422），但无法解析错误详情。"];
  return detail.map((e) => {
    const loc = Array.isArray(e.loc) ? e.loc.filter((p) => p !== "body").join(" → ") : "";
    return loc ? `${loc}: ${e.msg}` : e.msg;
  });
}

export default function App() {
  const [limit, setLimit] = useState("85");
  const [periods, setPeriods] = useState(DEFAULT_PERIODS);
  const [result, setResult] = useState(null);
  const [errors, setErrors] = useState(null);
  const [submitting, setSubmitting] = useState(false);

  const updatePeriod = (i, patch) =>
    setPeriods(periods.map((p, j) => (j === i ? { ...p, ...patch } : p)));

  const addPeriod = () => setPeriods([...periods, blankPeriod()]);
  const removePeriod = (i) => setPeriods(periods.filter((_, j) => j !== i));

  async function onSubmit(event) {
    event.preventDefault();
    setSubmitting(true);
    try {
      const res = await fetch("/api/assessments", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(buildPayload(limit, periods)),
      });
      if (res.status === 422) {
        // Invalid input: the whole assessment is rejected and any stale
        // conclusion must disappear.
        setResult(null);
        const body = await res.json().catch(() => null);
        setErrors(formatValidationErrors(body && body.detail));
        return;
      }
      if (!res.ok) {
        setResult(null);
        setErrors([`请求失败（HTTP ${res.status}）。`]);
        return;
      }
      setErrors(null);
      setResult(await res.json());
    } catch (err) {
      setResult(null);
      setErrors([`无法连接计算服务：${err.message}`]);
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <main className="page">
      <h1>车间噪声暴露巡检工作台</h1>
      <p className="hint">
        每个时段填写持续时间（1–3600 秒整数）与 63–8000 Hz 八个倍频带声级（0–140 dB）。
        后端按固定 A 计权将各频带换算为能量，再按持续时间合成总 LAeq；判定使用未舍入值，显示值保留一位小数。
      </p>

      <form onSubmit={onSubmit}>
        <fieldset className="limit">
          <label htmlFor="limit">暴露限值 LAeq 限值（40–100 dB(A)）</label>
          <input
            id="limit"
            type="number"
            min="40"
            max="100"
            step="any"
            value={limit}
            onChange={(e) => setLimit(e.target.value)}
          />
        </fieldset>

        {periods.map((period, i) => (
          <fieldset className="period" key={i} data-testid={`period-${i + 1}`}>
            <legend>
              时段 {i + 1}
              <button
                type="button"
                className="remove"
                onClick={() => removePeriod(i)}
                disabled={periods.length <= 1}
              >
                删除
              </button>
            </legend>
            <label className="duration">
              持续时间（秒）
              <input
                type="number"
                min="1"
                max="3600"
                step="1"
                value={period.duration}
                data-testid={`duration-${i + 1}`}
                onChange={(e) => updatePeriod(i, { duration: e.target.value })}
              />
            </label>
            <div className="bands">
              {FREQUENCIES.map((f) => (
                <label key={f}>
                  {f} Hz
                  <input
                    type="number"
                    min="0"
                    max="140"
                    step="any"
                    value={period.bands[f]}
                    data-testid={`band-${i + 1}-${f}`}
                    onChange={(e) =>
                      updatePeriod(i, { bands: { ...period.bands, [f]: e.target.value } })
                    }
                  />
                </label>
              ))}
            </div>
          </fieldset>
        ))}

        <div className="actions">
          <button type="button" onClick={addPeriod} disabled={periods.length >= MAX_PERIODS}>
            添加时段（{periods.length}/{MAX_PERIODS}）
          </button>
          <button type="submit" className="primary" disabled={submitting}>
            {submitting ? "计算中…" : "计算暴露"}
          </button>
        </div>
      </form>

      {errors && (
        <section className="errors" data-testid="errors" role="alert">
          <h2>输入未通过校验（422），已清除旧结论</h2>
          <ul>
            {errors.slice(0, 8).map((msg, i) => (
              <li key={i}>{msg}</li>
            ))}
            {errors.length > 8 && <li>…共 {errors.length} 条</li>}
          </ul>
        </section>
      )}

      {result && (
        <section className="results" data-testid="results">
          <h2>暴露结论</h2>
          <div className={result.passed ? "verdict pass" : "verdict fail"} data-testid="verdict">
            {result.passed ? "合格" : "超标"}
          </div>
          <p className="total">
            总 LAeq：
            <strong data-testid="total-laeq">{result.laeq_total_db} dB(A)</strong>
            （限值 {result.limit_db} dB(A)，按未舍入值判定；总时长 {result.total_duration_s} 秒）
          </p>
          <p className="dominant" data-testid="dominant-source">
            能量占比最高：时段 {result.dominant_source.period_index} ·{" "}
            {result.dominant_source.frequency_hz} Hz（占比{" "}
            {result.dominant_source.energy_share_percent}%）
          </p>
          <table>
            <thead>
              <tr>
                <th>时段</th>
                <th>持续时间（秒）</th>
                <th>LAeq dB(A)</th>
              </tr>
            </thead>
            <tbody>
              {result.periods.map((p) => (
                <tr key={p.index}>
                  <td>{p.index}</td>
                  <td>{p.duration}</td>
                  <td data-testid={`period-laeq-${p.index}`}>{p.laeq_db}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <p className="note">
            以上超标来源与总暴露值由后端同一组 A 计权能量计算得出，页面不做任何二次换算。
          </p>
        </section>
      )}
    </main>
  );
}
