# 比特币交易策略库 - 专为加密货币市场设计

> **版本**: v1.0  
> **更新日期**: 2026-01-03  
> **适用市场**: 比特币 (BTC) 永续合约  
> **交易所**: OKX（模拟盘）

---

## 目录

1. [加密货币市场特点](#1-加密货币市场特点)
2. [策略库概览](#2-策略库概览)
3. [详细策略设计](#3-详细策略设计)
4. [代码实现](#4-代码实现)

---

## 1. 加密货币市场特点

### 1.1 与股市的核心区别

| 特征 | 股市 | 加密货币市场 |
|------|------|-------------|
| **交易时间** | 工作日 9:30-16:00 | 7x24 小时不间断 |
| **波动率** | 日波动 1-3% | 日波动 5-15% |
| **涨跌幅限制** | 有（±10%/20%） | 无限制 |
| **做空机制** | 需要借券 | 永续合约随时做空 |
| **杠杆** | 最高 2-5 倍 | 最高 125 倍 |
| **资金费率** | 无 | 每 8 小时结算一次 |
| **流动性** | 高 | 主流币高，山寨币低 |
| **市场情绪** | 理性为主 | 情绪化严重 |
| **新闻影响** | 中等 | 极大（马斯克推特） |
| **技术分析有效性** | 中等 | 较高 |

### 1.2 比特币市场的独特特征

#### 1.2.1 永续合约资金费率

**什么是资金费率？**
- 多头和空头之间的资金交换
- 正费率：多头付给空头（市场看多）
- 负费率：空头付给多头（市场看空）
- 每 8 小时结算一次（00:00, 08:00, 16:00 UTC）

**交易机会**：
- 资金费率 > 0.1%：市场过度看多，考虑做空
- 资金费率 < -0.05%：市场过度看空，考虑做多
- 资金费率套利：现货做多 + 永续做空

#### 1.2.2 高波动率

**日内波动特征**：
- 早上 8-10 点（北京时间）：波动较大（欧美收盘）
- 晚上 9-11 点（北京时间）：波动较大（美股开盘）
- 周末：流动性降低，容易插针

**策略影响**：
- 止损要设置得更宽（3-5%）
- 仓位要更小（单笔 10-15%）
- 适合短线交易（4h-1d）

#### 1.2.3 链上数据

**独特的数据源**：
- 交易所流入流出量
- 巨鲸地址动向
- 矿工抛售压力
- UTXO 年龄分布
- 持币地址数量

**交易信号**：
- 交易所流入量激增 → 抛售压力大
- 巨鲸地址增持 → 看多信号
- 矿工余额下降 → 抛售压力

#### 1.2.4 市场周期

**4 年减半周期**：
- 减半前 6-12 个月：牛市启动
- 减半后 12-18 个月：牛市顶峰
- 之后 1-2 年：熊市
- 当前周期：2024 年 4 月减半

**季节性规律**：
- Q1（1-3月）：通常上涨
- Q2（4-6月）：震荡
- Q3（7-9月）：通常回调
- Q4（10-12月）：通常上涨

#### 1.2.5 关键价格位

**心理价位**：
- 整数关口：$90,000, $100,000, $110,000
- 历史高点：$69,000（2021年11月）
- 成本价位：矿工成本约 $25,000-$30,000

---

## 2. 策略库概览

### 2.1 策略分类

针对比特币市场，我设计了 **10 大类策略**：

| 策略类型 | 适用场景 | 风险等级 | 预期收益 | 推荐度 |
|---------|---------|---------|---------|--------|
| **1. 趋势跟踪** | 明显趋势 | 中 | 中-高 | ⭐⭐⭐⭐⭐ |
| **2. 震荡区间** | 横盘震荡 | 低-中 | 中 | ⭐⭐⭐⭐ |
| **3. 突破交易** | 关键位突破 | 中-高 | 高 | ⭐⭐⭐⭐ |
| **4. 资金费率套利** | 费率极端 | 低 | 低-中 | ⭐⭐⭐⭐⭐ |
| **5. 网格交易** | 震荡市 | 低 | 低-中 | ⭐⭐⭐⭐ |
| **6. 动量交易** | 强势行情 | 高 | 高 | ⭐⭐⭐ |
| **7. 均值回归** | 超买超卖 | 中 | 中 | ⭐⭐⭐⭐ |
| **8. 链上信号** | 巨鲸异动 | 中 | 中-高 | ⭐⭐⭐ |
| **9. 时间周期** | 特定时段 | 低-中 | 低-中 | ⭐⭐⭐ |
| **10. 波动率交易** | 高波动 | 高 | 高 | ⭐⭐⭐ |

---

## 3. 详细策略设计

下面我按“可落地的系统架构”把你这份 **BTC 永续合约策略备忘录**整体升级成一套更合理、更一致、可直接接回测/实盘框架的 **Strategy Spec v1.0**。
你可以先只启用 3 个策略（EMA 趋势、布林震荡、资金费率套利），但**架构里把所有策略都写全**，后续逐个打开即可。

---

# 0. 总体设计目标（你这套策略现在最缺的就是“系统层一致性”）

1. **统一口径**：所有指标窗口以 *bar 数* 表达（不混“20日/20根”）。
2. **风险先行**：仓位 = “按止损距离反推的风险仓位”，不是固定 20% 这种。
3. **择时/分流**：先判断市场状态（趋势/震荡/突破/高波动），再启用对应策略。
4. **冲突控制**：同一品种同一时刻，明确“只能一个策略持仓”或“可叠加但净敞口受限”。
5. **把交易成本写进规则**：手续费、滑点、资金费率、基差、执行价（mark/last）都要规定。

> 你原文里的“历史表现/胜率/夏普”等，我建议都标注为 **占位符**，必须在统一成本模型与执行规则后再回测，不然会过度乐观。

---

# 1. 全局统一定义（指标、成本、执行）

## 1.1 数据与指标口径（统一用 bar）

* timeframe ∈ {15m, 1h, 4h, 1d}
* `ATR(n)`：n 根K线（常用 14）
* `RSI(n)`：n 根K线（常用 14）
* `EMA(n)`：n 根K线（如 9/21/55）
* `MACD(fast, slow, signal)`：默认 (12,26,9)，柱 = macd - signal
* `BB(period, std)`：默认 (20,2)
* `BB_width = (upper-lower)/mid`（百分比口径）
* `ATR_pct = ATR(14)/close`

**成交量口径（关键）：**
不再写“20日均量”，统一写：`vol_sma = SMA(volume, N_bars)`

* 4h 下如果你想近似“20天”，就用 `N_bars = 20*6 = 120`
* 1d 下“20天”就是 `N_bars=20`

## 1.2 成本与执行（回测/实盘必须一致）

至少定义：

* `fee_maker`, `fee_taker`
* `slippage_bps`（可按波动/成交量动态）
* `use_mark_price_for_risk`：止损/强平逻辑用 mark price（建议 True）
* `funding_rate`：按交易所规则（8h/1h）计入 PnL
* `spread_model`：简单版可用固定 bps，进阶用盘口估计

---

# 2. 全局风控引擎（所有策略共享）

核心：**用“单笔风险”决定仓位**，并加全局熔断/限额。

## 2.1 单笔风险仓位（推荐）

* `risk_per_trade_pct = 0.5% ~ 1.0%`（账户权益）
* 止损距离（以价格计）：`stop_dist = k * ATR`
* 名义仓位（简化表达）：

  * `notional = (equity * risk_per_trade_pct) / stop_dist * price`
* 实盘还要考虑合约面值、最小下单量、杠杆与保证金模式（逐仓/全仓）

## 2.2 全局约束（非常关键）

* `max_leverage`（你写 2~3 可保留）
* `max_net_notional_pct`：净敞口上限（例如 100%~150% equity）
* `max_gross_notional_pct`：总敞口上限（例如 200%）
* `max_positions_per_symbol = 1`（强烈建议 BTC/USDT 永续先这样做，避免策略打架）
* `max_daily_loss_pct`：例如 -2% 触发当日停止开新仓
* `max_weekly_drawdown_pct`：例如 -6% 限制风险
* `cooldown_after_losses`：连续亏损 N 次，暂停 X 根K线

---

# 3. 市场状态识别（Regime Filter，决定启用哪些策略）

给你一套简单可落地、可调参的判别：

## 3.1 指标

* 趋势强度：`ADX(14)`（建议用 4h/1d）
* 震荡压缩：`BB_width(20,2)`
* 波动水平：`ATR_pct = ATR(14)/close`

## 3.2 规则（示例）

* **TREND（趋势）**：

  * `ADX(14) > 20` 且 `BB_width` 上升 或 `EMA55_slope` 显著
* **RANGE（震荡）**：

  * `ADX(14) < 18` 且 `BB_width < bw_threshold`
* **BREAKOUT（突破）**：

  * `BB_width` 处于近 N 根低分位（挤压） + 价格破关键位 + 放量
* **HIGH_VOL（极端波动）**：

  * `ATR_pct > vol_kill_threshold`（如 > 6%（4h）或你自行标定）

## 3.3 启用映射

* TREND：EMA趋势、MACD确认、突破
* RANGE：布林震荡、支撑阻力、RSI均值回归、网格
* BREAKOUT：关键位突破、整数关口
* HIGH_VOL：只允许减仓/套利（或趋势策略降风险），禁用均值回归与窄网格

---

# 4. 策略编排器（解决策略冲突与“先做3个也能兼容未来”）

建议 BTC/USDT 永续 **V1 规则**：

* `max_positions_per_symbol = 1`
* 同一时间只允许一个策略持仓；当多个策略同向触发，用优先级选择：

优先级建议：

1. 资金费率套利（若启用，通常为对冲型，单独管理）
2. 突破（BREAKOUT）
3. 趋势（TREND）
4. 震荡/均值回归（RANGE）
5. 网格（RANGE 且低波动）

> 网格和均值回归最容易在趋势启动时被碾压，优先级应最低，并且有“趋势检测强制退出”。

---

# 5. 各策略逐一完善（按你原策略编号保留，但口径统一、加缺失项）

下面每个策略都统一包含：**适用 Regime / 入场 / 出场 / 止损止盈 / 时间止损 / 仓位 / 备注**。

---

## 策略 1：趋势跟踪

### 3.1.1 EMA(9/21/55) 趋势跟踪（推荐保留）

**适用 Regime：TREND（且非 HIGH_VOL）**
**时间框架：4h, 1d**

**入场（做多）**

1. `EMA9 > EMA21 > EMA55`
2. `close > EMA9`
3. `EMA55_slope > 0`（用 EMA55 今日值-前值 或 回归斜率）
4. `MACD_hist > 0` 且 `MACD_hist` 连续放大（>=2 根即可，3 根太严格）
5. `volume > SMA(volume, N) * vol_mult`（N 用 bar 数，4h 常用 120；1d 用 20）
6. 追高过滤：`(close - EMA9) < dist_atr_mult * ATR(14)`（如 1.2 ATR）

**出场**

* 结构破坏：`close < EMA21` 或 `EMA9 < EMA21`
* 止损：`entry - stop_loss_atr * ATR(14)`
* 止盈：`entry + take_profit_atr * ATR(14)`（也可只用移动止损，不用固定止盈）
* 时间止损：入场后 `M` 根K线未达到 `+1*ATR` 浮盈则退出/减半（防磨损）

**移动止损（推荐）**

* `trail = max(trail, highest_since_entry - trailing_atr*ATR(14))`

**仓位（风险驱动）**

* `risk_per_trade_pct` + `stop_loss_atr` 反推 notional

---

### 3.1.2 MACD 趋势确认策略（把绝对阈值改成归一化）

**适用 Regime：TREND / BREAKOUT 初期**
**时间框架：1h, 4h**

**入场（做多）**

1. MACD 金叉（macd 上穿 signal）
2. `MACD_hist` 连续放大 ≥ 2 根
3. `close > EMA50`
4. `RSI(14) > 50`
5. 柱体强度用归一化而非 “50”：

   * 例：`MACD_hist_zscore(200) > 1.0` 或 `MACD_hist/close > hist_pct`

**出场**

* MACD 死叉
* 止损：`k*ATR`（优于固定 3%）
* 止盈：`m*ATR` 或 移动止损
* 时间止损：N 根未走出趋势则退出

---

## 策略 2：震荡区间

### 3.2.1 布林带震荡（推荐保留）

**适用 Regime：RANGE（必须满足）**
**时间框架：1h, 4h**

**入场（做多）**

1. `ADX(14) < 18`
2. `BB_width < bw_threshold`（你原来 <4% 可以保留，但建议按 timeframe 标定）
3. 触下轨：`close < lower * (1 + tol)` 或 `z = (close-mid)/std <= -2`
4. `RSI(14) < 35`
5. 恐慌过滤（可选）：`volume < SMA(volume,N)*panic_mult`（避免暴跌接刀）

**出场**

* 回中轨：`close >= mid` 或 `z >= 0`
* 止损：`max(2% , k*ATR)`（建议用 ATR 为主）
* 时间止损：T 根未回归则退出（防趋势启动）

**强制退出**

* 若触发 TREND 判定（ADX 上升并 >20 或 EMA55 斜率转强），立即平仓并禁用该策略一段 cooldown

---

### 3.2.2 支撑阻力区间策略（补齐“关键位识别算法”）

**适用 Regime：RANGE（或趋势回调段）**
**关键位识别（建议选一种可实现的）**

* Pivot 法（最易实现）：

  * 支撑 = 最近 `k` 根的 swing low（两侧各 r 根更低/更高判定）
  * 阻力 = swing high
* 叠加过滤：只保留成交量集中或多次触及的价位（touch count）

**入场（做多）**

1. `abs(close - support)/support < 1%`
2. 出现拒绝信号：长下影/吞没等（你原来写得对）
3. `RSI < 40`
4. `volume > SMA(volume,N)*1.2`

**出场**

* 到下一个阻力位
* 止损：跌破支撑 `buffer = max(1.5%, k*ATR)`
* 时间止损：N 根不反弹则退出

---

## 策略 3：突破交易

### 3.3.1 关键位突破（推荐保留，但要加“挤压+回踩失败退出”）

**适用 Regime：BREAKOUT**
**时间框架：4h, 1d**

**入场（做多）**

1. 突破前挤压：`BB_width` 处于过去 `N` 根低分位（如 20%分位）
2. `close > resistance * 1.005`（用收盘确认，减少假突破）
3. 放量：`volume > SMA(volume,N)*1.5`
4. K线实体：`abs(close-open)/open > 0.02`
5. `RSI > 60` 且 `MACD_hist > 0`

**出场**

* 回踩失败退出（更明确）：

  * 突破后回踩，若 `close < resistance` 连续 2 根 → 退出
* 止损：`min( resistance - k*ATR , entry*(1-stop_pct) )`（建议用 ATR 贴合波动）
* 止盈：可用 `take_profit_pct` 或 “分批止盈 + 移动止损”
* 时间止损：突破后 M 根K线不延续（未创新高/未走出 1*ATR）→ 退出

---

### 3.3.2 整数关口突破（本质是 3.3.1 的特例）

补齐：把 “连续2根收盘站上” 作为确认；同时加“失败退出”：

* 若 2 根后又有 1 根收盘跌回关口下方 → 退出（不等止损）

---

## 策略 4：资金费率套利（必须改写风险表述与基差控制）

### 3.4.1 正向套利（资金费率过高：现货多 + 永续空）

**适用 Regime：任意，但通常在情绪极端时出现**
**这是低方向风险，不是无风险。风险核心=基差与执行。**

**入场条件**

1. `funding_rate_8h > fr_enter`（如 0.10%）
2. `abs(basis) < basis_max`（basis = perp_mid/spot_mid - 1；如 <0.5%）
3. 条件持续 `>= K` 个结算周期（如 2~3）

**持仓与再平衡**

* 对冲目标：`delta ~ 0`
* 再平衡阈值：`abs(delta) > rebalance_threshold` 或 `abs(basis) > basis_rebalance`

**退出条件（关键）**

1. `funding_rate < fr_exit`（如 0.05%）
2. `abs(basis) > basis_stop`（如 1.5%~2%）立刻减仓/退出
3. 流动性恶化/插针：触发风险开关退出

**仓位**

* 不建议高杠杆（1x 为主）
* `max_arbitrage_notional_pct`（如 30%~50% equity），并受全局敞口约束

---

### 3.4.2 反向套利（资金费率为负：永续多 + 现货空）

**注意：现货做空往往涉及借币成本/可借量/利率**
若你没有稳定借币通道，建议把它写成“可选模块”，或者改为“期货/交割合约对冲”结构。

---

## 策略 5：网格交易（只允许在 RANGE 且低波动）

网格最重要的是：**趋势检测强制退出 + 网格重心动态更新**。

### 3.5.1 等差网格

**适用 Regime：RANGE 且 ATR_pct 中低、BB_width 低**
**网格区间建议动态而不是手写 85000-95000：**

* `lower = mid - k*ATR`，`upper = mid + k*ATR` 或 用最近 N 根高低点的分位数

**强制退出**

* 若 `ADX>20` 或价格突破区间并延续（2 根收盘在区间外）→ 平仓止损
* 网格止损不建议写“跌破区间10%”，更应与波动相关：`stop = upper/lower +/- k*ATR`

---

### 3.5.2 动态网格（把 spacing 写成 ATR/波动函数更一致）

推荐直接用：

* `grid_spacing_pct = clip(a*ATR_pct, min_pct, max_pct)`
  比你现在“0.5/1/2%”更稳健。

---

## 策略 6：动量（放量追击，必须严格风控）

### 3.6.1 突然放量动量

**适用 Regime：BREAKOUT / NEWS_VOL（可视作 HIGH_VOL 的子类，但要小仓位）**
**入场**

1. `return_1bar > 3%`（按 timeframe 调参）
2. `volume > SMA(volume,N)*3`
3. 价格突破近 `M` 根高点（例如 20 根 Donchian）
4. 不在极端追高：`distance_to_vwap` 或 `distance_to_ema` 限制（可选）

**出场**

* 时间止盈：持有 1~2 小时/若干根 bar
* 小止损：`k*ATR` 或 1.5%（保守）
* 分批止盈 + 跟踪止损（比固定 2.5%更稳）

---

## 策略 7：均值回归（必须绑定 RANGE）

### 3.7.1 RSI 超买超卖

**适用 Regime：RANGE（强制）**

* 入场建议加“止跌确认”，避免下跌趋势里抄底：

  * RSI<30 且出现“更高低点/吞没”之一
  * 或 `zscore <= -2`（靠近布林下轨）

**出场**

* RSI 回到 50 或 zscore 回到 0
* 时间止损：N 根不回归退出

---

## 策略 8：链上信号（建议作为“过滤器/调仓因子”，不要单独当快进快出信号）

### 3.8.1 交易所流入流出

链上数据频率多是日级/小时级，容易滞后。更合理的用法：

* **作为风险开关/偏置因子**：

  * 若 `inflow_z > 2` 且价格在高位（RSI>65）→ 禁止追多、趋势策略减仓
  * 若 `outflow_z > 2` → 允许趋势策略加一点风险预算

单独做空/做多也可以，但建议持仓周期更长（天级），否则噪声太大。

---

# 6. 给你一个“统一配置模板”（你后面接系统最省事）

下面这个 JSON 结构：全局风控 + regime + 策略模块都能容纳。

```json
{
  "global": {
    "symbol": "BTC/USDT:USDT",
    "timeframes": ["15m", "1h", "4h", "1d"],
    "execution": {
      "use_mark_price_for_risk": true,
      "fee_maker": 0.0002,
      "fee_taker": 0.0006,
      "slippage_bps": 3
    },
    "risk": {
      "risk_per_trade_pct": 0.0075,
      "max_leverage": 3,
      "max_positions_per_symbol": 1,
      "max_net_notional_pct": 1.2,
      "max_gross_notional_pct": 2.0,
      "max_daily_loss_pct": 0.02,
      "cooldown_after_losses": { "loss_streak": 3, "cooldown_bars": 24 }
    }
  },
  "regime": {
    "adx_period": 14,
    "trend_adx_on": 20,
    "range_adx_off": 18,
    "bb_period": 20,
    "bb_std": 2,
    "bw_threshold": { "1h": 0.04, "4h": 0.05 },
    "vol_kill_threshold": { "1h": 0.05, "4h": 0.06 }
  },
  "strategies": {
    "ema_trend": {
      "enabled": true,
      "timeframe": "4h",
      "ema": [9, 21, 55],
      "atr_period": 14,
      "stop_loss_atr": 2.0,
      "take_profit_atr": 4.0,
      "trailing_stop": { "enabled": true, "atr_mult": 1.5 },
      "filters": {
        "require_regime": "TREND",
        "max_distance_atr": 1.2,
        "volume_sma_bars": 120,
        "volume_mult": 1.2
      },
      "time_stop": { "bars": 18, "min_favorable_atr": 1.0 }
    },
    "bb_range": {
      "enabled": true,
      "timeframe": "1h",
      "atr_period": 14,
      "stop_loss_atr": 1.5,
      "filters": {
        "require_regime": "RANGE",
        "rsi_oversold": 35,
        "z_entry": -2.0
      },
      "time_stop": { "bars": 24 }
    },
    "funding_arbitrage": {
      "enabled": true,
      "funding_enter": 0.001,
      "funding_exit": 0.0005,
      "basis_max": 0.005,
      "basis_stop": 0.02,
      "max_notional_pct": 0.5,
      "rebalance_delta_threshold": 0.02
    },

    "macd_trend": { "enabled": false },
    "sr_range": { "enabled": false },
    "breakout_keylevel": { "enabled": false },
    "breakout_round": { "enabled": false },
    "grid_fixed": { "enabled": false },
    "grid_dynamic": { "enabled": false },
    "momentum_spike": { "enabled": false },
    "rsi_mean_reversion": { "enabled": false },
    "onchain_flow_filter": { "enabled": false }
  }
}
```

---

# 7. 你先做 3 个策略的“最稳落地路径”（但架构已全）

**V1 实盘/半实盘启用：**

1. EMA 趋势（4h）
2. 布林震荡（1h）
3. 资金费率套利（触发式、1x、严格基差）

**并且强制：**

* `max_positions_per_symbol = 1`（趋势/震荡/突破互斥）
* HIGH_VOL 时禁用震荡与网格
* 每天最大亏损触发后停止开新仓

---




## 4. 代码实现

### 4.1 策略基类

```python
# strategies/base_strategy.py

from abc import ABC, abstractmethod
from typing import Dict, Optional
from dataclasses import dataclass
from enum import Enum


class SignalType(Enum):
    """信号类型"""
    BUY = "buy"
    SELL = "sell"
    HOLD = "hold"
    CLOSE_LONG = "close_long"
    CLOSE_SHORT = "close_short"


@dataclass
class TradingSignal:
    """交易信号"""
    signal_type: SignalType
    confidence: float  # 0-1
    entry_price: float
    stop_loss: float
    take_profit: float
    position_size: float  # 仓位大小（资金百分比）
    leverage: int
    reasoning: str  # 信号理由


class BitcoinStrategy(ABC):
    """比特币交易策略基类"""
    
    def __init__(self, name: str, params: Dict):
        self.name = name
        self.params = params
        self.position = None  # 当前持仓
    
    @abstractmethod
    def analyze(self, market_data: Dict) -> TradingSignal:
        """
        分析市场数据，生成交易信号
        
        Args:
            market_data: 市场数据，包含：
                - price: 当前价格
                - volume: 成交量
                - ohlcv: K线数据
                - indicators: 技术指标
                - funding_rate: 资金费率（可选）
                - onchain_data: 链上数据（可选）
        
        Returns:
            TradingSignal: 交易信号
        """
        pass
    
    def calculate_position_size(
        self,
        capital: float,
        risk_pct: float,
        stop_loss_pct: float
    ) -> float:
        """
        计算仓位大小
        
        Args:
            capital: 总资金
            risk_pct: 风险百分比（单笔最大亏损）
            stop_loss_pct: 止损百分比
        
        Returns:
            仓位大小（USDT）
        """
        # 凯利公式或固定比例
        risk_amount = capital * risk_pct
        position_size = risk_amount / stop_loss_pct
        
        # 限制最大仓位
        max_position = capital * self.params.get('max_position', 0.20)
        return min(position_size, max_position)
    
    def validate_signal(self, signal: TradingSignal, market_data: Dict) -> bool:
        """
        验证信号有效性
        
        Args:
            signal: 交易信号
            market_data: 市场数据
        
        Returns:
            是否有效
        """
        # 基本验证
        if signal.confidence < 0.5:
            return False
        
        # 检查止损止盈设置
        if signal.signal_type == SignalType.BUY:
            if signal.stop_loss >= signal.entry_price:
                return False
            if signal.take_profit <= signal.entry_price:
                return False
        
        return True
```

### 4.2 EMA 趋势跟踪策略实现

```python
# strategies/ema_trend_following.py

from .base_strategy import BitcoinStrategy, TradingSignal, SignalType
import pandas as pd
import numpy as np


class EMATrendFollowingStrategy(BitcoinStrategy):
    """EMA 趋势跟踪策略"""
    
    def __init__(self, params: Dict = None):
        default_params = {
            "ema_fast": 9,
            "ema_medium": 21,
            "ema_slow": 55,
            "atr_period": 14,
            "stop_loss_atr": 2.0,
            "take_profit_atr": 4.0,
            "max_position": 0.20,
            "max_leverage": 3,
            "rsi_min": 50,
            "rsi_max": 70,
            "volume_threshold": 1.2
        }
        if params:
            default_params.update(params)
        
        super().__init__("EMA趋势跟踪", default_params)
    
    def analyze(self, market_data: Dict) -> TradingSignal:
        """分析市场数据"""
        
        # 提取数据
        df = pd.DataFrame(market_data['ohlcv'])
        current_price = market_data['price']
        indicators = market_data['indicators']
        
        # 计算 EMA
        ema_fast = indicators['ema_9']
        ema_medium = indicators['ema_21']
        ema_slow = indicators['ema_55']
        
        # 计算 ATR
        atr = indicators['atr']
        
        # 其他指标
        rsi = indicators['rsi']
        macd = indicators['macd']
        macd_signal = indicators['macd_signal']
        volume = market_data['volume']
        avg_volume = indicators['volume_ma']
        
        # 判断趋势
        is_uptrend = (ema_fast > ema_medium > ema_slow)
        is_downtrend = (ema_fast < ema_medium < ema_slow)
        
        # 做多信号
        if is_uptrend and current_price > ema_fast:
            # 检查其他条件
            macd_bullish = macd > macd_signal and macd > 0
            volume_surge = volume > avg_volume * self.params['volume_threshold']
            rsi_ok = self.params['rsi_min'] < rsi < self.params['rsi_max']
            
            if macd_bullish and volume_surge and rsi_ok:
                # 计算止损止盈
                stop_loss = current_price - (atr * self.params['stop_loss_atr'])
                take_profit = current_price + (atr * self.params['take_profit_atr'])
                
                # 计算仓位
                position_size = self.calculate_position_size(
                    capital=market_data.get('capital', 10000),
                    risk_pct=0.02,
                    stop_loss_pct=(current_price - stop_loss) / current_price
                )
                
                return TradingSignal(
                    signal_type=SignalType.BUY,
                    confidence=0.85,
                    entry_price=current_price,
                    stop_loss=stop_loss,
                    take_profit=take_profit,
                    position_size=position_size,
                    leverage=self.params['max_leverage'],
                    reasoning=f"EMA多头排列，MACD金叉，成交量放大{volume/avg_volume:.2f}倍，RSI={rsi:.1f}"
                )
        
        # 做空信号
        elif is_downtrend and current_price < ema_fast:
            # 检查其他条件
            macd_bearish = macd < macd_signal and macd < 0
            volume_surge = volume > avg_volume * self.params['volume_threshold']
            rsi_ok = 30 < rsi < 50
            
            if macd_bearish and volume_surge and rsi_ok:
                stop_loss = current_price + (atr * self.params['stop_loss_atr'])
                take_profit = current_price - (atr * self.params['take_profit_atr'])
                
                position_size = self.calculate_position_size(
                    capital=market_data.get('capital', 10000),
                    risk_pct=0.02,
                    stop_loss_pct=(stop_loss - current_price) / current_price
                )
                
                return TradingSignal(
                    signal_type=SignalType.SELL,
                    confidence=0.85,
                    entry_price=current_price,
                    stop_loss=stop_loss,
                    take_profit=take_profit,
                    position_size=position_size,
                    leverage=self.params['max_leverage'],
                    reasoning=f"EMA空头排列，MACD死叉，成交量放大，RSI={rsi:.1f}"
                )
        
        # 平仓信号
        if self.position:
            if self.position['side'] == 'long' and current_price < ema_medium:
                return TradingSignal(
                    signal_type=SignalType.CLOSE_LONG,
                    confidence=0.90,
                    entry_price=current_price,
                    stop_loss=0,
                    take_profit=0,
                    position_size=0,
                    leverage=1,
                    reasoning="价格跌破EMA(21)，趋势转弱"
                )
        
        # 持有信号
        return TradingSignal(
            signal_type=SignalType.HOLD,
            confidence=0.0,
            entry_price=current_price,
            stop_loss=0,
            take_profit=0,
            position_size=0,
            leverage=1,
            reasoning="无明确信号"
        )
```

### 4.3 资金费率套利策略实现

```python
# strategies/funding_rate_arbitrage.py

from .base_strategy import BitcoinStrategy, TradingSignal, SignalType


class FundingRateArbitrageStrategy(BitcoinStrategy):
    """资金费率套利策略"""
    
    def __init__(self, params: Dict = None):
        default_params = {
            "min_funding_rate": 0.10,  # 最小费率 0.1%
            "exit_funding_rate": 0.05,  # 退出费率 0.05%
            "max_position": 0.50,  # 最大仓位 50%
            "leverage": 1,  # 不使用杠杆
            "min_duration": 3  # 最少持续 3 个周期
        }
        if params:
            default_params.update(params)
        
        super().__init__("资金费率套利", default_params)
        self.funding_rate_history = []
    
    def analyze(self, market_data: Dict) -> TradingSignal:
        """分析资金费率"""
        
        current_price = market_data['price']
        funding_rate = market_data.get('funding_rate', 0)
        
        # 记录历史费率
        self.funding_rate_history.append(funding_rate)
        if len(self.funding_rate_history) > 10:
            self.funding_rate_history.pop(0)
        
        # 正向套利（费率过高）
        if funding_rate > self.params['min_funding_rate']:
            # 检查持续性
            if len(self.funding_rate_history) >= self.params['min_duration']:
                recent_rates = self.funding_rate_history[-self.params['min_duration']:]
                if all(r > self.params['min_funding_rate'] for r in recent_rates):
                    # 开仓：现货做多 + 永续做空
                    return TradingSignal(
                        signal_type=SignalType.BUY,  # 这里是套利信号
                        confidence=0.95,
                        entry_price=current_price,
                        stop_loss=current_price * 0.98,  # 2% 止损（价差风险）
                        take_profit=0,  # 无止盈，持续收费率
                        position_size=self.params['max_position'],
                        leverage=1,
                        reasoning=f"资金费率={funding_rate*100:.2f}%，年化收益={funding_rate*3*365*100:.1f}%"
                    )
        
        # 平仓信号
        if self.position and funding_rate < self.params['exit_funding_rate']:
            return TradingSignal(
                signal_type=SignalType.CLOSE_LONG,
                confidence=0.95,
                entry_price=current_price,
                stop_loss=0,
                take_profit=0,
                position_size=0,
                leverage=1,
                reasoning=f"资金费率降至{funding_rate*100:.2f}%，退出套利"
            )
        
        return TradingSignal(
            signal_type=SignalType.HOLD,
            confidence=0.0,
            entry_price=current_price,
            stop_loss=0,
            take_profit=0,
            position_size=0,
            leverage=1,
            reasoning="资金费率不满足套利条件"
        )
```

---

## 5. 策略库管理

```python
# strategies/bitcoin_strategy_library.py

from typing import Dict, List
from .base_strategy import BitcoinStrategy
from .ema_trend_following import EMATrendFollowingStrategy
from .funding_rate_arbitrage import FundingRateArbitrageStrategy
# ... 导入其他策略


class BitcoinStrategyLibrary:
    """比特币策略库"""
    
    def __init__(self):
        self.strategies: Dict[str, BitcoinStrategy] = {}
        self._initialize_strategies()
    
    def _initialize_strategies(self):
        """初始化所有策略"""
        
        # 1. EMA 趋势跟踪
        self.strategies["ema_trend_following"] = EMATrendFollowingStrategy()
        
        # 2. 资金费率套利
        self.strategies["funding_rate_arbitrage"] = FundingRateArbitrageStrategy()
        
        # 3. 布林带震荡
        # self.strategies["bollinger_ranging"] = BollingerRangingStrategy()
        
        # ... 添加其他策略
    
    def get_strategy(self, name: str) -> BitcoinStrategy:
        """获取策略"""
        return self.strategies.get(name)
    
    def get_all_strategies(self) -> List[BitcoinStrategy]:
        """获取所有策略"""
        return list(self.strategies.values())
    
    def get_strategies_for_market(self, market_condition: str) -> List[BitcoinStrategy]:
        """根据市场状态获取适用策略"""
        # 根据市场状态筛选策略
        suitable_strategies = []
        
        if market_condition == "trending_up":
            suitable_strategies.append(self.strategies["ema_trend_following"])
        elif market_condition == "ranging":
            suitable_strategies.append(self.strategies["bollinger_ranging"])
        elif market_condition == "high_funding_rate":
            suitable_strategies.append(self.strategies["funding_rate_arbitrage"])
        
        return suitable_strategies
```

---

## 6. 总结

### 6.1 策略选择建议

| 市场状态 | 推荐策略 | 风险等级 |
|---------|---------|---------|
| **强趋势（ADX>25）** | EMA趋势跟踪 | 中 |
| **震荡（波动率<3%）** | 布林带震荡、网格交易 | 低-中 |
| **突破（整数关口）** | 关键位突破 | 中-高 |
| **高资金费率（>0.1%）** | 资金费率套利 | 低 |
| **巨鲸异动** | 链上信号策略 | 中 |
| **周末** | 避免交易或小仓位 | 高 |

### 6.2 风险提示

1. **杠杆风险** - 建议最大 3-5 倍杠杆
2. **流动性风险** - 避免在低流动性时段交易
3. **黑天鹅风险** - 预留 20-30% 资金应对极端行情
4. **资金费率风险** - 套利时注意价差波动
5. **链上数据延迟** - 链上数据有 10-30 分钟延迟

---

**文档结束**

这是一个完整的比特币专用策略库！所有策略都考虑了加密货币市场的特殊性。
