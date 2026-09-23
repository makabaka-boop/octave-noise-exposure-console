export default function ResultPanel({ result }) {
  const { total_laeq_display, total_laeq, limit_db, compliant, dominant, periods } = result

  const periodById = Object.fromEntries(periods.map((p) => [p.index, p]))
  const domPeriod = periodById[dominant.period_index]
  const domBand = domPeriod?.bands.find((b) => b.frequency === dominant.frequency)

  return (
    <section className="result" data-testid="result-panel">
      <div className={`verdict ${compliant ? 'ok' : 'bad'}`} data-testid="verdict">
        <div className="verdict-main">
          总暴露 LAeq = <strong data-testid="total-laeq">{total_laeq_display}</strong> dB
          <span className="unrounded">（未舍入 {total_laeq.toFixed(6)} dB）</span>
        </div>
        <div className="verdict-sub">
          限值 {limit_db} dB ·{' '}
          {compliant ? (
            <span className="ok-text">合格：未舍入暴露值不超过限值</span>
          ) : (
            <span className="bad-text">超标：未舍入暴露值高于限值</span>
          )}
        </div>
      </div>

      <div className="dominant" data-testid="dominant">
        <h3>能量占比最高的来源（超标追溯依据）</h3>
        <p>
          时段 <strong>#{dominant.period_index}</strong>（
          {domPeriod?.duration_s} s） ·{' '}
          <strong>{dominant.frequency} Hz</strong> 频带 ·
          原始声级 <strong>{domBand ? domBand.level_db.toFixed(1) : '—'}</strong> dB ·
          A 计权后 <strong>{domBand ? domBand.a_weighted_db.toFixed(1) : '—'}</strong> dB ·
          占全任务能量{' '}
          <strong>{(dominant.energy_share * 100).toFixed(2)}%</strong>
        </p>
        <p className="note">
          并列时取最早时段、最低频率。下方各时段 / 各频带能量占比与总 LAeq
          来自后端同一次能量合并计算，可逐项复算。
        </p>
      </div>

      <h3>各时段结论</h3>
      <table className="result-table">
        <thead>
          <tr>
            <th>时段</th>
            <th>duration (s)</th>
            <th>本时段 LAeq（展示值）</th>
            <th>未舍入 LAeq</th>
            <th>本时段能量占全任务比例</th>
          </tr>
        </thead>
        <tbody>
          {periods.map((p) => {
            const share = p.bands.reduce((s, b) => s + b.energy_share, 0)
            return (
              <tr key={p.index} data-testid={`result-period-${p.index}`}>
                <td>#{p.index}</td>
                <td>{p.duration_s}</td>
                <td>{p.laeq_display}</td>
                <td>{p.laeq.toFixed(6)}</td>
                <td>{(share * 100).toFixed(2)}%</td>
              </tr>
            )
          })}
        </tbody>
      </table>

      <details>
        <summary>逐频带能量与占比（可逐项复算）</summary>
        <table className="result-table bands">
          <thead>
            <tr>
              <th>时段</th>
              <th>频率 (Hz)</th>
              <th>原始 L (dB)</th>
              <th>A 计权后 (dB)</th>
              <th>能量 10^(LA/10)</th>
              <th>占全任务能量</th>
            </tr>
          </thead>
          <tbody>
            {periods.flatMap((p) =>
              p.bands.map((b) => (
                <tr
                  key={`${p.index}-${b.frequency}`}
                  className={
                    p.index === dominant.period_index && b.frequency === dominant.frequency
                      ? 'dom-row'
                      : ''
                  }
                >
                  <td>#{p.index}</td>
                  <td>{b.frequency}</td>
                  <td>{b.level_db.toFixed(1)}</td>
                  <td>{b.a_weighted_db.toFixed(1)}</td>
                  <td>{b.energy.toExponential(6)}</td>
                  <td>{(b.energy_share * 100).toFixed(4)}%</td>
                </tr>
              )),
            )}
          </tbody>
        </table>
      </details>
    </section>
  )
}
