import {
  Activity,
  Bell,
  Bot,
  ChartNoAxesCombined,
  CircleDot,
  GitBranch,
  Globe,
  Home,
  KeyRound,
  Link2,
  Network,
  QrCode,
  Settings,
  Target,
  Users
} from "lucide-react";
import Link from "next/link";

const navItems = [
  { href: "/", icon: Home, label: "Dashboard" },
  { href: "/campaigns", icon: Target, label: "Campaigns" },
  { href: "/links/demo", icon: Link2, label: "Links" },
  { href: "/qr", icon: QrCode, label: "QR Codes" },
  { href: "/visitors/demo", icon: Users, label: "Visitors" },
  { href: "/leads", icon: CircleDot, label: "Leads" },
  { href: "/analytics", icon: ChartNoAxesCombined, label: "Analytics" },
  { href: "/identity-graph", icon: GitBranch, label: "Identity Graph" },
  { href: "/ai-insights", icon: Bot, label: "AI Insights" },
  { href: "/notifications", icon: Bell, label: "Notifications" },
  { href: "/domains", icon: Globe, label: "Domains" },
  { href: "/api-webhooks", icon: KeyRound, label: "API & Webhooks" },
  { href: "/settings", icon: Settings, label: "Settings" }
] as const;

export function AppShell({ children }: { children: React.ReactNode }) {
  return (
    <div className="min-h-screen bg-obsidian text-ink">
      <aside className="fixed inset-y-0 left-0 hidden w-64 border-r border-border bg-panel/95 xl:block">
        <div className="flex h-16 items-center gap-3 border-b border-border px-5">
          <div className="grid size-9 place-items-center rounded-ui border border-live/50 bg-live/10">
            <Network className="size-5 text-live" aria-hidden="true" />
          </div>
          <div>
            <div className="font-display text-lg">UrlTrack</div>
            <div className="font-mono text-[11px] text-muted">INTEL OPS</div>
          </div>
        </div>
        <nav className="space-y-1 px-3 py-4">
          {navItems.map((item) => (
            <Link
              key={item.href}
              href={item.href}
              className="flex h-9 items-center gap-3 rounded-ui px-3 text-sm text-muted transition hover:bg-raised hover:text-ink"
            >
              <item.icon className="size-4" aria-hidden="true" />
              <span>{item.label}</span>
            </Link>
          ))}
        </nav>
      </aside>

      <div className="xl:pl-64">
        <header className="sticky top-0 z-20 flex h-16 items-center justify-between border-b border-border bg-obsidian/90 px-4 backdrop-blur md:px-6">
          <div className="flex items-center gap-3 xl:hidden">
            <Network className="size-5 text-live" aria-hidden="true" />
            <span className="font-display text-lg">UrlTrack</span>
          </div>
          <div className="hidden items-center gap-2 font-mono text-xs text-muted xl:flex">
            <Activity className="size-4 text-live" aria-hidden="true" />
            <span>LIVE SIGNAL</span>
          </div>
          <div className="flex items-center gap-2">
            <span className="rounded-ui border border-border bg-panel px-3 py-1 font-mono text-xs text-muted">ws_mn_ops</span>
          </div>
        </header>
        <main className="mx-auto w-full max-w-7xl px-4 py-5 md:px-6">{children}</main>
      </div>
    </div>
  );
}
