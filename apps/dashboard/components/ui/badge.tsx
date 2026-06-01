import { cn } from "@/lib/utils";

type BadgeProps = {
  children: React.ReactNode;
  tone?: "live" | "warning" | "info" | "neutral" | "critical";
};

const tones = {
  critical: "border-red-500/40 bg-red-500/10 text-red-200",
  info: "border-signal/40 bg-signal/10 text-signal",
  live: "border-live/40 bg-live/10 text-live",
  neutral: "border-border bg-raised text-muted",
  warning: "border-accent/40 bg-accent/10 text-accent"
};

export function Badge({ children, tone = "neutral" }: BadgeProps) {
  return <span className={cn("inline-flex items-center rounded-ui border px-2 py-1 text-xs", tones[tone])}>{children}</span>;
}
