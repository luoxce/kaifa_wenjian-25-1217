import { cn } from "@/lib/utils";

interface BilingualLabelProps {
  zh: string;
  en: string;
  className?: string;
  align?: "left" | "center" | "right";
  compact?: boolean;
}

export default function BilingualLabel({
  zh,
  en,
  className,
  align = "left",
  compact,
}: BilingualLabelProps) {
  return (
    <div
      className={cn(
        "flex flex-col gap-0.5 text-slate-100",
        align === "center" && "items-center text-center",
        align === "right" && "items-end text-right",
        compact && "leading-tight",
        className
      )}
    >
      <span className="text-[12px] text-current">{zh}</span>
      <span className="text-[10px] uppercase tracking-wide text-slate-500">{en}</span>
    </div>
  );
}
