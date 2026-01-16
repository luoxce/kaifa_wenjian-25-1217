import type { HTMLAttributes } from "react";

import { cn } from "@/lib/utils";

interface BadgeProps extends HTMLAttributes<HTMLSpanElement> {
  variant?: "default" | "success" | "danger" | "warning" | "info";
}

export function Badge({ className, variant = "default", ...props }: BadgeProps) {
  const styles = {
    default: "border-slate-800 bg-slate-900 text-slate-200",
    success: "border-emerald-500/40 bg-emerald-500/10 text-emerald-300",
    danger: "border-rose-500/40 bg-rose-500/10 text-rose-300",
    warning: "border-amber-500/40 bg-amber-500/10 text-amber-300",
    info: "border-blue-500/40 bg-blue-500/10 text-blue-300",
  }[variant];

  return (
    <span
      className={cn(
        "inline-flex items-center rounded-full border px-2 py-0.5 text-[10px] font-medium",
        styles,
        className
      )}
      {...props}
    />
  );
}
