# StockGo (MVP)

A U.S. stock analysis backend built on free data sources: market data (`yfinance`) + news (Google News RSS) -> technical indicators -> structured event reports -> MySQL storage -> FastAPI query and generation APIs.

## How To Run

### Local Python + Node

1. Start MySQL (optional but recommended)

```bash
docker compose up -d mysql
```

2. Configure environment variables

```bash
cp .env.example .env
```

3. Install dependencies and start the API (`localhost:8000` must be running before the frontend)

```bash
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

4. Start the frontend in a separate terminal

```bash
cd web
npm install
npm run dev
```

Open http://localhost:3000 in your browser. If you see “localhost took too long to respond”, make sure the API from the previous step is running. Visiting http://localhost:8000/health should return `{"ok":true}`.

### Docker Deploy (Frontend + Backend + MySQL)

1. Prepare environment variables

```bash
cp .env.example .env
```

At minimum, review these values in `.env` before starting:

- `MYSQL_PASSWORD`
- `MYSQL_ROOT_PASSWORD`
- `JWT_SECRET`
- `SEC_USER_AGENT`
- `NEXT_PUBLIC_API_BASE` if the frontend will not be accessed from the same machine as the backend
- `CORS_ORIGINS` if the frontend origin is not `http://localhost:3000`

2. Build and start the full stack

```bash
docker compose up -d --build
```

3. Open the services

- Frontend: http://localhost:3000
- Backend API: http://localhost:8000/health

4. Stop the stack

```bash
docker compose down
```

If you need to reset MySQL data as well:

```bash
docker compose down -v
```

## Common Endpoints

- `GET /health`
- `POST /v1/analysis/run`: generate an analysis result (synchronous by default)
- `GET /v1/analysis/run/{run_id}`: query run status and result
- `GET /v1/report/latest?ticker=TSLA`
- `POST /admin/sync/{job}`: manually trigger an admin sync job; supported `job` values are `reports`, `news`, `financials`, `sec`, and `quotes`

Example admin sync request:

```bash
curl -X POST "http://127.0.0.1:8000/admin/sync/financials?tickers=AAPL,MSFT" \
  -H "Authorization: Bearer <admin_token>"
```

If `tickers` is omitted, the job uses `WATCHLIST` by default. For the `quotes` job, omitting `tickers` refreshes all non-ETF instruments currently stored in the database.

## Example

Synchronous analysis generation (returns a structured report):

```bash
curl -s -X POST "http://127.0.0.1:8000/v1/analysis/run" \
  -H "Content-Type: application/json" \
  -d '{"ticker":"TSLA","start":"2025-12-01","end":"2026-02-24","timeframe":"1d"}'
```

## Notes

- News is sourced from Google News RSS. It is free and generally reliable, but responses are usually title-heavy. You can later replace it with a higher-quality news API or paid provider.
- The current default `bias` output is rule-based. If an OpenAI-compatible endpoint is configured, the app automatically switches to structured LLM output.

## Scheduler And Incremental Updates

The project includes optional APScheduler jobs for incremental updates on `WATCHLIST`:

- **Incremental updates**: read the most recent market bar and news timestamps from the database, then backfill only a small window (5 days for price data, 3 days for news) before upserting.
- **Indicator warmup**: to keep rolling indicators such as MA200 accurate, technical indicators are recomputed with an additional warmup window (400 days by default for daily data).

Enable with `.env` settings:

- `SCHEDULER_ENABLED=true`
- `SCHEDULER_FINANCIALS_ONLY=true` to enable only financial statement sync jobs (balance sheet / income statement / cash flow)
- `WATCHLIST=TSLA,AAPL,MSFT`
- `MARKET_UPDATE_MINUTES=30`
- `NEWS_UPDATE_MINUTES=30`
- `REPORT_LOOKBACK_DAYS=365`
