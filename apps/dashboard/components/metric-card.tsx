import { ArrowDownRight, ArrowUpRight } from "lucide-react";

import { formatCompactNumber } from "@/lib/format";
import { cn } from "@/lib/utils";

import { Card } from "./ui/card";

type MetricCardProps = {
  label: string;
  value: number;
  delta: number;
  series: number[];
  tone?: "live" | "warning" | "info";
};

export function MetricCard({ label, value, delta, series, tone = "live" }: MetricCardProps) {
  const max = Math.max(...series, 1);
  const isPositive = delta >= 0;

  return (
    <Card className="p-4">
      <div className="flex items-start justify-between gap-3">
        <div>
          <div className="text-sm text-muted">{label}</div>
          <div className="mt-2 font-display text-3xl">{formatCompactNumber(value)}</div>
        </div>
        <div
          className={cn(
            "inline-flex items-center gap-1 rounded-ui border px-2 py-1 font-mono text-xs",
            isPositive ? "border-live/40 bg-live/10 text-live" : "border-accent/40 bg-accent/10 text-accent"
          )}
        >
          {isPositive ? <ArrowUpRight className="size-3" /> : <ArrowDownRight className="size-3" />}
          {Math.abs(delta)}%
        </div>
      </div>
      <div className="mt-4 flex h-10 items-end gap-1">
        {series.map((point, index) => (
          <div
            key={`${label}-${index}`}
            className={cn("w-full rounded-sm", tone === "warning" ? "bg-accent" : tone === "info" ? "bg-signal" : "bg-live")}
            style={{ height: `${Math.max(12, (point / max) * 100)}%` }}
          />
        ))}
      </div>
    </Card>
  );
}
