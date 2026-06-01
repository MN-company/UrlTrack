import { SectionPage } from "@/components/section-page";

export default function ApiWebhooksPage() {
  return (
    <SectionPage
      title="API & Webhooks"
      subtitle="API keys and outbound delivery"
      rows={[
        ["n8n_pipeline", "active", "visit.created, lead.updated"],
        ["crm_sync", "active", "HMAC signed"],
        ["legacy_listener", "paused", "5 retries failed"]
      ]}
    />
  );
}
