import { SectionPage } from "@/components/section-page";

export default function LeadsPage() {
  return (
    <SectionPage
      title="Leads"
      subtitle="High-confidence identified visitors"
      rows={[
        ["lead_91ad", "active", "score 86 · demo, returning"],
        ["lead_c47a", "active", "score 73 · email captured"],
        ["lead_70be", "review", "score 58 · identity conflict"]
      ]}
    />
  );
}
