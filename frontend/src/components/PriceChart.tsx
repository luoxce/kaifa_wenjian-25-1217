import { useEffect, useRef } from "react";
import {
  createChart,
  type IChartApi,
  type CandlestickData,
  type HistogramData,
  type ISeriesApi,
} from "lightweight-charts";

import type { Candle, Order } from "@/types/schema";

interface PriceChartProps {
  candles: Candle[];
  orders: Order[];
}

const chartOptions = {
  layout: {
    background: { color: "#0a0a0a" },
    textColor: "#cbd5f5",
    fontFamily: "Inter, sans-serif",
  },
  grid: {
    vertLines: { color: "#141414" },
    horzLines: { color: "#141414" },
  },
  timeScale: {
    borderColor: "#27272a",
  },
  rightPriceScale: {
    borderColor: "#27272a",
  },
  crosshair: {
    vertLine: { color: "#1f2937" },
    horzLine: { color: "#1f2937" },
  },
};

export default function PriceChart({ candles, orders }: PriceChartProps) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const seriesRef = useRef<ISeriesApi<"Candlestick"> | null>(null);
  const histogramRef = useRef<ISeriesApi<"Histogram"> | null>(null);
  const rangeRef = useRef<{ min: number; max: number } | null>(null);
  const rangeSeedRef = useRef<number | null>(null);

  useEffect(() => {
    if (!containerRef.current) return;
    const chart = createChart(containerRef.current, chartOptions);
    chartRef.current = chart;
    const series = chart.addCandlestickSeries({
      upColor: "#00ff9d",
      downColor: "#ff0055",
      borderVisible: false,
      wickUpColor: "#00ff9d",
      wickDownColor: "#ff0055",
    });
    seriesRef.current = series;

    const histogram = chart.addHistogramSeries({
      color: "#3b82f6",
      priceScaleId: "signal",
      priceFormat: { type: "volume" },
      base: 0,
      scaleMargins: { top: 0.8, bottom: 0 },
    });
    histogramRef.current = histogram;

    const handleResize = () => {
      if (!containerRef.current || !chartRef.current) return;
      chartRef.current.applyOptions({
        width: containerRef.current.clientWidth,
        height: containerRef.current.clientHeight,
      });
    };
    handleResize();
    window.addEventListener("resize", handleResize);

    return () => {
      window.removeEventListener("resize", handleResize);
      chart.remove();
    };
  }, []);

  useEffect(() => {
    if (!seriesRef.current) return;
    const data = candles.map((candle) => ({
      time: candle.time,
      open: candle.open,
      high: candle.high,
      low: candle.low,
      close: candle.close,
    })) as CandlestickData[];
    seriesRef.current.setData(data);

    if (histogramRef.current) {
      const histData = candles.map((candle) => {
        const diff = candle.close - candle.open;
        const value = Math.abs(diff);
        return {
          time: candle.time,
          value,
          color: diff >= 0 ? "#00ff9d" : "#ff0055",
        } as HistogramData;
      });
      histogramRef.current.setData(histData);
    }

    const markers = orders.map((order) => {
      const side = order.side?.toUpperCase?.() ?? order.side;
      const isBuy = side === "BUY";
      return {
        time: normalizeTime(order.timestamp, candles),
        position: isBuy ? "belowBar" : "aboveBar",
        color: isBuy ? "#00ff9d" : "#ff0055",
        shape: isBuy ? "arrowUp" : "arrowDown",
        text: `${side} ${order.price?.toFixed?.(2) ?? ""}`,
      };
    });
    seriesRef.current.setMarkers(markers);

    if (!candles.length) return;
    const seed = candles[0]?.time ?? null;
    if (rangeSeedRef.current !== seed) {
      rangeSeedRef.current = seed;
      rangeRef.current = null;
    }
    const range = computeRange(candles);
    if (!range) return;
    const buffered = applyBuffer(range, 0.04);
    if (!rangeRef.current) {
      rangeRef.current = buffered;
    } else {
      const current = rangeRef.current;
      if (buffered.min < current.min || buffered.max > current.max) {
        rangeRef.current = {
          min: Math.min(current.min, buffered.min),
          max: Math.max(current.max, buffered.max),
        };
      }
    }

    const locked = rangeRef.current;
    if (locked) {
      seriesRef.current.applyOptions({
        autoscaleInfoProvider: () => ({
          priceRange: {
            minValue: locked.min,
            maxValue: locked.max,
          },
        }),
      });
    }
  }, [candles, orders]);

  return <div ref={containerRef} className="h-full w-full" />;
}

const candleTimeFallback = (candles: Candle[]) => {
  if (!candles.length) return Math.floor(Date.now() / 1000);
  return candles[candles.length - 1].time;
};

const normalizeTime = (timestamp: number, candles: Candle[]) => {
  if (!timestamp) return candleTimeFallback(candles);
  return timestamp > 10_000_000_000 ? Math.floor(timestamp / 1000) : timestamp;
};

const computeRange = (candles: Candle[]) => {
  let min = Number.POSITIVE_INFINITY;
  let max = Number.NEGATIVE_INFINITY;
  for (const candle of candles) {
    min = Math.min(min, candle.low);
    max = Math.max(max, candle.high);
  }
  if (!Number.isFinite(min) || !Number.isFinite(max) || min === max) {
    return null;
  }
  return { min, max };
};

const applyBuffer = (range: { min: number; max: number }, ratio: number) => {
  const span = range.max - range.min;
  const padding = span * ratio;
  return {
    min: range.min - padding,
    max: range.max + padding,
  };
};
