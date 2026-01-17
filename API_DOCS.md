# Alpha Arena API (简版)

Base URL: `http://127.0.0.1:8000`

## 健康与账户
- `GET /api/health`
- `GET /api/account/summary`
- `GET /api/balances?currency=`

## 市场数据
- `GET /api/market/candles?symbol=BTC/USDT:USDT&timeframe=1h&limit=200`
- `GET /api/market/symbols`
- `GET /api/market/timeframes?symbol=BTC/USDT:USDT`
- `GET /api/market/funding?symbol=BTC/USDT:USDT`
- `GET /api/market/prices?symbol=BTC/USDT:USDT`

## 决策与交易
- `GET /api/decisions?symbol=BTC/USDT:USDT&limit=50`
- `GET /api/orders?symbol=BTC/USDT:USDT&limit=50`
- `GET /api/trades?symbol=BTC/USDT:USDT&limit=50`
- `GET /api/positions?symbol=BTC/USDT:USDT`

## 回测
- `GET /api/backtests?limit=20`
- `GET /api/backtests/{id}`
- `POST /api/backtest/run`（写接口）

## 数据健康 (Data Health)
- `GET /api/data-health/coverage?symbol=BTC/USDT:USDT`
- `GET /api/data-health/integrity-events?symbol=BTC/USDT:USDT&timeframe=1h&limit=200`
- `POST /api/data-health/scan`（写接口）
- `POST /api/data-health/repair`（写接口）
- `GET /api/data-health/repair-jobs?symbol=BTC/USDT:USDT&timeframe=1h`

## 写接口开关
所有 `POST` 接口默认关闭，需要 `.env`：
```
API_WRITE_ENABLED=true
```
