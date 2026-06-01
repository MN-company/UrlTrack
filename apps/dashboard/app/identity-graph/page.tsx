import { SectionPage } from "@/components/section-page";

export default function IdentityGraphPage() {
  return (
    <SectionPage
      title="Identity Graph"
      subtitle="Visitor, signal and lead relationships"
      badge="graph"
      rows={[
        ["visitor_91ad", "active", "5 signals · 4 visits"],
        ["canvas_c4a0", "verified", "linked to 3 visitors"],
        ["email_b3f1", "active", "lead owner signal"]
      ]}
    />
  );
}
