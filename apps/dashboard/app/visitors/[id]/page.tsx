import { GitBranch, Mail, Monitor, ShieldCheck } from "lucide-react";

import { AppShell } from "@/components/shell";
import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";

const signals = [
  { Icon: Mail, type: "email_hash", value: "b3f1...a81", weight: 40 },
  { Icon: Monitor, type: "thumbmark_hash", value: "91ad...ef2", weight: 15 },
  { Icon: GitBranch, type: "canvas_webgl", value: "c4a0...019", weight: 30 },
  { Icon: ShieldCheck, type: "webrtc_ip", value: "10.0...hash", weight: 10 }
];

type PageProps = {
  params: Promise<{ id: string }>;
};

export default async function VisitorDetailPage({ params }: PageProps) {
  const { id } = await params;

  return (
    <AppShell>
      <div className="mb-5 flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="font-display text-3xl">visitor_{id}</h1>
          <p className="mt-1 font-mono text-sm text-muted">first_seen 2026-05-28 · last_seen 2026-06-01</p>
        </div>
        <Badge tone="live">confidence 81%</Badge>
      </div>

      <section className="grid gap-4 xl:grid-cols-[0.85fr_1.15fr]">
        <Card className="p-4">
          <h2 className="font-display text-xl">Identity Signals</h2>
          <div className="mt-4 space-y-3">
            {signals.map(({ Icon, type, value, weight }) => (
              <div key={type} className="grid grid-cols-[auto_1fr_auto] items-center gap-3 border-b border-border pb-3 last:border-0">
                <Icon className="size-4 text-live" aria-hidden="true" />
                <div>
                  <div className="font-mono text-sm">{type}</div>
                  <div className="mt-1 font-mono text-xs text-muted">{value}</div>
                </div>
                <Badge tone="info">+{weight}</Badge>
              </div>
            ))}
          </div>
        </Card>

        <Card className="p-4">
          <h2 className="font-display text-xl">Visit Timeline</h2>
          <div className="mt-4 space-y-4">
            {["/launch", "/pricing", "/qr-booth", "/investor-demo"].map((slug, index) => (
              <div key={slug} className="grid grid-cols-[88px_1fr_auto] items-center gap-3">
                <span className="font-mono text-xs text-muted">10:{42 - index * 7}</span>
                <div className="h-px bg-border" />
                <Badge tone={index === 1 ? "warning" : "live"}>{slug}</Badge>
              </div>
            ))}
          </div>
        </Card>
      </section>

      <section className="mt-4 grid gap-4 xl:grid-cols-2">
        <Card className="p-4">
          <h2 className="font-display text-xl">Identity Graph</h2>
          <div className="mt-4 grid h-72 place-items-center rounded-ui border border-border bg-obsidian">
            <div className="relative size-56">
              <div className="absolute left-20 top-20 grid size-16 place-items-center rounded-full border border-live bg-live/10 font-mono text-xs">
                visitor
              </div>
              {["email", "fp", "ip", "lead"].map((node, index) => (
                <div
                  key={node}
                  className="absolute grid size-14 place-items-center rounded-full border border-border bg-raised font-mono text-xs text-muted"
                  style={{
                    left: `${index % 2 === 0 ? 0 : 164}px`,
                    top: `${index < 2 ? 0 : 164}px`
                  }}
                >
                  {node}
                </div>
              ))}
            </div>
          </div>
        </Card>
        <Card className="p-4">
          <h2 className="font-display text-xl">Lead Profile</h2>
          <div className="mt-4 grid gap-3 sm:grid-cols-2">
            {[
              ["Score", "86"],
              ["Stage", "qualified"],
              ["Consent", "captured"],
              ["Tags", "demo, returning"]
            ].map(([label, value]) => (
              <div key={label} className="rounded-ui border border-border bg-raised p-3">
                <div className="text-xs text-muted">{label}</div>
                <div className="mt-1 font-mono text-sm">{value}</div>
              </div>
            ))}
          </div>
        </Card>
      </section>
    </AppShell>
  );
}
