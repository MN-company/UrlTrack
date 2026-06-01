import { AppShell } from "@/components/shell";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";

export default function OnboardingPage() {
  return (
    <AppShell>
      <div className="mx-auto max-w-2xl">
        <h1 className="font-display text-3xl">Create Workspace</h1>
        <Card className="mt-5 p-5">
          <form className="space-y-4">
            <label className="block">
              <span className="text-sm text-muted">Workspace name</span>
              <input className="mt-2 h-10 w-full rounded-ui border border-border bg-obsidian px-3 outline-none focus:border-live" name="name" defaultValue="MN Ops" />
            </label>
            <label className="block">
              <span className="text-sm text-muted">Slug</span>
              <input className="mt-2 h-10 w-full rounded-ui border border-border bg-obsidian px-3 font-mono outline-none focus:border-live" name="slug" defaultValue="mn-ops" />
            </label>
            <Button type="submit" tone="primary">Create Workspace</Button>
          </form>
        </Card>
      </div>
    </AppShell>
  );
}
