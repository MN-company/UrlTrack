import { SectionPage } from "@/components/section-page";

export default function QRPage() {
  return (
    <SectionPage
      title="QR Codes"
      subtitle="QR assets and scan analytics"
      rows={[
        ["qr_booth_h", "active", "H correction · SVG"],
        ["qr_launch_green", "active", "M correction · PNG"],
        ["qr_safe_offer", "paused", "awaiting logo upload"]
      ]}
    />
  );
}
