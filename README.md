# 车间噪声职业暴露工作台

面向职业卫生师的噪声暴露复算工具：编辑 1 ~ 24 个测量时段（每个时段 1 ~ 3600 整数秒，
63 / 125 / 250 / 500 / 1000 / 2000 / 4000 / 8000 Hz 八个倍频带，0 ~ 140 dB 有限数），
FastAPI 按能量合并计算总 LAeq，React 页面逐项展示可复算的结论。

> 关键原则：**不做声级算术平均**。各倍频带先换算为能量、再按时长加权合并，
> 短时高声级不会被长时低背景稀释；总暴露值、各时段 LAeq、能量占比最高的来源
> 全部来自同一次能量计算。

## 目录结构

```
api/                FastAPI 后端
  main.py           路由（POST /api/exposure，GET /api/health）
  schemas.py        Pydantic 校验（422 规则集中于此）
  calculations.py   A 计权修正、能量换算、HALF_UP 展示舍入
  service.py        能量合并、主导来源、合格判定
  requirements.txt
  Dockerfile
tests/test_api.py   pytest：独立参考公式 + 边界样例（44 项）
web/                React + Vite 前端
  src/App.jsx                   编辑 1~24 时段、提交、422 清结论
  src/components/PeriodTable.jsx
  src/components/ResultPanel.jsx
  e2e/smoke.spec.js  Playwright 单条主流程冒烟
  nginx.conf        容器内托管静态文件并反代 /api
docker-compose.yml  api(8000) + web(5173)
```

## 计算方法（可逐项复算）

1. 每个频带套用固定 A 计权修正（不随输入变化）：

   | 频率 Hz | 63 | 125 | 250 | 500 | 1000 | 2000 | 4000 | 8000 |
   |---|---|---|---|---|---|---|---|---|
   | 修正 dB | -26.2 | -16.1 | -8.6 | -3.2 | 0 | +1.2 | +1.0 | -1.1 |

2. 频带能量（相对声压平方，参考声压取对数后约去）：
   `E_ij = 10 ** ((L_ij + A_j) / 10)`
3. 单时段 LAeq：`LAeq_i = 10 * log10(sum_j E_ij)`
4. 总 LAeq（时长加权能量合并）：
   `LAeq = 10 * log10( sum_i d_i * sum_j E_ij / sum_i d_i )`
5. 能量占比：`d_i * E_ij / 全任务总能量`；占比最高的时段/频带为主导来源，
   **并列时取最早时段、最低频率**。
6. 判定使用**未舍入**总 LAeq 与用户给定 40 ~ 100 dB 限值比较（`<=` 合格）；
   页面展示值才四舍五入到一位（HALF_UP）。例如未舍入 85.04 dB 展示为 85.0，
   对 85 dB 限值仍判超标。

## 422 规则（整次拒绝，页面清除旧结论）

- 时段数不在 1 ~ 24；duration 不是 1 ~ 3600 的整数（1.5、字符串、布尔均拒绝）；
- 频带缺失、出现八频带以外的额外键；
- 声级不是 0 ~ 140 的有限数（字符串、布尔、null 均拒绝）；
- limit 不在 40 ~ 100；顶层或嵌套层出现额外字段。

## 本地开发（非 Docker）

```bash
# 后端
pip install -r api/requirements.txt -r requirements-dev.txt
uvicorn api.main:app --reload --port 8000

# 前端（vite 已把 /api 代理到 8000）
cd web && npm install && npm run dev
```

## Docker Compose

```bash
docker compose up --build
# web: http://localhost:5173 （nginx 托管静态文件并反代 /api -> api:8000）
# api: http://localhost:8000/api/health
```

## 测试

```bash
# 后端：独立参考公式核对 + 422 边界 + 未舍入判定
pytest                 # 44 passed

# 前端：一条主流程冒烟（需先跑起 api:8000 与 web:5173）
cd web && npx playwright install chromium && npx playwright test
```

## 联调样例说明

页面「填入联调样例」：60 s 高噪声（LAeq≈104.3 dB）+ 1740 s 中噪声 + 1800 s 低噪声。

- 声级算术平均会得到约 80 dB（**稀释**，误判合格）；
- 能量合并总 LAeq ≈ **87.7 dB，对 85 dB 限值超标**；
- 仅 60 s 的时段贡献全任务 **76.1%** 能量，主导来源为时段 1 / 2000 Hz（29.5%）。
