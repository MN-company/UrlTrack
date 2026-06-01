import { SectionPage } from "@/components/section-page";

export default function CampaignsPage() {
  return (
    <SectionPage
      title="Campaigns"
      subtitle="Workspace campaign groups"
      rows={[
        ["summer_launch", "active", "4 links · 12.4K visits"],
        ["booth_qr", "active", "2 links · 1.2K scans"],
        ["investor_followup", "paused", "reviewing traffic quality"]
      ]}
    />
  );
}
