# 车间噪声暴露巡检工作台

职业卫生师使用的噪声暴露复算工具：React 页面编辑 1–24 个测量时段，FastAPI 完成全部数值计算，Docker Compose 分别运行 `web` 与 `api` 两个服务。

## 计算规则（后端唯一实现）

- 每个时段：持续时间 `duration`（1–3600 秒整数）+ 63/125/250/500/1000/2000/4000/8000 Hz 八个倍频带声级（0–140 dB 有限数）。
- 固定 A 计权修正：`-26.2, -16.1, -8.6, -3.2, 0, +1.2, +1.0, -1.1` dB。
- 各频带先换算为能量 `E = 10^((L + A) / 10)`，再按时段持续时间加权合成：

  ```
  LAeq,total = 10 · lg( Σ_p T_p · Σ_b 10^((L_pb + A_b)/10)  /  Σ_p T_p )
  ```

- **判定用未舍入值**：未舍入总 LAeq ≤ 用户限值（40–100 dB）才合格；只有展示值四舍五入（half-up）到一位小数。因此可能出现“显示 85.0 但判超标”（真实值 85.04）。
- 响应一次给出：每时段 LAeq、总 LAeq、能量占比最高的时段与频带（并列时取最早时段、再取最低频率）。页面的超标来源与总暴露值来自同一组能量计算，前端不做任何二次换算。
- 字段缺失、额外频带/字段、非法数值（非整数时长、超范围、NaN/Infinity）→ 整次请求返回 422，页面清除旧结论。

## 运行（Docker Compose）

```bash
docker compose up --build
# 页面: http://localhost:8080   API: http://localhost:8000/api/health
```

`web` 容器用 nginx 托管前端构建产物，并把 `/api/*` 反代到 `api` 容器（同源，无 CORS 问题）。

## 本地开发（不用 Docker）

```bash
# API（终端 1）
cd api && pip install -r requirements-dev.txt
python3 -m uvicorn app.main:app --reload --port 8000

# 前端（终端 2，vite dev server 会把 /api 代理到 8000）
cd web && npm install && npm run dev   # http://localhost:5173
```

## 测试

```bash
# 后端：独立公式核对 + 边界样例（45 例）
cd api && python3 -m pytest tests/ -q

# 端到端：仅一条主流程冒烟（需先启动整套服务）
cd e2e && npm install && npx playwright install chromium
WEB_URL=http://localhost:8080 npm test    # 默认即 8080，可省略 WEB_URL
```

## API 契约

`POST /api/assessments`

```json
{
  "limit": 85,
  "periods": [
    {"duration": 1200, "bands": {"63": 78, "125": 80, "250": 82, "500": 84,
      "1000": 85, "2000": 83, "4000": 80, "8000": 75}}
  ]
}
```

→ `200`：`{ limit_db, total_duration_s, laeq_total_db, passed, periods: [{index, duration, laeq_db}], dominant_source: {period_index, frequency_hz, energy_share_percent} }`
→ `422`：任何字段缺失/多余/非法，整次拒绝，`detail` 为逐条错误。

## 结构

```
api/            FastAPI 应用
  app/calc.py     能量计算（唯一数值实现）
  app/models.py   请求/响应校验（422 的来源）
  app/main.py     路由与装配
  tests/          pytest：独立公式核对 + 边界样例
web/            React + Vite 前端（nginx 反代 /api）
e2e/            Playwright 单条主流程冒烟
docker-compose.yml
```
