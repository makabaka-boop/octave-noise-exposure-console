import { useState } from 'react'
import PeriodTable from './components/PeriodTable.jsx'
import ResultPanel from './components/ResultPanel.jsx'
import { FREQS } from './constants.js'

const API_BASE = import.meta.env.VITE_API_BASE || ''

function emptyPeriod() {
  return { duration: '', levels: Object.fromEntries(FREQS.map((f) => [f, ''])) }
}

function samplePeriods() {
  // 一组贴近真实车间的联调样例：短时高声级 + 长时背景，
  // 算术平均声级看起来不高，能量合并后短时高声级不被稀释。
  return [
    {
      duration: 60,
      levels: { 63: 78, 125: 84, 250: 90, 500: 96, 1000: 100, 2000: 99, 4000: 95, 8000: 88 },
    },
    {
      duration: 1740,
      levels: { 63: 68, 125: 72, 250: 76, 500: 78, 1000: 79, 2000: 77, 4000: 74, 8000: 69 },
    },
    {
      duration: 1800,
      levels: { 63: 64, 125: 68, 250: 71, 500: 73, 1000: 74, 2000: 72, 4000: 69, 8000: 65 },
    },
  ]
}

export default function App() {
  const [limit, setLimit] = useState('85')
  const [periods, setPeriods] = useState([emptyPeriod()])
  const [result, setResult] = useState(null)
  const [errors, setErrors] = useState([])
  const [networkError, setNetworkError] = useState('')
  const [submitting, setSubmitting] = useState(false)

  function clearResult() {
    setResult(null)
    setErrors([])
    setNetworkError('')
  }

  function updatePeriod(i, patch) {
    setPeriods((prev) => prev.map((p, idx) => (idx === i ? { ...p, ...patch } : p)))
    // 输入变动后旧结论不再可信
    clearResult()
  }

  function updateLevel(i, freq, value) {
    setPeriods((prev) =>
      prev.map((p, idx) =>
        idx === i ? { ...p, levels: { ...p.levels, [freq]: value } } : p,
      ),
    )
    clearResult()
  }

  function addPeriod() {
    if (periods.length >= 24) return
    setPeriods((prev) => [...prev, emptyPeriod()])
    clearResult()
  }

  function removePeriod(i) {
    if (periods.length <= 1) return
    setPeriods((prev) => prev.filter((_, idx) => idx !== i))
    clearResult()
  }

  function loadSample() {
    setPeriods(samplePeriods())
    setLimit('85')
    clearResult()
  }

  function validateLocal() {
    const errs = []
    const lim = Number(limit)
    if (limit === '' || !Number.isFinite(lim) || lim < 40 || lim > 100) {
      errs.push('限值 limit 必须是 40 ~ 100 dB 的数字')
    }
    periods.forEach((p, i) => {
      const d = Number(p.duration)
      if (p.duration === '' || !Number.isInteger(d) || d < 1 || d > 3600) {
        errs.push(`时段 ${i + 1}：duration 必须是 1 ~ 3600 的整数秒`)
      }
      FREQS.forEach((f) => {
        const v = p.levels[f]
        const n = Number(v)
        if (v === '' || !Number.isFinite(n) || n < 0 || n > 140) {
          errs.push(`时段 ${i + 1} / ${f} Hz：声级必须是 0 ~ 140 dB 的数字`)
        }
      })
    })
    return errs
  }

  async function submit() {
    const errs = validateLocal()
    if (errs.length) {
      setErrors(errs)
      setResult(null) // 整次非法：清除旧结论
      return
    }
    setSubmitting(true)
    setErrors([])
    setNetworkError('')
    try {
      const payload = {
        limit: Number(limit),
        periods: periods.map((p) => ({
          duration: Number(p.duration),
          levels: Object.fromEntries(
            FREQS.map((f) => [String(f), Number(p.levels[f])]),
          ),
        })),
      }
      const res = await fetch(`${API_BASE}/api/exposure`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      })
      if (res.status === 422) {
        const data = await res.json()
        const detail = data.detail
        const msgs = Array.isArray(detail)
          ? detail.map((d) => {
              const loc = (d.loc || []).filter((x) => x !== 'body').join(' / ')
              return loc ? `${loc}：${d.msg}` : d.msg
            })
          : ['请求被拒绝（422），请检查输入']
        setErrors(msgs)
        setResult(null) // 后端 422：页面清除旧结论
        return
      }
      if (!res.ok) {
        setNetworkError(`服务异常：HTTP ${res.status}`)
        setResult(null)
        return
      }
      setResult(await res.json())
    } catch (e) {
      setNetworkError(`无法连接计算服务：${e.message}`)
      setResult(null)
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <main className="page">
      <header>
        <h1>车间噪声职业暴露工作台</h1>
        <p className="subtitle">
          倍频带声压级 → A 计权能量合并 → 总 LAeq；判定使用未舍入值，展示保留一位小数。
        </p>
      </header>

      <section className="limit-row">
        <label>
          职业接触限值 LAeq（dB，40~100）：
          <input
            type="number"
            value={limit}
            min="40"
            max="100"
            step="0.1"
            onChange={(e) => {
              setLimit(e.target.value)
              clearResult()
            }}
            data-testid="limit-input"
          />
        </label>
        <div className="actions">
          <button type="button" onClick={addPeriod} disabled={periods.length >= 24}>
            添加时段（{periods.length}/24）
          </button>
          <button type="button" onClick={loadSample}>
            填入联调样例
          </button>
          <button
            type="button"
            className="primary"
            onClick={submit}
            disabled={submitting}
            data-testid="submit-btn"
          >
            {submitting ? '计算中…' : '计算暴露结论'}
          </button>
        </div>
      </section>

      <PeriodTable
        periods={periods}
        onUpdate={updatePeriod}
        onLevel={updateLevel}
        onRemove={removePeriod}
      />

      {(errors.length > 0 || networkError) && (
        <section className="errors" data-testid="errors">
          <h3>输入未通过校验（整次请求未计算，已清除旧结论）</h3>
          {networkError && <p>{networkError}</p>}
          <ul>
            {errors.map((m, i) => (
              <li key={i}>{m}</li>
            ))}
          </ul>
        </section>
      )}

      {result && <ResultPanel result={result} />}
    </main>
  )
}
