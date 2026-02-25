# StockGo (MVP)

美股免费数据源股票分析后端：行情（`yfinance`）+ 新闻（Google News RSS）→ 技术指标 → 事件报告（结构化）→ MySQL 落库 → FastAPI 提供查询与生成接口。

## 运行方式

1) 启动 MySQL（可选但推荐）

```bash
docker compose up -d
```

2) 配置环境变量

```bash
cp .env.example .env
```

3) 安装依赖与启动 API

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

## 常用接口

- `GET /health`
- `POST /v1/analysis/run`：生成分析（默认同步）
- `GET /v1/analysis/run/{run_id}`：查询运行状态与结果
- `GET /v1/report/latest?ticker=TSLA`

## 示例

同步生成（返回结构化报告）：

```bash
curl -s -X POST "http://127.0.0.1:8000/v1/analysis/run" \
  -H "Content-Type: application/json" \
  -d '{"ticker":"TSLA","start":"2025-12-01","end":"2026-02-24","timeframe":"1d"}'
```

## 备注

- 新闻源使用 Google News RSS（免费、可用性高），返回通常以标题为主；后续可接入更高质量新闻 API/付费源。
- 当前默认使用“规则融合”输出 `bias`；如配置 OpenAI 兼容接口，会自动走 LLM 结构化输出。

## 定时调度 + 增量更新

项目内置 APScheduler（可选），用于对 `WATCHLIST` 做定时增量更新：
- **增量更新**：从数据库中读取“最后一根 K 线/最后一条新闻时间”，只回溯少量窗口（行情 5 天、新闻 3 天）并 upsert。
- **指标 warmup**：为保证 MA200 等滚动指标正确，技术指标会额外带一个 warmup 窗口（日线默认 400 天）。

开启方式（`.env`）：
- `SCHEDULER_ENABLED=true`
- `WATCHLIST=TSLA,AAPL,MSFT`
- `MARKET_UPDATE_MINUTES=30`
- `NEWS_UPDATE_MINUTES=30`
- `REPORT_LOOKBACK_DAYS=365`
