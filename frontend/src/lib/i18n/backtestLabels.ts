export const BACKTEST_GROUPS = {
  presets: { zh: "参数预设", en: "Presets" },
  basics: { zh: "基础参数", en: "Basics" },
  strategy: { zh: "策略参数", en: "Strategy" },
  costs: { zh: "成本与撮合", en: "Costs & Execution" },
  risk: { zh: "风控控制", en: "Risk Controls" },
  output: { zh: "输出设置", en: "Output" },
};

export const BACKTEST_FIELDS = {
  symbol: {
    zh: "交易对",
    en: "Symbol",
    helpZh: "交易对/合约标识（如 BTC/USDT:USDT）。",
    helpEn: "Trading pair or contract symbol (e.g., BTC/USDT:USDT).",
  },
  timeframe: {
    zh: "周期",
    en: "Timeframe",
    helpZh: "K 线周期，决定信号频率与交易次数。",
    helpEn: "Candle interval; drives signal frequency and trade count.",
  },
  startTime: {
    zh: "开始时间",
    en: "Start Time",
    helpZh: "回测区间起点（ISO 时间）。",
    helpEn: "Start timestamp for the backtest window (ISO).",
  },
  endTime: {
    zh: "结束时间",
    en: "End Time",
    helpZh: "回测区间终点（ISO 时间）。",
    helpEn: "End timestamp for the backtest window (ISO).",
  },
  strategy: {
    zh: "策略",
    en: "Strategy",
    helpZh: "策略选择（来自策略库）。",
    helpEn: "Strategy selector (from library).",
  },
  limit: {
    zh: "K 线数量",
    en: "Bars Limit",
    helpZh: "使用的 K 线条数，越大越慢。",
    helpEn: "Number of candles; larger = slower.",
  },
  signalWindow: {
    zh: "信号窗口",
    en: "Signal Window",
    helpZh: "单次信号回看窗口（需 <= K 线数量）。",
    helpEn: "Lookback window per signal (<= bars limit).",
  },
  initialCapital: {
    zh: "初始资金",
    en: "Initial Capital",
    helpZh: "回测初始权益。",
    helpEn: "Starting equity for the backtest.",
  },
  leverage: {
    zh: "杠杆倍数",
    en: "Leverage",
    helpZh: "影响保证金占用与强平风险。",
    helpEn: "Affects margin usage and liquidation risk.",
  },
  feeRate: {
    zh: "手续费率",
    en: "Fee Rate",
    helpZh: "单边手续费率（如 0.0005 = 0.05%）。",
    helpEn: "One-way fee rate (e.g., 0.0005 = 0.05%).",
  },
  slippageBps: {
    zh: "基础滑点",
    en: "Slippage (bps)",
    helpZh: "成交价偏移，越大越保守。",
    helpEn: "Execution price offset; higher is more conservative.",
  },
  slippageModel: {
    zh: "滑点模型",
    en: "Slippage Model",
    helpZh: "fixed 固定 / volatility 波动率 / sizeImpact 量化冲击。",
    helpEn: "fixed / volatility / sizeImpact.",
  },
  orderSizeMode: {
    zh: "下单方式",
    en: "Order Size Mode",
    helpZh: "固定数量 / 固定金额 / 按权益比例。",
    helpEn: "fixedQty / fixedNotional / percentEquity.",
  },
  orderSizeValue: {
    zh: "下单数值",
    en: "Order Size Value",
    helpZh: "与下单方式对应的数值。",
    helpEn: "Value for the selected size mode.",
  },
  allowShort: {
    zh: "允许做空",
    en: "Allow Short",
    helpZh: "是否允许空头交易。",
    helpEn: "Whether shorting is allowed.",
  },
  fundingEnabled: {
    zh: "计入资金费",
    en: "Funding Enabled",
    helpZh: "永续合约建议开启。",
    helpEn: "Recommended for perpetuals.",
  },
  riskMaxDrawdown: {
    zh: "最大回撤阈值",
    en: "Max Drawdown",
    helpZh: "触发停止/降仓的回撤阈值。",
    helpEn: "Drawdown threshold for stop/derisk.",
  },
  riskMaxPosition: {
    zh: "最大仓位占用",
    en: "Max Position",
    helpZh: "最大仓位占用比例。",
    helpEn: "Maximum position usage ratio.",
  },
  name: {
    zh: "回测名称",
    en: "Run Name",
    helpZh: "可选名称，便于对比与追踪。",
    helpEn: "Optional label for tracking and comparison.",
  },
};

export const BACKTEST_TABS = {
  price: { zh: "价格", en: "Price" },
  equity: { zh: "权益", en: "Equity" },
  drawdown: { zh: "回撤", en: "Drawdown" },
  summary: { zh: "概览", en: "Summary" },
  details: { zh: "详情", en: "Details" },
  trades: { zh: "交易明细", en: "Trades" },
  logs: { zh: "运行日志", en: "Logs" },
  export: { zh: "导出", en: "Export" },
};

export const SUMMARY_METRICS = [
  { key: "totalReturn", zh: "总收益率", en: "Total Return", format: "pct" },
  { key: "cagr", zh: "年化收益率", en: "CAGR", format: "pct" },
  { key: "mdd", zh: "最大回撤", en: "Max Drawdown", format: "pct", star: true },
  {
    key: "maxDrawdownDuration",
    zh: "回撤持续时间",
    en: "DD Duration",
    format: "duration",
  },
  { key: "sharpe", zh: "夏普比率", en: "Sharpe Ratio", format: "num" },
  { key: "sortino", zh: "索提诺比率", en: "Sortino Ratio", format: "num" },
  { key: "calmar", zh: "卡玛比率", en: "Calmar Ratio", format: "num", star: true },
  { key: "winRate", zh: "胜率", en: "Win Rate", format: "pct" },
  { key: "payoffRatio", zh: "盈亏比", en: "Payoff Ratio", format: "num" },
  { key: "profitFactor", zh: "利润因子", en: "Profit Factor", format: "num", star: true },
  { key: "tradesCount", zh: "交易次数", en: "Trades Count", format: "int" },
  { key: "fundingPnl", zh: "资金费收益", en: "Funding PnL", format: "funding", star: true },
];

export const DETAIL_GROUPS = [
  {
    key: "returns",
    zh: "收益结构",
    en: "Return Structure",
    items: [
      { key: "monthlyReturnMean", zh: "月度平均收益", en: "Monthly Return Mean", suffix: "%" },
      { key: "monthlyReturnStd", zh: "月度收益波动", en: "Monthly Return Std", suffix: "%" },
      { key: "bestDay", zh: "最佳单日", en: "Best Day", suffix: "%" },
      { key: "worstDay", zh: "最差单日", en: "Worst Day", suffix: "%" },
      { key: "skew", zh: "偏度", en: "Skew" },
      { key: "kurtosis", zh: "峰度", en: "Kurtosis" },
    ],
  },
  {
    key: "risk",
    zh: "风险细节",
    en: "Risk Diagnostics",
    items: [
      { key: "volatility", zh: "年化波动率", en: "Volatility", suffix: "%" },
      { key: "downsideVolatility", zh: "下行波动率", en: "Downside Volatility", suffix: "%" },
      { key: "var95", zh: "VaR 95%", en: "VaR 95%", suffix: "%" },
      { key: "cvar95", zh: "CVaR 95%", en: "CVaR 95%", suffix: "%" },
      { key: "maxDailyDrawdown", zh: "最大日回撤", en: "Max Daily Drawdown", suffix: "%" },
    ],
  },
  {
    key: "trades",
    zh: "交易细节",
    en: "Trade Quality",
    items: [
      { key: "avgTradePnl", zh: "平均单笔收益", en: "Avg Trade PnL" },
      { key: "expectancy", zh: "单笔期望", en: "Expectancy" },
      { key: "maxLosingStreak", zh: "最大连亏", en: "Max Losing Streak" },
      { key: "avgHoldingTime", zh: "平均持仓时间", en: "Avg Holding Time", suffix: "s" },
      { key: "turnoverPerDay", zh: "日均交易数", en: "Trades per Day" },
    ],
  },
  {
    key: "costs",
    zh: "成本与摩擦",
    en: "Costs & Friction",
    items: [
      { key: "feePaid", zh: "手续费总额", en: "Fee Paid" },
      { key: "slippageCost", zh: "滑点损耗", en: "Slippage Cost" },
      { key: "costDrag", zh: "成本拖累", en: "Cost Drag", suffix: "%" },
      { key: "avgCostPerTrade", zh: "单笔成本", en: "Avg Cost per Trade" },
    ],
  },
  {
    key: "exposure",
    zh: "仓位与杠杆",
    en: "Exposure & Leverage",
    items: [
      { key: "maxExposure", zh: "最大风险敞口", en: "Max Exposure" },
      { key: "avgLeverage", zh: "平均杠杆", en: "Avg Leverage" },
      { key: "maxMarginUsage", zh: "最大保证金占用", en: "Max Margin Usage" },
      { key: "liquidationCount", zh: "强平次数", en: "Liquidations" },
    ],
  },
  {
    key: "benchmark",
    zh: "基准对比",
    en: "Benchmark",
    items: [
      { key: "alphaVsBtc", zh: "超额收益", en: "Alpha vs BTC", suffix: "%" },
      { key: "strategyMddVsBenchmark", zh: "回撤对比", en: "MDD vs Benchmark" },
      { key: "informationRatio", zh: "信息比率", en: "Information Ratio" },
    ],
  },
];

export const TRADE_COLUMNS = [
  { key: "entryTime", zh: "开仓时间", en: "Entry Time" },
  { key: "exitTime", zh: "平仓时间", en: "Exit Time" },
  { key: "side", zh: "方向", en: "Side" },
  { key: "entryPrice", zh: "开仓价", en: "Entry Px", align: "right" },
  { key: "exitPrice", zh: "平仓价", en: "Exit Px", align: "right" },
  { key: "qty", zh: "数量", en: "Qty", align: "right" },
  { key: "pnl", zh: "盈亏", en: "PnL", align: "right" },
  { key: "pnlPct", zh: "盈亏率", en: "PnL%", align: "right" },
  { key: "durationSec", zh: "持仓时长", en: "Duration", align: "right" },
  { key: "reason", zh: "原因", en: "Reason" },
];

export const EXPORT_ITEMS = [
  {
    key: "equity",
    zh: "权益曲线",
    en: "Equity Curve",
    descZh: "时间-权益-回撤序列",
    descEn: "Time/equity/drawdown series",
    filename: "equity_curve.csv",
  },
  {
    key: "trades",
    zh: "交易明细",
    en: "Trades Log",
    descZh: "逐笔交易明细",
    descEn: "Per-trade details",
    filename: "trades.csv",
  },
  {
    key: "positions",
    zh: "仓位轨迹",
    en: "Positions",
    descZh: "仓位、名义、杠杆轨迹",
    descEn: "Position/notional/leverage",
    filename: "positions.csv",
  },
];

