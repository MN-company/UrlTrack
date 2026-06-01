import { AppShell } from "@/components/shell";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";

const insights = [
  ["warning", "Traffic quality drop", "EU paid campaign has a 19% increase in datacenter traffic."],
  ["critical", "Lead cluster conflict", "Two high-value leads share Thumbmark but conflict on email domain."],
  ["info", "Returning visitor pattern", "QR booth traffic converts after the third return visit."]
] as const;

export default function AIInsightsPage() {
  return (
    <AppShell>
      <div className="mb-5">
        <h1 className="font-display text-3xl">AI Insights</h1>
        <p className="mt-1 text-sm text-muted">Workspace anomaly and lead ranking feed</p>
      </div>

      <section className="grid gap-4 xl:grid-cols-[0.85fr_1.15fr]">
        <div className="space-y-3">
          {insights.map(([tone, title, summary]) => (
            <Card key={title} className="p-4">
              <div className="mb-3 flex items-center justify-between gap-3">
                <h2 className="font-display text-lg">{title}</h2>
                <Badge tone={tone}>{tone}</Badge>
              </div>
              <p className="text-sm text-muted">{summary}</p>
              <div className="mt-4">
                <Button type="button" tone="ghost">Dismiss</Button>
              </div>
            </Card>
          ))}
        </div>
        <Card className="p-4">
          <h2 className="font-display text-xl">Ask Workspace</h2>
          <textarea
            className="mt-4 min-h-40 w-full resize-none rounded-ui border border-border bg-obsidian p-3 text-sm outline-none focus:border-live"
            defaultValue="Which links are creating high-confidence leads from Italy this week?"
          />
          <div className="mt-3 flex justify-end">
            <Button type="button" tone="primary">Run</Button>
          </div>
        </Card>
      </section>
    </AppShell>
  );
}
