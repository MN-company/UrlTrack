import { Network } from "lucide-react";
import Link from "next/link";

import { Card } from "@/components/ui/card";

export function AuthPanel({ children, title, footer }: { children: React.ReactNode; title: string; footer: React.ReactNode }) {
  return (
    <main className="grid min-h-screen place-items-center bg-obsidian px-4 py-8 text-ink">
      <div className="w-full max-w-md">
        <div className="mb-5 flex items-center gap-3">
          <div className="grid size-10 place-items-center rounded-ui border border-live/50 bg-live/10">
            <Network className="size-5 text-live" aria-hidden="true" />
          </div>
          <div>
            <div className="font-display text-xl">UrlTrack</div>
            <Link href="/" className="font-mono text-xs text-muted">
              INTEL OPS
            </Link>
          </div>
        </div>
        <Card className="p-5">
          <h1 className="font-display text-2xl">{title}</h1>
          <div className="mt-5">{children}</div>
        </Card>
        <div className="mt-4 text-sm text-muted">{footer}</div>
      </div>
    </main>
  );
}
