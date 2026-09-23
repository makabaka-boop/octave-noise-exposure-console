import { FREQS, A_CORRECTION } from '../constants.js'

function corrText(f) {
  const v = A_CORRECTION[f]
  return `A=${v > 0 ? '+' : ''}${v}`
}

export default function PeriodTable({ periods, onUpdate, onLevel, onRemove }) {
  return (
    <section className="table-wrap">
      <table className="period-table">
        <thead>
          <tr>
            <th rowSpan="2">时段</th>
            <th rowSpan="2">duration（秒，1~3600 整数）</th>
            <th colSpan={FREQS.length}>各倍频带声压级 L（dB，0~140）</th>
            <th rowSpan="2">操作</th>
          </tr>
          <tr>
            {FREQS.map((f) => (
              <th key={f}>
                {f} Hz
                <span className="corr">{corrText(f)}</span>
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {periods.map((p, i) => (
            <tr key={i}>
              <td>#{i + 1}</td>
              <td>
                <input
                  aria-label={`时段${i + 1}-duration`}
                  type="number"
                  min="1"
                  max="3600"
                  step="1"
                  value={p.duration}
                  onChange={(e) => onUpdate(i, { duration: e.target.value })}
                />
              </td>
              {FREQS.map((f) => (
                <td key={f}>
                  <input
                    aria-label={`时段${i + 1}-${f}Hz`}
                    type="number"
                    min="0"
                    max="140"
                    step="0.1"
                    value={p.levels[f]}
                    onChange={(e) => onLevel(i, f, e.target.value)}
                  />
                </td>
              ))}
              <td>
                <button
                  type="button"
                  onClick={() => onRemove(i)}
                  disabled={periods.length <= 1}
                >
                  删除
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  )
}
