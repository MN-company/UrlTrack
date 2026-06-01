import { Badge } from "./ui/badge";
import { Card } from "./ui/card";

const events = [
  { label: "visitor.identified", meta: "tm_91ad... matched ws lead", tone: "live" as const },
  { label: "suspicious.detected", meta: "VPN cluster on /demo-brief", tone: "warning" as const },
  { label: "lead.score_changed", meta: "lead_4c2 moved to 82", tone: "info" as const },
  { label: "webhook.delivered", meta: "n8n outbound 204", tone: "neutral" as const }
];

export function ActivityFeed() {
  return (
    <Card className="p-4">
      <div className="mb-4 flex items-center justify-between">
        <h2 className="font-display text-lg">Realtime Feed</h2>
        <Badge tone="live">streaming</Badge>
      </div>
      <div className="space-y-3">
        {events.map((event) => (
          <div key={event.label} className="flex items-start justify-between gap-4 border-b border-border pb-3 last:border-0 last:pb-0">
            <div>
              <div className="font-mono text-sm">{event.label}</div>
              <div className="mt-1 text-sm text-muted">{event.meta}</div>
            </div>
            <Badge tone={event.tone}>{event.tone}</Badge>
          </div>
        ))}
      </div>
    </Card>
  );
}
