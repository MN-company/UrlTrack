import { AppShell } from "@/components/shell";
import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";

const bars = [48, 58, 44, 72, 81, 67, 92, 88, 76, 84, 96, 91];

export default function AnalyticsPage() {
  return (
    <AppShell>
      <div className="mb-5 flex flex-wrap items-center justify-between gap-4">
        <div>
          <h1 className="font-display text-3xl">Analytics</h1>
          <p className="mt-1 text-sm text-muted">Campaign and link performance</p>
        </div>
        <div className="flex gap-2">
          <Badge tone="neutral">Last 30 days</Badge>
          <Badge tone="info">CSV ready</Badge>
        </div>
      </div>

      <section className="grid gap-4 xl:grid-cols-[1.35fr_0.65fr]">
        <Card className="p-4">
          <h2 className="font-display text-xl">Clicks Over Time</h2>
          <div className="mt-6 flex h-72 items-end gap-2">
            {bars.map((bar, index) => (
              <div key={index} className="flex flex-1 flex-col items-center gap-2">
                <div className="w-full rounded-sm bg-live" style={{ height: `${bar}%` }} />
                <span className="font-mono text-[10px] text-muted">{index + 1}</span>
              </div>
            ))}
          </div>
        </Card>
        <Card className="p-4">
          <h2 className="font-display text-xl">Device Breakdown</h2>
          <div className="mt-6 space-y-4">
            {[
              ["Desktop", 52, "bg-live"],
              ["Mobile", 39, "bg-signal"],
              ["Tablet", 9, "bg-accent"]
            ].map(([label, value, color]) => (
              <div key={label as string}>
                <div className="mb-2 flex justify-between text-sm">
                  <span className="text-muted">{label as string}</span>
                  <span className="font-mono">{value as number}%</span>
                </div>
                <div className="h-2 rounded-full bg-raised">
                  <div className={`${color as string} h-2 rounded-full`} style={{ width: `${value as number}%` }} />
                </div>
              </div>
            ))}
          </div>
        </Card>
      </section>
    </AppShell>
  );
}
