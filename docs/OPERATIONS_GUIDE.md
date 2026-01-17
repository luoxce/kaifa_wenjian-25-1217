# Operations Manual (Local Run)

This guide shows the exact steps to bring up the API + frontend and open the UI.

## 1) Backend setup (first time)

```bash
pip install -r requirements.txt
copy .env.example .env
python scripts/db_migrate.py
```

Optional (load history data):
```bash
python scripts/ingest_okx.py --symbol BTC/USDT:USDT --since-days 365 --timeframes 15m,1h,4h,1d
```

## 2) Start the API server

```bash
python scripts/api_server.py --host 127.0.0.1 --port 8000
```

Check health:
```bash
http://127.0.0.1:8000/api/health
```

## 3) Frontend setup (first time)

```bash
cd frontend
copy .env.example .env
```

Edit `frontend/.env` and set:
```
VITE_API_BASE_URL=http://127.0.0.1:8000
VITE_WS_BASE_URL=ws://127.0.0.1:8000
VITE_DASHBOARD_SYMBOL=BTC/USDT:USDT
VITE_DASHBOARD_TIMEFRAME=15m
VITE_DASHBOARD_LIMIT=200
```

Install and run:
```bash
npm install
npm run dev
```

## 4) Open the UI

- Dashboard: `http://127.0.0.1:5173`
- Backtest: `http://127.0.0.1:5173/backtest`
- Data Monitor: `http://127.0.0.1:5173/data-monitor`

## 5) If something looks empty

Checklist:
1) API is running and `http://127.0.0.1:8000/api/health` returns ok.
2) Frontend `.env` has `VITE_API_BASE_URL` set to the API URL.
3) You have data in the database (run ingest if needed).

## 6) Optional write actions

By default, write endpoints (ingest, backtest, sync) are disabled.
To enable, set in `.env`:
```
API_WRITE_ENABLED=true
```

## 7) Common fixes

- Port in use: change `--port` or close the process using it.
- No candles: run ingest or verify symbol/timeframe.
- Frontend not updating: restart `npm run dev` after editing `frontend/.env`.
