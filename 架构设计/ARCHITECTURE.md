# Alpha Arena - 项目架构设计文档

> **版本**: v1.0  
> **更新日期**: 2026-01-14  
> **作者**: AI Assistant  
> **项目**: Alpha Arena - AI 驱动的加密货币量化交易系统

---

## 📋 目录

1. [项目概述](#项目概述)
2. [系统架构](#系统架构)
3. [模块设计](#模块设计)
4. [数据流设计](#数据流设计)
5. [数据库设计](#数据库设计)
6. [API 设计](#api-设计)
7. [部署架构](#部署架构)
8. [技术栈](#技术栈)

---

## 1. 项目概述

### 1.1 项目简介

**Alpha Arena** 是一个基于大语言模型（LLM）的加密货币量化交易决策系统，旨在通过 AI 技术辅助交易者做出更明智的交易决策。

### 1.1.1 真源与范围

- 策略库与参数：以 `架构设计/BITCOIN_STRATEGY_LIBRARY.md` 为准
- 智能体流程与执行边界：以 `架构设计/MULTI_AGENT_ARCHITECTURE.md` 为准
- 数据库与采集规划：以 `架构设计/DB_PLAN.md` 为准
- 单币种 BTC/USDT:USDT，OKX 模拟盘永续（后续切换实盘）
- LLM 仅选择策略，不修改参数；强化学习为离线训练/定期发布

### 1.2 核心功能

- **市场数据采集**: 从 OKX 交易所实时获取市场数据
- **技术分析**: 自动计算技术指标（EMA、RSI、MACD、布林带等）
- **AI 决策引擎**: 使用 DeepSeek/Qwen 等 LLM 生成交易建议
- **风险管理**: 多层风控检查（杠杆、仓位、止损）
- **回测系统**: 基于历史数据验证策略有效性
- **离线训练与反馈**: 基于回测/实盘结果更新策略评分与 Prompt
- **交易执行**: OKX 模拟盘永续（当前），实盘可切换
- **Web 可视化**: FastAPI + 前端仪表盘

### 1.3 设计目标

- **模块化**: 清晰的模块划分，易于扩展和维护
- **可测试性**: 每个模块都可以独立测试
- **可配置性**: 通过配置文件灵活调整参数
- **高性能**: 支持实时数据处理和快速回测
- **安全性**: API 密钥加密存储，完善的权限控制

---

## 2. 系统架构

### 2.1 三层架构（与 MULTI_AGENT_ARCHITECTURE 对齐）

```
┌─────────────────────────────────────────────────────────┐
│                   决策与策略调度层                         │
│  (LLM 选择 + 多策略组合评分/权重分配)                      │
└─────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────┐
│                      策略执行层                          │
│  (趋势跟踪、均值回归、突破、网格、资金费率等策略)           │
└─────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────┐
│                   离线训练与反馈层                         │
│  (离线训练/评估，定期更新策略评分与 Prompt)                │
└─────────────────────────────────────────────────────────┘
```

### 2.2 核心数据流（当前实现）

```
OKX 采集脚本
   ↓
SQLite (market_data / funding / price_snapshots ...)
   ↓
DataService (统一读接口，禁止业务层 SQL)
   ↓
策略/技术分析/回测/执行
   ↓
Portfolio Scheduler (策略评分 + 权重分配)
   ↓
OrderExecutor (Simulated / OKX Stub)
   ↓
orders / trades / positions / order_lifecycle_events
   ↓
离线评估与反馈（策略评分 / Prompt 更新）
```

### 2.3 关键约束与对齐原则

- 单币种：BTC/USDT:USDT（OKX 永续模拟盘起步，后续切实盘）。
- LLM 仅做“策略选择”，不直接修改参数；离线训练定期更新策略评分与 Prompt。
- 多策略调度仅影响“组合权重/启停”，不直接绕过风控与执行层。
- 业务层读数据必须通过 DataService；SQL 仅允许出现在采集/DB 工具中。
- 回测与实盘共享统一接口：OrderExecutor + OrderStatus 状态机。

### 2.4 强化学习/离线训练机制（与 MULTI_AGENT_ARCHITECTURE 对齐）

- 训练方式：离线训练/周期评估，不在实盘实时训练。
- 数据来源：backtest_results / trades / decisions / market_data。
- 产出内容：策略评分表、参数建议范围、Prompt 更新版本。
- 上线方式：人工或规则审核后发布到策略选择器。
- 影响范围：仅影响“策略选择/评分”，不直接下单。

## 3. 模块设计

### 3.0 当前落地情况（防止与规划冲突）

- 已落地：数据采集 + 数据库 + DataService + 回测 MVP + 订单模型/状态机 + Simulated/OKX 执行器骨架 + LLM 决策 + 多策略组合评分（Portfolio）。
- 规划中：强化学习/离线训练自动化、完整回测撮合、实盘监控与告警、策略组合强化版本。


### 3.1 模块目录结构

```
kaifa_wenjian-25-1217/
├── requirements.txt
├── .env.example
├── src/
│   └── alpha_arena/
│       ├── __init__.py
│       ├── config.py            # 配置加载
│       ├── data/
│       │   ├── __init__.py
│       │   ├── data_service.py  # 统一数据读取
│       │   └── models.py        # 数据快照模型
│       ├── db/
│       │   ├── connection.py    # 数据库连接
│       │   ├── migrate.py       # 迁移执行器
│       │   └── migrations/
│       │       └── 001_init.sql # 基础表结构
│       ├── execution/
│       │   ├── __init__.py
│       │   ├── base_executor.py # 执行器接口
│       │   ├── simulated_executor.py
│       │   └── okx_executor.py  # OKX Stub 执行器
│       ├── ingest/
│       │   └── okx.py           # OKX 数据采集
│       ├── models/
│       │   ├── __init__.py
│       │   ├── enums.py         # 订单状态枚举
│       │   └── order.py         # 订单模型
│       ├── strategies/
│       │   ├── __init__.py
│       │   ├── base.py          # 策略接口
│       │   ├── signals.py       # 信号结构
│       │   ├── indicators.py    # 技术指标
│       │   ├── ema_trend.py     # EMA 趋势
│       │   ├── bollinger_range.py
│       │   ├── funding_rate_arbitrage.py
│       │   └── registry.py      # 策略注册表
│       └── utils/
│           └── time.py          # 时间工具
├── scripts/
│   ├── db_migrate.py            # 迁移脚本入口
│   ├── ingest_okx.py            # OKX 采集入口
│   ├── ingest_scheduler.py      # 定时采集
│   ├── db_stats.py              # 数据质量统计
│   ├── db_repair.py             # 缺口修复
│   ├── smoke_data_service.py    # DataService 测试
│   └── run_backtest_mvp.py      # 回测 MVP
├── data/                        # 本地数据库/缓存
└── 架构设计/
    ├── ARCHITECTURE.md
    ├── DB_PLAN.md
    ├── DB_OVERVIEW.md
    ├── MULTI_AGENT_ARCHITECTURE.md
    └── BITCOIN_STRATEGY_LIBRARY.md
```

### 3.2 核心模块职责

#### 3.2.1 配置管理模块 (`config.py`)

**职责**:
- 统一管理项目配置
- 加载环境变量
- 提供配置访问接口

**核心类**:
- `Settings`: 配置类

**配置项**:
- OKX API 配置
- LLM 配置
- 数据库配置
- 市场配置
- 回测配置

#### 3.2.2 数据模块 (`data/`)

**职责**:
- 市场数据采集
- 数据库管理
- 定时任务调度

**核心类**:
- `MarketDataDB`: 数据库管理器
- `MarketDataCollector`: 数据采集器
- `DataUpdateScheduler`: 定时任务调度器

**功能**:
- 批量历史数据下载
- 增量数据更新
- 数据查询和统计

#### 3.2.3 技术分析模块 (`analysis/`)

**职责**:
- 计算技术指标
- 识别市场形态
- 生成技术分析报告

**核心类**:
- `TechnicalIndicators`: 技术指标计算器
- `PatternRecognizer`: 形态识别器
- `TechnicalAnalysisAgent`: 技术分析 Agent

**支持的指标**:
- EMA (指数移动平均线)
- RSI (相对强弱指标)
- MACD (平滑异同移动平均线)
- Bollinger Bands (布林带)
- ATR (平均真实波幅)
- Volume (成交量)

#### 3.2.4 策略库模块 (`strategies/`)

**职责**:
- 统一策略接口与信号结构（StrategySignal）。
- 仅通过 DataService 读取数据，禁止策略层直接写 SQL。
- 策略注册与启停控制（当前仅启用 EMA/布林/资金费率）。

**已实现策略**:
- EMA 趋势跟踪
- 布林带震荡
- 资金费率套利

**规划策略**:
- 突破交易、网格交易、动量交易、均值回归、链上信号、时间周期、波动率交易

#### 3.2.5 决策引擎模块 (`decision/`)

**职责**:
- 调用 LLM 生成决策
- 构建 Prompt
- 解析 LLM 输出

**核心类**:
- `LLMClient`: LLM 客户端
- `PromptBuilder`: Prompt 构建器
- `DecisionEngine`: LLM 单策略决策引擎
- `PortfolioDecisionEngine`: 多策略组合评分与权重分配
- `StrategyScorer`: 组合评分（Regime + 回测表现）
- `PortfolioScheduler`: 权重分配（Top-N + 归一化）

**决策流程**:
1. 收集市场数据
2. 运行技术分析
3. 构建 Prompt
4. 调用 LLM
5. 解析决策
6. 组合评分与权重分配（多策略模式）
7. 风险检查
8. 返回决策结果

#### 3.2.6 强化学习/离线训练模块 (`reinforcement/`，规划)

**职责**:
- 聚合回测/实盘结果，建立经验样本与奖励函数。
- 评估策略在不同市场环境下的表现并生成评分。
- 产出可解释的策略选择偏好与 Prompt 更新建议。

**核心组件（规划）**:
- `ExperienceBuffer`: 经验回放与数据切片
- `RewardCalculator`: 奖励函数与评估指标
- `RLOptimizer`: 离线训练/评估器
- `PromptUpdater`: Prompt 版本更新器

**输出**:
- 策略评分表（用于 LLM 选择）
- Prompt 版本（写入 `prompt_versions`）

#### 3.2.7 风险管理模块 (`risk/`)

**职责**:
- 多层风控检查
- 风险评估
- 生成风险报告

**核心类**:
- `RiskChecker`: 风险检查器
- `RiskRules`: 风控规则
- `RiskManager`: 风险管理器

**风控检查项**:
- 杠杆检查
- 仓位检查
- 止损检查
- 单笔风险检查
- 总风险检查

#### 3.2.8 回测系统模块 (`backtest/`)

**职责**:
- 历史数据回测
- 性能评估
- 报告生成

**核心类**:
- `BacktestConfig`: 回测配置
- `BacktestEngine`: 回测引擎
- `TradeSimulator`: 交易模拟器
- `PerformanceEvaluator`: 性能评估器
- `BacktestReporter`: 报告生成器

**性能指标**:
- 总收益率
- 最大回撤
- 夏普率
- 盈亏比
- 胜率
- 卡尔玛比率

#### 3.2.9 实盘交易模块 (`trading/`)

**职责**:
- 连接交易所
- 订单管理
- 持仓管理
- 交易执行

**核心类**:
- `OKXClient`: OKX 客户端
- `OrderManager`: 订单管理器
- `PositionManager`: 持仓管理器
- `TradeExecutor`: 交易执行器

**功能**:
- 下单
- 撤单
- 查询订单
- 查询持仓
- 查询余额

#### 3.2.10 API 模块 (`api/`)

**职责**:
- 提供 REST API
- 路由管理
- 请求验证
- 响应格式化

**核心文件**:
- `main.py`: FastAPI 应用
- `routes.py`: 路由定义
- `schemas.py`: 数据模型
- `dependencies.py`: 依赖注入

**API 端点**:
- `/api/market/data` - 市场数据
- `/api/decision/generate` - 生成决策
- `/api/backtest/run` - 运行回测
- `/api/trading/order` - 订单管理

---

## 4. 数据流设计

### 4.1 数据采集流程

```
┌─────────────┐
│  OKX API    │
└──────┬──────┘
       │ fetch_ohlcv()
       ▼
┌─────────────────────┐
│ MarketDataCollector │
│  - 获取 K线数据      │
│  - 数据清洗         │
│  - 去重处理         │
└──────┬──────────────┘
       │ insert_candles()
       ▼
┌─────────────────────┐
│  MarketDataDB       │
│  - 批量插入         │
│  - 创建索引         │
└──────┬──────────────┘
       │
       ▼
┌─────────────────────┐
│  SQLite Database    │
│  market_data 表     │
└─────────────────────┘
```

### 4.2 决策生成流程

```
┌─────────────┐
│  用户请求   │
└──────┬──────┘
       │
       ▼
┌─────────────────────┐
│  DecisionEngine     │
│  1. 加载市场数据    │
└──────┬──────────────┘
       │
       ▼
┌─────────────────────┐
│ TechnicalAnalysis   │
│  2. 计算技术指标    │
│  3. 识别形态        │
└──────┬──────────────┘
       │
       ▼
┌─────────────────────┐
│  PromptBuilder      │
│  4. 构建 Prompt     │
└──────┬──────────────┘
       │
       ▼
┌─────────────────────┐
│  LLMClient          │
│  5. 调用 LLM        │
└──────┬──────────────┘
       │
       ▼
┌─────────────────────┐
│  DecisionParser     │
│  6. 解析决策        │
└──────┬──────────────┘
       │
       ▼
┌─────────────────────┐
│  PortfolioScheduler │
│  7. 组合评分/权重    │
└──────┬──────────────┘
       │
       ▼
┌─────────────────────┐
│  RiskManager        │
│  8. 风险检查        │
└──────┬──────────────┘
       │
       ▼
┌─────────────────────┐
│  决策结果           │
│  - 单策略或组合     │
│  - 权重分配         │
│  - 风险评估         │
└─────────────────────┘
```

### 4.3 回测执行流程

```
┌─────────────┐
│  用户配置   │
│  回测参数   │
└──────┬──────┘
       │
       ▼
┌─────────────────────┐
│  BacktestEngine     │
│  1. 加载历史数据    │
└──────┬──────────────┘
       │
       ▼
┌─────────────────────┐
│  遍历每根 K线       │
│  ┌───────────────┐  │
│  │ 当前价格      │  │
│  │ 当前时间      │  │
│  └───────┬───────┘  │
└──────────┼──────────┘
           │
    ┌──────▼──────┐
    │ 生成交易信号│
    └──────┬──────┘
           │
    ┌──────▼──────┐
    │ 风险检查    │
    └──────┬──────┘
           │
    ┌──────▼──────┐
    │ 执行交易    │
    │ - 开仓      │
    │ - 平仓      │
    │ - 止损止盈  │
    └──────┬──────┘
           │
    ┌──────▼──────┐
    │ 更新持仓    │
    │ 记录权益    │
    └──────┬──────┘
           │
           ▼
┌─────────────────────┐
│  PerformanceEvaluator│
│  计算性能指标        │
│  - 收益率           │
│  - 最大回撤         │
│  - 夏普率           │
└──────┬──────────────┘
       │
       ▼
┌─────────────────────┐
│  BacktestReporter   │
│  生成回测报告        │
└──────┬──────────────┘
       │
       ▼
┌─────────────────────┐
│  回测结果           │
│  - 性能指标         │
│  - 交易记录         │
│  - 权益曲线         │
└─────────────────────┘
```

---

### 4.4 离线训练与反馈流程

```
回测/实盘结果 (backtest_results / trades / decisions)
   ↓
经验样本构建 + 奖励计算 (ExperienceBuffer / RewardCalculator)
   ↓
离线训练与评估 (RLOptimizer)
   ↓
策略评分 / Prompt 版本更新
   ↓
策略选择器读取评分与 Prompt（不直接下单）
```

## 5. 数据库设计

### 5.1 数据库选型

- **主数据库**: SQLite
  - 优点: 轻量级、无需配置、适合单机应用
  - 缺点: 并发性能有限
  - 适用场景: 开发、测试、小规模部署

- **生产数据库** (可选): PostgreSQL / MySQL
  - 优点: 高并发、高性能、支持复杂查询
  - 缺点: 需要额外配置和维护
  - 适用场景: 生产环境、大规模部署

### 5.2 数据表设计

完整规划与约束见 `架构设计/DB_PLAN.md`（作为数据库设计真源）。

#### 5.2.1 市场数据表 (`market_data`)

```sql
CREATE TABLE market_data (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol TEXT NOT NULL,              -- 交易对 (BTC/USDT:USDT)
    timeframe TEXT NOT NULL,           -- 时间框架 (15m, 1h, 4h, 1d)
    timestamp INTEGER NOT NULL,        -- 时间戳 (毫秒)
    open NUMERIC NOT NULL,
    high NUMERIC NOT NULL,
    low NUMERIC NOT NULL,
    close NUMERIC NOT NULL,
    volume NUMERIC NOT NULL,
    created_at INTEGER DEFAULT (strftime('%s', 'now')),
    UNIQUE(symbol, timeframe, timestamp)
);

CREATE INDEX idx_market_data_symbol_timeframe_timestamp
ON market_data(symbol, timeframe, timestamp DESC);
```

**字段说明**:
- `symbol`: 交易对符号
- `timeframe`: 时间框架（15m, 1h, 4h, 1d）
- `timestamp`: Unix 时间戳（毫秒）
- `open/high/low/close`: OHLC 价格
- `volume`: 成交量

#### 5.2.2 市场衍生指标表

**资金费率表 (`funding_rates`)**
```sql
CREATE TABLE funding_rates (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol TEXT NOT NULL,
    timestamp INTEGER NOT NULL,
    funding_rate NUMERIC NOT NULL,
    next_funding_time INTEGER,
    created_at INTEGER DEFAULT (strftime('%s', 'now')),
    UNIQUE(symbol, timestamp)
);

CREATE INDEX idx_funding_rates_symbol_timestamp
ON funding_rates(symbol, timestamp DESC);
```

**价格快照表 (`price_snapshots`)**
```sql
CREATE TABLE price_snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol TEXT NOT NULL,
    timestamp INTEGER NOT NULL,
    last_price NUMERIC,
    mark_price NUMERIC,
    index_price NUMERIC,
    created_at INTEGER DEFAULT (strftime('%s', 'now')),
    UNIQUE(symbol, timestamp)
);

CREATE INDEX idx_price_snapshots_symbol_timestamp
ON price_snapshots(symbol, timestamp DESC);
```

**未平仓量表 (`open_interest`)**
```sql
CREATE TABLE open_interest (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol TEXT NOT NULL,
    timestamp INTEGER NOT NULL,
    open_interest NUMERIC NOT NULL,
    open_interest_value NUMERIC,
    created_at INTEGER DEFAULT (strftime('%s', 'now')),
    UNIQUE(symbol, timestamp)
);

CREATE INDEX idx_open_interest_symbol_timestamp
ON open_interest(symbol, timestamp DESC);
```

**多空比表 (`long_short_ratio`)**
```sql
CREATE TABLE long_short_ratio (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol TEXT NOT NULL,
    timestamp INTEGER NOT NULL,
    ratio NUMERIC NOT NULL,
    created_at INTEGER DEFAULT (strftime('%s', 'now')),
    UNIQUE(symbol, timestamp)
);

CREATE INDEX idx_long_short_ratio_symbol_timestamp
ON long_short_ratio(symbol, timestamp DESC);
```

#### 5.2.3 LLM 版本与运行记录

**Prompt 版本表 (`prompt_versions`)**
```sql
CREATE TABLE prompt_versions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    version TEXT NOT NULL,
    content TEXT NOT NULL,
    created_at INTEGER DEFAULT (strftime('%s', 'now')),
    UNIQUE(name, version)
);
```

**模型版本表 (`model_versions`)**
```sql
CREATE TABLE model_versions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    version TEXT NOT NULL,
    metadata TEXT,
    created_at INTEGER DEFAULT (strftime('%s', 'now')),
    UNIQUE(name, version)
);
```

**LLM 运行记录表 (`llm_runs`)**
```sql
CREATE TABLE llm_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    prompt_version_id INTEGER,
    model_version_id INTEGER,
    timestamp INTEGER NOT NULL,
    request TEXT,
    response TEXT,
    status TEXT,
    latency_ms INTEGER,
    created_at INTEGER DEFAULT (strftime('%s', 'now')),
    FOREIGN KEY (prompt_version_id) REFERENCES prompt_versions(id),
    FOREIGN KEY (model_version_id) REFERENCES model_versions(id)
);
```

#### 5.2.4 决策记录表 (`decisions`)

```sql
CREATE TABLE decisions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol TEXT NOT NULL,
    timeframe TEXT NOT NULL,
    timestamp INTEGER NOT NULL,
    action TEXT NOT NULL,              -- 操作 (buy, sell, hold)
    confidence REAL,                   -- 置信度 (0-1)
    reasoning TEXT,                    -- 决策理由
    technical_analysis TEXT,           -- 技术分析结果 (JSON)
    risk_assessment TEXT,              -- 风险评估 (JSON)
    llm_response TEXT,                 -- LLM 原始响应
    llm_run_id INTEGER,
    prompt_version_id INTEGER,
    model_version_id INTEGER,
    created_at INTEGER DEFAULT (strftime('%s', 'now')),
    FOREIGN KEY (llm_run_id) REFERENCES llm_runs(id),
    FOREIGN KEY (prompt_version_id) REFERENCES prompt_versions(id),
    FOREIGN KEY (model_version_id) REFERENCES model_versions(id)
);

CREATE INDEX idx_decisions_symbol_timestamp
ON decisions(symbol, timestamp DESC);
```

#### 5.2.5 实盘订单表 (`orders`)

```sql
CREATE TABLE orders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol TEXT NOT NULL,
    side TEXT NOT NULL,                -- buy / sell
    type TEXT NOT NULL,                -- market / limit
    price NUMERIC,                     -- 市价单可为空
    amount NUMERIC NOT NULL,
    leverage NUMERIC,
    status TEXT NOT NULL,              -- new / partial / filled / canceled / rejected
    client_order_id TEXT,
    exchange_order_id TEXT,
    time_in_force TEXT,
    created_at INTEGER DEFAULT (strftime('%s', 'now')),
    updated_at INTEGER
);

CREATE INDEX idx_orders_symbol_created_at
ON orders(symbol, created_at DESC);
```

#### 5.2.6 订单生命周期表 (`order_lifecycle_events`)

```sql
CREATE TABLE order_lifecycle_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id INTEGER NOT NULL,
    status TEXT NOT NULL,
    message TEXT,
    timestamp INTEGER NOT NULL,
    created_at INTEGER DEFAULT (strftime('%s', 'now')),
    FOREIGN KEY (order_id) REFERENCES orders(id)
);

CREATE INDEX idx_order_lifecycle_events_order_id
ON order_lifecycle_events(order_id, timestamp DESC);
```

#### 5.2.7 实盘成交表 (`trades`)

```sql
CREATE TABLE trades (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id INTEGER NOT NULL,
    symbol TEXT NOT NULL,
    side TEXT NOT NULL,                -- buy / sell
    price NUMERIC NOT NULL,
    amount NUMERIC NOT NULL,
    fee NUMERIC,
    fee_currency TEXT,
    realized_pnl NUMERIC,
    timestamp INTEGER NOT NULL,
    created_at INTEGER DEFAULT (strftime('%s', 'now')),
    FOREIGN KEY (order_id) REFERENCES orders(id)
);

CREATE INDEX idx_trades_symbol_timestamp
ON trades(symbol, timestamp DESC);
```

#### 5.2.8 实盘持仓表 (`positions`)

```sql
CREATE TABLE positions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol TEXT NOT NULL,
    side TEXT NOT NULL,                -- long / short
    size NUMERIC NOT NULL,
    entry_price NUMERIC NOT NULL,
    leverage NUMERIC,
    unrealized_pnl NUMERIC,
    margin NUMERIC,
    liquidation_price NUMERIC,
    updated_at INTEGER DEFAULT (strftime('%s', 'now'))
);

CREATE INDEX idx_positions_symbol_updated_at
ON positions(symbol, updated_at DESC);
```

#### 5.2.9 持仓快照表 (`position_snapshots`)

```sql
CREATE TABLE position_snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol TEXT NOT NULL,
    timestamp INTEGER NOT NULL,
    side TEXT NOT NULL,
    size NUMERIC NOT NULL,
    entry_price NUMERIC,
    mark_price NUMERIC,
    unrealized_pnl NUMERIC,
    leverage NUMERIC,
    margin NUMERIC,
    liquidation_price NUMERIC,
    created_at INTEGER DEFAULT (strftime('%s', 'now')),
    UNIQUE(symbol, timestamp, side)
);

CREATE INDEX idx_position_snapshots_symbol_timestamp
ON position_snapshots(symbol, timestamp DESC);
```

#### 5.2.10 账户余额表 (`balances`)

```sql
CREATE TABLE balances (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    currency TEXT NOT NULL,
    timestamp INTEGER NOT NULL,
    total NUMERIC NOT NULL,
    free NUMERIC,
    used NUMERIC,
    created_at INTEGER DEFAULT (strftime('%s', 'now')),
    UNIQUE(currency, timestamp)
);

CREATE INDEX idx_balances_currency_timestamp
ON balances(currency, timestamp DESC);
```

#### 5.2.11 风控事件表 (`risk_events`)

```sql
CREATE TABLE risk_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol TEXT NOT NULL,
    timestamp INTEGER NOT NULL,
    level TEXT NOT NULL,
    rule TEXT NOT NULL,
    details TEXT,
    created_at INTEGER DEFAULT (strftime('%s', 'now'))
);

CREATE INDEX idx_risk_events_symbol_timestamp
ON risk_events(symbol, timestamp DESC);
```

#### 5.2.12 采集运行表 (`ingestion_runs`)

```sql
CREATE TABLE ingestion_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source TEXT NOT NULL,
    symbol TEXT NOT NULL,
    timeframe TEXT,
    data_type TEXT NOT NULL,
    started_at INTEGER NOT NULL,
    ended_at INTEGER,
    rows_inserted INTEGER,
    status TEXT NOT NULL,
    error TEXT
);

CREATE INDEX idx_ingestion_runs_symbol_started_at
ON ingestion_runs(symbol, started_at DESC);
```

#### 5.2.13 回测配置表 (`backtest_configs`)

```sql
CREATE TABLE backtest_configs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    symbol TEXT NOT NULL,
    timeframe TEXT NOT NULL,
    start_time INTEGER NOT NULL,
    end_time INTEGER NOT NULL,
    initial_capital NUMERIC NOT NULL,
    commission_rate NUMERIC NOT NULL,
    strategy_params TEXT,              -- 策略参数 (JSON)
    created_at INTEGER DEFAULT (strftime('%s', 'now'))
);
```

#### 5.2.14 回测结果表 (`backtest_results`)

```sql
CREATE TABLE backtest_results (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    config_id INTEGER NOT NULL,
    total_return NUMERIC,
    max_drawdown NUMERIC,
    sharpe_ratio NUMERIC,
    profit_factor NUMERIC,
    total_trades INTEGER,
    profitable_trades INTEGER,
    win_rate NUMERIC,
    final_equity NUMERIC,
    equity_curve TEXT,                 -- 权益曲线 (JSON)
    trade_log TEXT,                    -- 交易记录 (JSON)
    created_at INTEGER DEFAULT (strftime('%s', 'now')),
    FOREIGN KEY (config_id) REFERENCES backtest_configs(id)
);
```

#### 5.2.15 回测订单表 (`backtest_orders`)

```sql
CREATE TABLE backtest_orders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    backtest_id INTEGER NOT NULL,
    timestamp INTEGER NOT NULL,
    side TEXT NOT NULL,                -- buy / sell
    price NUMERIC NOT NULL,
    amount NUMERIC NOT NULL,
    fee NUMERIC NOT NULL,
    pnl NUMERIC,
    created_at INTEGER DEFAULT (strftime('%s', 'now')),
    FOREIGN KEY (backtest_id) REFERENCES backtest_results(id)
);
```

#### 5.2.16 回测持仓表 (`backtest_positions`)

```sql
CREATE TABLE backtest_positions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    backtest_id INTEGER NOT NULL,
    timestamp INTEGER NOT NULL,
    side TEXT NOT NULL,                -- long / short
    amount NUMERIC NOT NULL,
    entry_price NUMERIC NOT NULL,
    current_price NUMERIC,
    unrealized_pnl NUMERIC,
    stop_loss NUMERIC,
    take_profit NUMERIC,
    created_at INTEGER DEFAULT (strftime('%s', 'now')),
    FOREIGN KEY (backtest_id) REFERENCES backtest_results(id)
);
```

#### 5.2.17 回测决策表 (`backtest_decisions`)

```sql
CREATE TABLE backtest_decisions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    backtest_id INTEGER NOT NULL,
    timestamp INTEGER NOT NULL,
    action TEXT NOT NULL,
    confidence REAL,
    reasoning TEXT,
    created_at INTEGER DEFAULT (strftime('%s', 'now')),
    FOREIGN KEY (backtest_id) REFERENCES backtest_results(id)
);
```

### 5.3 数据库关系图

```
market_data (OHLCV)
  ├─→ decisions (策略决策)
  └─→ backtest_configs → backtest_results
        ├─→ backtest_orders
        ├─→ backtest_positions
        └─→ backtest_decisions

orders → trades
positions → position_snapshots

prompt_versions / model_versions → llm_runs → decisions

funding_rates / price_snapshots / open_interest / long_short_ratio
balances / risk_events / ingestion_runs
```

---
## 6. API 设计

### 6.1 API 基础信息

- **基础 URL**: `http://localhost:8000/api`
- **认证方式**: API Key (可选)
- **数据格式**: JSON
- **HTTP 方法**: GET, POST, PUT, DELETE

### 6.2 API 端点列表

#### 6.2.1 市场数据 API

**获取最新市场数据**
```
GET /api/market/latest
Query Parameters:
  - symbol: 交易对 (必填)
  - timeframe: 时间框架 (可选, 默认 1h)
  - limit: 返回数量 (可选, 默认 100)

Response:
{
  "success": true,
  "data": [
    {
      "timestamp": 1704268800000,
      "open": 42000.0,
      "high": 42500.0,
      "low": 41800.0,
      "close": 42300.0,
      "volume": 1234.56
    }
  ]
}
```

**触发数据采集**
```
POST /api/market/collect
Body:
{
  "symbol": "BTC/USDT:USDT",
  "timeframe": "1h",
  "update_only": true
}

Response:
{
  "success": true,
  "message": "Data collection started",
  "data": {
    "fetched": 100,
    "inserted": 50
  }
}
```

**获取数据统计**
```
GET /api/market/stats

Response:
{
  "success": true,
  "data": {
    "tables": [
      {
        "symbol": "BTC/USDT:USDT",
        "timeframe": "1h",
        "count": 8760,
        "start_time": "2024-01-01 00:00:00",
        "end_time": "2025-01-01 00:00:00"
      }
    ]
  }
}
```

#### 6.2.2 决策生成 API

**生成交易决策**
```
POST /api/decision/generate
Body:
{
  "symbol": "BTC/USDT:USDT",
  "timeframe": "1h",
  "strategy": "balanced"
}

Response:
{
  "success": true,
  "data": {
    "action": "buy",
    "confidence": 0.75,
    "reasoning": "技术指标显示超卖，建议做多",
    "technical_analysis": {
      "rsi": 28.5,
      "macd": {"macd": -120, "signal": -150, "histogram": 30},
      "ema_5": 42000,
      "ema_20": 42500
    },
    "risk_assessment": {
      "passed": true,
      "checks": [...]
    }
  }
}
```

**获取决策历史**
```
GET /api/decision/history
Query Parameters:
  - symbol: 交易对 (可选)
  - limit: 返回数量 (可选, 默认 50)

Response:
{
  "success": true,
  "data": [
    {
      "id": 1,
      "symbol": "BTC/USDT:USDT",
      "timestamp": 1704268800000,
      "action": "buy",
      "confidence": 0.75,
      "reasoning": "..."
    }
  ]
}
```

#### 6.2.3 回测管理 API

**创建回测任务**
```
POST /api/backtest/create
Body:
{
  "name": "BTC MA Cross Strategy",
  "symbol": "BTC/USDT:USDT",
  "timeframe": "1h",
  "start_time": "2024-01-01T00:00:00Z",
  "end_time": "2024-12-31T23:59:59Z",
  "initial_capital": 10000,
  "commission_rate": 0.0006,
  "strategy_params": {
    "ma_short": 5,
    "ma_long": 20
  }
}

Response:
{
  "success": true,
  "data": {
    "config_id": 1,
    "message": "Backtest configuration created"
  }
}
```

**运行回测**
```
POST /api/backtest/run/{config_id}

Response:
{
  "success": true,
  "data": {
    "result_id": 1,
    "total_return": 15.5,
    "max_drawdown": 8.2,
    "sharpe_ratio": 1.35,
    "total_trades": 42,
    "win_rate": 55.5
  }
}
```

**获取回测结果**
```
GET /api/backtest/result/{result_id}

Response:
{
  "success": true,
  "data": {
    "id": 1,
    "config_id": 1,
    "total_return": 15.5,
    "max_drawdown": 8.2,
    "sharpe_ratio": 1.35,
    "profit_factor": 1.8,
    "total_trades": 42,
    "profitable_trades": 23,
    "win_rate": 55.5,
    "final_equity": 11550.0,
    "equity_curve": [...],
    "trade_log": [...]
  }
}
```

**获取回测列表**
```
GET /api/backtest/list
Query Parameters:
  - limit: 返回数量 (可选, 默认 20)

Response:
{
  "success": true,
  "data": [
    {
      "id": 1,
      "name": "BTC MA Cross Strategy",
      "symbol": "BTC/USDT:USDT",
      "total_return": 15.5,
      "created_at": 1704268800
    }
  ]
}
```

### 6.3 错误响应格式

```json
{
  "success": false,
  "error": {
    "code": "INVALID_PARAMETER",
    "message": "Invalid symbol format",
    "details": "Symbol must be in format XXX/YYY:ZZZ"
  }
}
```

### 6.4 错误代码列表

| 错误代码 | HTTP 状态码 | 说明 |
|---------|-----------|------|
| INVALID_PARAMETER | 400 | 参数错误 |
| UNAUTHORIZED | 401 | 未授权 |
| NOT_FOUND | 404 | 资源不存在 |
| RATE_LIMIT_EXCEEDED | 429 | 请求频率超限 |
| INTERNAL_ERROR | 500 | 内部错误 |
| EXTERNAL_API_ERROR | 502 | 外部 API 错误 |

---

## 7. 部署架构

### 7.1 开发环境

```
┌─────────────────────────────────┐
│  开发机器                        │
│  ┌───────────────────────────┐  │
│  │  Python 3.11+             │  │
│  │  SQLite                   │  │
│  │  FastAPI (开发服务器)     │  │
│  └───────────────────────────┘  │
└─────────────────────────────────┘
```

### 7.2 生产环境

```
┌─────────────────────────────────────────────────────────┐
│  负载均衡器 (Nginx)                                      │
└─────────────┬───────────────────────────────────────────┘
              │
    ┌─────────┴─────────┐
    │                   │
┌───▼────┐         ┌────▼───┐
│ FastAPI│         │ FastAPI│
│ 实例 1 │         │ 实例 2 │
└───┬────┘         └────┬───┘
    │                   │
    └─────────┬─────────┘
              │
    ┌─────────▼─────────┐
    │  PostgreSQL       │
    │  (主数据库)       │
    └───────────────────┘
              │
    ┌─────────▼─────────┐
    │  Redis            │
    │  (缓存)           │
    └───────────────────┘
```

### 7.3 Docker 部署

```yaml
version: '3.8'

services:
  api:
    build: .
    ports:
      - "8000:8000"
    environment:
      - DATABASE_URL=postgresql://user:pass@db:5432/alpha_arena
      - REDIS_URL=redis://redis:6379/0
    depends_on:
      - db
      - redis
  
  db:
    image: postgres:15
    volumes:
      - postgres_data:/var/lib/postgresql/data
    environment:
      - POSTGRES_USER=user
      - POSTGRES_PASSWORD=pass
      - POSTGRES_DB=alpha_arena
  
  redis:
    image: redis:7
    volumes:
      - redis_data:/data

volumes:
  postgres_data:
  redis_data:
```

---

## 8. 技术栈

### 8.1 后端技术

| 技术 | 版本 | 用途 |
|------|------|------|
| Python | 3.11+ | 主要编程语言 |
| FastAPI | 0.104+ | Web 框架 |
| Pydantic | 2.0+ | 数据验证 |
| SQLAlchemy | 2.0+ | ORM (可选) |
| ccxt | 4.0+ | 交易所 API |
| pandas | 2.0+ | 数据处理 |
| numpy | 1.24+ | 数值计算 |
| ta-lib | 0.4+ | 技术指标 (可选) |

### 8.2 数据库

| 技术 | 版本 | 用途 |
|------|------|------|
| SQLite | 3.40+ | 开发/测试数据库 |
| PostgreSQL | 15+ | 生产数据库 (可选) |
| Redis | 7+ | 缓存 (可选) |

### 8.3 前端技术

| 技术 | 版本 | 用途 |
|------|------|------|
| HTML5 | - | 页面结构 |
| CSS3 | - | 样式 |
| JavaScript | ES6+ | 交互逻辑 |
| Chart.js | 4.0+ | 图表可视化 |

### 8.4 外部服务

| 服务 | 用途 |
|------|------|
| OKX API | 市场数据和交易 |
| DeepSeek API | LLM 服务 |
| Qwen (本地) | 本地 LLM (可选) |

### 8.5 开发工具

| 工具 | 用途 |
|------|------|
| pytest | 单元测试 |
| black | 代码格式化 |
| flake8 | 代码检查 |
| mypy | 类型检查 |
| pre-commit | Git 钩子 |

---

## 9. 下一步计划

### 9.1 短期目标（1-2周）

  - [ ] 完善技术分析模块
  - [ ] 建立强化学习/离线训练任务（离线评估 + 策略评分）
- [ ] 集成 LLM 决策引擎
- [ ] 实现完整的风险管理系统
- [ ] 优化回测引擎性能

### 9.2 中期目标（1-2月）

- [ ] 实现实盘交易功能
- [ ] 开发 Web 可视化界面
- [ ] 添加更多技术指标
- [ ] 实现策略参数优化

### 9.3 长期目标（3-6月）

- [ ] 实现分布式回测
- [ ] 添加机器学习模型
- [ ] 构建策略社区

---

## 10. 参考资料

- [FastAPI 文档](https://fastapi.tiangolo.com/)
- [ccxt 文档](https://docs.ccxt.com/)
- [OKX API 文档](https://www.okx.com/docs-v5/en/)
- [DeepSeek API 文档](https://platform.deepseek.com/docs)
- [技术分析指标](https://www.investopedia.com/technical-analysis-4689657)

---

**文档结束**








