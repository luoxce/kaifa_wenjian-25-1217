import type { ReactNode } from "react";

import BilingualLabel from "@/components/ui/BilingualLabel";
import { BACKTEST_FIELDS, BACKTEST_GROUPS } from "@/lib/i18n/backtestLabels";
import { cn } from "@/lib/utils";
import type { BacktestRequest } from "@/types/schema";

type StrategyOption = {
  key: string;
  name: string;
};

export interface BacktestFormState extends BacktestRequest {
  strategy: string;
  limit: number;
  signalWindow: number;
  name: string;
}

interface Preset {
  label: string;
  values: Partial<BacktestFormState>;
}

interface ConfigPanelProps {
  value: BacktestFormState;
  onChange: (next: BacktestFormState) => void;
  onRun: () => void;
  onReset: () => void;
  strategies: StrategyOption[];
  presets: Preset[];
  timeframeOptions: string[];
  earliestLabel: string;
  latestLabel: string;
  limitNote?: string | null;
  running?: boolean;
  apiEnabled: boolean;
  writeEnabled?: boolean;
  errorMessage?: string | null;
}

export default function ConfigPanel({
  value,
  onChange,
  onRun,
  onReset,
  strategies,
  presets,
  timeframeOptions,
  earliestLabel,
  latestLabel,
  limitNote,
  running,
  apiEnabled,
  writeEnabled = true,
  errorMessage,
}: ConfigPanelProps) {
  const update = (key: keyof BacktestFormState, nextValue: string | number | boolean) => {
    onChange({ ...value, [key]: nextValue });
  };

  const updateRisk = (key: keyof BacktestFormState["risk"], nextValue: number) => {
    onChange({
      ...value,
      risk: {
        ...value.risk,
        [key]: nextValue,
      },
    });
  };

  return (
    <aside className="flex h-full flex-col rounded-xl border border-[#1c1c1c] bg-[#0a0a0a]">
      <div className="border-b border-[#1c1c1c] px-4 py-3">
        <BilingualLabel zh="回测参数" en="Backtest Config" />
        <p className="mt-1 text-[11px] text-slate-500">
          参数分组可折叠，修改后点击运行即可生成回测结果 / Adjust inputs and run to generate a new backtest.
        </p>
      </div>

      <div className="flex-1 space-y-4 overflow-auto px-4 py-4 text-xs text-slate-200">
        {!apiEnabled && (
          <div className="rounded border border-rose-500/30 bg-rose-500/10 p-2 text-[11px] text-rose-300">
            API 未配置 / API not configured. 请设置 VITE_API_BASE_URL。
          </div>
        )}
        {apiEnabled && !writeEnabled && (
          <div className="rounded border border-amber-500/30 bg-amber-500/10 p-2 text-[11px] text-amber-200">
            写接口关闭 / Writes disabled. 请设置 API_WRITE_ENABLED=true。
          </div>
        )}
        {errorMessage && (
          <div className="rounded border border-rose-500/30 bg-rose-500/10 p-2 text-[11px] text-rose-300">
            {errorMessage}
          </div>
        )}

        <AccordionGroup title={BACKTEST_GROUPS.presets}>
          <div className="flex flex-wrap gap-2">
            {presets.map((preset) => (
              <button
                key={preset.label}
                className={cn(
                  "rounded-md border border-[#27272a] px-3 py-1 text-[11px] font-mono transition",
                  preset.values.timeframe === value.timeframe
                    ? "border-emerald-500/40 bg-emerald-500/10 text-emerald-200"
                    : "hover:bg-slate-800/50"
                )}
                onClick={() => onChange({ ...value, ...preset.values })}
              >
                {preset.label}
              </button>
            ))}
          </div>
        </AccordionGroup>

        <AccordionGroup title={BACKTEST_GROUPS.basics} open>
          <Field
            label={BACKTEST_FIELDS.symbol}
            value={value.symbol}
            onChange={(val) => update("symbol", val)}
          />
          <Field
            label={BACKTEST_FIELDS.timeframe}
            value={value.timeframe}
            onChange={(val) => update("timeframe", val)}
            type="select"
            options={timeframeOptions.map((tf) => ({ key: tf, name: tf }))}
          />
          <HintRow>
            最早可选日期 / Earliest: {earliestLabel} · 最新 / Latest: {latestLabel}
          </HintRow>
          <Field
            label={BACKTEST_FIELDS.startTime}
            value={toLocalInput(value.startTime)}
            onChange={(val) => update("startTime", toIso(val))}
            type="datetime-local"
          />
          <Field
            label={BACKTEST_FIELDS.endTime}
            value={toLocalInput(value.endTime)}
            onChange={(val) => update("endTime", toIso(val))}
            type="datetime-local"
          />
          <Field
            label={BACKTEST_FIELDS.limit}
            value={value.limit}
            onChange={(val) => update("limit", Number(val))}
            type="number"
            disabled
          />
          {limitNote && <HintRow>{limitNote}</HintRow>}
        </AccordionGroup>

        <AccordionGroup title={BACKTEST_GROUPS.strategy} open>
          <Field
            label={BACKTEST_FIELDS.strategy}
            value={value.strategy}
            onChange={(val) => update("strategy", val)}
            type="select"
            options={strategies.length ? strategies : [{ key: "ema_trend", name: "ema_trend" }]}
          />
          <Field
            label={BACKTEST_FIELDS.signalWindow}
            value={value.signalWindow}
            onChange={(val) => update("signalWindow", Number(val))}
            type="number"
          />
          <Field
            label={BACKTEST_FIELDS.initialCapital}
            value={value.initialCapital}
            onChange={(val) => update("initialCapital", Number(val))}
            type="number"
          />
        </AccordionGroup>

        <AccordionGroup title={BACKTEST_GROUPS.costs}>
          <Field
            label={BACKTEST_FIELDS.feeRate}
            value={value.feeRate}
            onChange={(val) => update("feeRate", Number(val))}
            type="number"
          />
          <Field
            label={BACKTEST_FIELDS.slippageBps}
            value={value.slippageBps}
            onChange={(val) => update("slippageBps", Number(val))}
            type="number"
          />
          <Field
            label={BACKTEST_FIELDS.slippageModel}
            value={value.slippageModel}
            onChange={(val) => update("slippageModel", val)}
            type="select"
            options={[
              { key: "fixed", name: "fixed" },
              { key: "volatility", name: "volatility" },
              { key: "sizeImpact", name: "sizeImpact" },
            ]}
          />
          <Field
            label={BACKTEST_FIELDS.orderSizeMode}
            value={value.orderSizeMode}
            onChange={(val) => update("orderSizeMode", val)}
            type="select"
            options={[
              { key: "fixedQty", name: "fixedQty" },
              { key: "fixedNotional", name: "fixedNotional" },
              { key: "percentEquity", name: "percentEquity" },
            ]}
          />
          <Field
            label={BACKTEST_FIELDS.orderSizeValue}
            value={value.orderSizeValue}
            onChange={(val) => update("orderSizeValue", Number(val))}
            type="number"
          />
          <Toggle
            label={BACKTEST_FIELDS.fundingEnabled}
            value={value.fundingEnabled}
            onChange={(val) => update("fundingEnabled", val)}
          />
        </AccordionGroup>

        <AccordionGroup title={BACKTEST_GROUPS.risk}>
          <Field
            label={BACKTEST_FIELDS.leverage}
            value={value.leverage ?? 1}
            onChange={(val) => update("leverage", Number(val))}
            type="number"
          />
          <Toggle
            label={BACKTEST_FIELDS.allowShort}
            value={value.allowShort}
            onChange={(val) => update("allowShort", val)}
          />
          <Field
            label={BACKTEST_FIELDS.riskMaxDrawdown}
            value={value.risk.maxDrawdown ?? 0.0}
            onChange={(val) => updateRisk("maxDrawdown", Number(val))}
            type="number"
          />
          <Field
            label={BACKTEST_FIELDS.riskMaxPosition}
            value={value.risk.maxPosition ?? 1.0}
            onChange={(val) => updateRisk("maxPosition", Number(val))}
            type="number"
          />
        </AccordionGroup>

        <AccordionGroup title={BACKTEST_GROUPS.output}>
          <Field
            label={BACKTEST_FIELDS.name}
            value={value.name}
            onChange={(val) => update("name", val)}
          />
        </AccordionGroup>
      </div>

      <div className="border-t border-[#1c1c1c] p-4">
        <div className="flex gap-2">
          <button
            className="flex-1 rounded-md border border-[#27272a] px-3 py-2 text-[11px] text-slate-300 hover:bg-slate-800/50"
            onClick={onReset}
            disabled={running}
          >
            重置 / Reset
          </button>
          <button
            className="flex-1 rounded-md border border-emerald-500/40 bg-emerald-500/10 px-3 py-2 text-[11px] font-semibold text-emerald-300 hover:bg-emerald-500/20"
            onClick={onRun}
            disabled={!apiEnabled || running}
          >
            {running ? "运行中 / Running" : "运行回测 / Run"}
          </button>
        </div>
      </div>
    </aside>
  );
}

function AccordionGroup({
  title,
  children,
  open,
}: {
  title: { zh: string; en: string };
  children: ReactNode;
  open?: boolean;
}) {
  return (
    <details open={open} className="rounded-lg border border-[#1c1c1c] bg-[#050505]/60">
      <summary className="flex cursor-pointer items-center justify-between px-3 py-2 text-[11px] text-slate-300">
        <BilingualLabel zh={title.zh} en={title.en} compact />
        <span className="text-[10px] text-slate-500">▼</span>
      </summary>
      <div className="grid gap-3 border-t border-[#1c1c1c] px-3 py-3">{children}</div>
    </details>
  );
}

function HintRow({ children }: { children: ReactNode }) {
  return <div className="text-[10px] text-slate-500">{children}</div>;
}

interface FieldProps {
  label: { zh: string; en: string; helpZh?: string; helpEn?: string };
  value: string | number;
  onChange: (value: string) => void;
  type?: "text" | "number" | "select" | "datetime-local";
  options?: { key: string; name: string }[];
  disabled?: boolean;
}

function Field({
  label,
  tooltip,
  value,
  onChange,
  type = "text",
  options,
  disabled,
}: FieldProps & { tooltip?: string }) {
  const tip = tooltip ?? buildTooltip(label);

  if (type === "select") {
    return (
      <label className="flex flex-col gap-2 text-[11px] text-slate-300">
        <LabelRow label={label} tooltip={tip} />
        <select
          className="rounded-md border border-[#27272a] bg-[#050505] px-2 py-2 text-[11px] text-slate-100"
          value={value}
          onChange={(event) => onChange(event.target.value)}
          disabled={disabled}
        >
          {options?.map((option) => (
            <option key={option.key} value={option.key}>
              {option.name}
            </option>
          ))}
        </select>
      </label>
    );
  }

  return (
    <label className="flex flex-col gap-2 text-[11px] text-slate-300">
      <LabelRow label={label} tooltip={tip} />
      <input
        className="rounded-md border border-[#27272a] bg-[#050505] px-2 py-2 text-[11px] text-slate-100"
        value={value}
        onChange={(event) => onChange(event.target.value)}
        type={type}
        disabled={disabled}
      />
    </label>
  );
}

function Toggle({
  label,
  value,
  onChange,
}: {
  label: { zh: string; en: string; helpZh?: string; helpEn?: string };
  value: boolean;
  onChange: (next: boolean) => void;
}) {
  return (
    <div className="flex items-center justify-between gap-3 rounded-md border border-[#27272a] bg-[#050505] px-3 py-2">
      <LabelRow label={label} tooltip={buildTooltip(label)} />
      <button
        className={cn(
          "h-5 w-11 rounded-full border border-[#27272a] transition",
          value ? "bg-emerald-500/30" : "bg-slate-800/50"
        )}
        onClick={() => onChange(!value)}
      >
        <span
          className={cn(
            "block h-4 w-4 translate-x-1 rounded-full bg-slate-200 transition",
            value && "translate-x-6"
          )}
        />
      </button>
    </div>
  );
}

function LabelRow({ label, tooltip }: { label: { zh: string; en: string }; tooltip: string }) {
  return (
    <div className="flex items-center justify-between">
      <BilingualLabel zh={label.zh} en={label.en} compact />
      <span className="text-[10px] text-slate-500" title={tooltip}>
        ?
      </span>
    </div>
  );
}

function buildTooltip(label: { helpZh?: string; helpEn?: string }) {
  const zh = label.helpZh ?? "";
  const en = label.helpEn ?? "";
  if (!zh && !en) return "";
  return `${zh}\n${en}`.trim();
}

function toLocalInput(iso: string) {
  const date = new Date(iso);
  if (!Number.isFinite(date.getTime())) return "";
  const offset = date.getTimezoneOffset() * 60 * 1000;
  return new Date(date.getTime() - offset).toISOString().slice(0, 16);
}

function toIso(value: string) {
  if (!value) return new Date().toISOString();
  const date = new Date(value);
  if (!Number.isFinite(date.getTime())) return new Date().toISOString();
  return date.toISOString();
}
