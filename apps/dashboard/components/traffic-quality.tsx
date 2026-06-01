import { Card } from "./ui/card";

const rows = [
  { label: "Clean", value: 72, color: "bg-live" },
  { label: "Review", value: 18, color: "bg-accent" },
  { label: "Blocked", value: 10, color: "bg-red-400" }
];

export function TrafficQuality() {
  return (
    <Card className="p-4">
      <h2 className="font-display text-lg">Traffic Quality</h2>
      <div className="mt-4 space-y-4">
        {rows.map((row) => (
          <div key={row.label}>
            <div className="mb-2 flex items-center justify-between text-sm">
              <span className="text-muted">{row.label}</span>
              <span className="font-mono">{row.value}%</span>
            </div>
            <div className="h-2 rounded-full bg-raised">
              <div className={`${row.color} h-2 rounded-full`} style={{ width: `${row.value}%` }} />
            </div>
          </div>
        ))}
      </div>
    </Card>
  );
}
