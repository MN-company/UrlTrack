import { SectionPage } from "@/components/section-page";

export default function NotificationsPage() {
  return (
    <SectionPage
      title="Notifications"
      subtitle="Telegram, email and threshold rules"
      rows={[
        ["high_value_lead", "active", "lead.score_changed > 75"],
        ["suspicious_cluster", "active", "suspicious.detected"],
        ["qr_spike", "paused", "qr.scanned > baseline"]
      ]}
    />
  );
}
