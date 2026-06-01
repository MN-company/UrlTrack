import { SectionPage } from "@/components/section-page";

export default function DomainsPage() {
  return (
    <SectionPage
      title="Domains"
      subtitle="Workspace routing and SSL status"
      rows={[
        ["go.example.com", "verified", "SSL active"],
        ["qr.example.com", "verified", "SSL active"],
        ["fallback.example.net", "pending", "DNS check required"]
      ]}
    />
  );
}
