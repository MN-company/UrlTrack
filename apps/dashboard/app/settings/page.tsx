import { defaultWorkspaceSettings } from "@urltrack/shared";

import { AppShell } from "@/components/shell";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";

export default function SettingsPage() {
  const traffic = defaultWorkspaceSettings.scoring.traffic_quality;
  const lead = defaultWorkspaceSettings.scoring.lead_score;

  return (
    <AppShell>
      <div className="mb-5 flex flex-wrap items-center justify-between gap-4">
        <div>
          <h1 className="font-display text-3xl">Settings</h1>
          <p className="mt-1 text-sm text-muted">Workspace scoring and integrations</p>
        </div>
        <Button type="button" tone="primary">Save</Button>
      </div>

      <section className="grid gap-4 xl:grid-cols-2">
        <Card className="p-4">
          <div className="mb-4 flex items-center justify-between">
            <h2 className="font-display text-xl">Traffic Quality</h2>
            <Badge tone="warning">penalties</Badge>
          </div>
          {Object.entries(traffic).map(([key, value]) => (
            <label key={key} className="mb-4 block last:mb-0">
              <div className="mb-2 flex justify-between text-sm">
                <span className="text-muted">{key}</span>
                <span className="font-mono">{value}</span>
              </div>
              <input className="w-full accent-live" type="range" min="-100" max="100" defaultValue={value} />
            </label>
          ))}
        </Card>
        <Card className="p-4">
          <div className="mb-4 flex items-center justify-between">
            <h2 className="font-display text-xl">Lead Score</h2>
            <Badge tone="live">bonuses</Badge>
          </div>
          {Object.entries(lead).map(([key, value]) => (
            <label key={key} className="mb-4 block last:mb-0">
              <div className="mb-2 flex justify-between text-sm">
                <span className="text-muted">{key}</span>
                <span className="font-mono">{value}</span>
              </div>
              <input className="w-full accent-live" type="number" defaultValue={value} />
            </label>
          ))}
        </Card>
      </section>
    </AppShell>
  );
}
