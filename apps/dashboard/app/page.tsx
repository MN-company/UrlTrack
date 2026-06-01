import { ActivityFeed } from "@/components/activity-feed";
import { MetricCard } from "@/components/metric-card";
import { AppShell } from "@/components/shell";
import { TrafficQuality } from "@/components/traffic-quality";
import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";

const topLinks = [
  { slug: "/launch", clicks: 2840, identity: 76, quality: "Clean" },
  { slug: "/founder-note", clicks: 1660, identity: 63, quality: "Review" },
  { slug: "/qr-booth", clicks: 940, identity: 81, quality: "Clean" },
  { slug: "/investor-demo", clicks: 681, identity: 58, quality: "Review" },
  { slug: "/safe-offer", clicks: 432, identity: 71, quality: "Clean" }
];

export default function DashboardPage() {
  return (
    <AppShell>
      <div className="mb-5 flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="font-display text-3xl">Dashboard</h1>
          <p className="mt-1 text-sm text-muted">Workspace signal summary</p>
        </div>
        <Badge tone="live">sub-50ms redirect target</Badge>
      </div>

      <section className="grid gap-3 md:grid-cols-2 xl:grid-cols-5">
        <MetricCard label="Clicks Today" value={18420} delta={12} series={[18, 22, 19, 28, 34, 39, 43]} />
        <MetricCard label="Unique Visitors" value={6210} delta={9} series={[8, 12, 16, 22, 20, 31, 36]} tone="info" />
        <MetricCard label="Active Links" value={128} delta={4} series={[22, 22, 24, 24, 27, 29, 31]} />
        <MetricCard label="Leads Captured" value={914} delta={17} series={[9, 11, 14, 18, 21, 25, 29]} tone="info" />
        <MetricCard label="Suspicious %" value={11} delta={-6} series={[22, 19, 18, 14, 13, 12, 11]} tone="warning" />
      </section>

      <section className="mt-4 grid gap-4 xl:grid-cols-[1.35fr_0.65fr]">
        <Card className="p-4">
          <div className="mb-4 flex items-center justify-between">
            <h2 className="font-display text-lg">Top Links</h2>
            <span className="font-mono text-xs text-muted">last 24h</span>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full min-w-[620px] border-collapse text-sm">
              <thead className="text-left text-muted">
                <tr className="border-b border-border">
                  <th className="py-2 font-normal">Slug</th>
                  <th className="py-2 font-normal">Clicks</th>
                  <th className="py-2 font-normal">Identity</th>
                  <th className="py-2 font-normal">Quality</th>
                </tr>
              </thead>
              <tbody>
                {topLinks.map((link) => (
                  <tr key={link.slug} className="border-b border-border last:border-0">
                    <td className="py-3 font-mono">{link.slug}</td>
                    <td className="py-3">{link.clicks.toLocaleString()}</td>
                    <td className="py-3">
                      <div className="flex items-center gap-2">
                        <div className="h-2 w-28 rounded-full bg-raised">
                          <div className="h-2 rounded-full bg-live" style={{ width: `${link.identity}%` }} />
                        </div>
                        <span className="font-mono text-xs">{link.identity}%</span>
                      </div>
                    </td>
                    <td className="py-3">
                      <Badge tone={link.quality === "Clean" ? "live" : "warning"}>{link.quality}</Badge>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>

        <TrafficQuality />
      </section>

      <section className="mt-4 grid gap-4 xl:grid-cols-[0.8fr_1.2fr]">
        <ActivityFeed />
        <Card className="p-4">
          <div className="mb-4 flex items-center justify-between">
            <h2 className="font-display text-lg">Top Countries</h2>
            <span className="font-mono text-xs text-muted">geo edge sample</span>
          </div>
          <div className="grid gap-3 sm:grid-cols-2">
            {["US", "IT", "DE", "FR", "GB", "BR"].map((country, index) => (
              <div key={country} className="flex items-center gap-3">
                <span className="w-8 font-mono text-sm">{country}</span>
                <div className="h-2 flex-1 rounded-full bg-raised">
                  <div className="h-2 rounded-full bg-signal" style={{ width: `${92 - index * 11}%` }} />
                </div>
              </div>
            ))}
          </div>
        </Card>
      </section>
    </AppShell>
  );
}
