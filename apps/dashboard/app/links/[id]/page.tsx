import { BarChart3, ExternalLink, QrCode, Settings, Users } from "lucide-react";

import { FlowBuilder } from "@/components/flow-builder";
import { AppShell } from "@/components/shell";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";

const metrics = [
  { label: "Clicks", value: "12,480", Icon: BarChart3 },
  { label: "Visitors", value: "4,912", Icon: Users },
  { label: "QR Scans", value: "1,204", Icon: QrCode },
  { label: "Identity", value: "74%", Icon: Users }
];

type PageProps = {
  params: Promise<{ id: string }>;
};

export default async function LinkDetailPage({ params }: PageProps) {
  const { id } = await params;

  return (
    <AppShell>
      <div className="mb-5 flex flex-wrap items-start justify-between gap-4">
        <div>
          <div className="mb-2 flex flex-wrap items-center gap-2">
            <h1 className="font-display text-3xl">/{id}</h1>
            <Badge tone="live">active</Badge>
          </div>
          <p className="font-mono text-sm text-muted">https://example.com/campaign/launch</p>
        </div>
        <div className="flex gap-2">
          <Button type="button">
            <ExternalLink className="size-4" aria-hidden="true" />
            Open
          </Button>
          <Button type="button" tone="primary">
            <Settings className="size-4" aria-hidden="true" />
            Save
          </Button>
        </div>
      </div>

      <div className="mb-4 grid gap-3 md:grid-cols-4">
        {metrics.map(({ label, value, Icon }) => (
          <Card key={label} className="p-4">
            <div className="flex items-center justify-between text-muted">
              <span className="text-sm">{label}</span>
              <Icon className="size-4" aria-hidden="true" />
            </div>
            <div className="mt-2 font-display text-2xl">{value}</div>
          </Card>
        ))}
      </div>

      <section className="grid gap-4 xl:grid-cols-[1.3fr_0.7fr]">
        <div>
          <div className="mb-3 flex items-center justify-between">
            <h2 className="font-display text-xl">Flow Builder</h2>
            <Badge tone="info">React Flow</Badge>
          </div>
          <FlowBuilder />
        </div>
        <Card className="p-4">
          <h2 className="font-display text-xl">Visits</h2>
          <div className="mt-4 space-y-3">
            {[
              ["vis_81f2", "Desktop", "US", "82%", "Clean"],
              ["vis_62aa", "Mobile", "IT", "58%", "Review"],
              ["vis_0ad1", "Desktop", "DE", "91%", "Clean"],
              ["vis_f9c4", "Tablet", "FR", "34%", "VPN"]
            ].map(([visit, device, country, confidence, quality]) => (
              <div key={visit} className="grid grid-cols-[1fr_auto] gap-2 border-b border-border pb-3 last:border-0">
                <div>
                  <div className="font-mono text-sm">{visit}</div>
                  <div className="mt-1 text-xs text-muted">
                    {device} · {country} · {confidence}
                  </div>
                </div>
                <Badge tone={quality === "Clean" ? "live" : quality === "VPN" ? "critical" : "warning"}>{quality}</Badge>
              </div>
            ))}
          </div>
        </Card>
      </section>
    </AppShell>
  );
}
