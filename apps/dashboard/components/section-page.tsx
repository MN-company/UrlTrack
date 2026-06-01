import { AppShell } from "@/components/shell";
import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";

type SectionPageProps = {
  title: string;
  subtitle: string;
  badge?: string;
  rows: Array<[string, string, string]>;
};

export function SectionPage({ title, subtitle, badge = "workspace", rows }: SectionPageProps) {
  return (
    <AppShell>
      <div className="mb-5 flex flex-wrap items-center justify-between gap-4">
        <div>
          <h1 className="font-display text-3xl">{title}</h1>
          <p className="mt-1 text-sm text-muted">{subtitle}</p>
        </div>
        <Badge tone="info">{badge}</Badge>
      </div>
      <Card className="p-4">
        <div className="overflow-x-auto">
          <table className="w-full min-w-[620px] border-collapse text-sm">
            <thead className="text-left text-muted">
              <tr className="border-b border-border">
                <th className="py-2 font-normal">Name</th>
                <th className="py-2 font-normal">Status</th>
                <th className="py-2 font-normal">Signal</th>
              </tr>
            </thead>
            <tbody>
              {rows.map(([name, status, signal]) => (
                <tr key={name} className="border-b border-border last:border-0">
                  <td className="py-3 font-mono">{name}</td>
                  <td className="py-3">
                    <Badge tone={status === "active" || status === "verified" ? "live" : "warning"}>{status}</Badge>
                  </td>
                  <td className="py-3 text-muted">{signal}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>
    </AppShell>
  );
}
