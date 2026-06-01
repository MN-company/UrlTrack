import { describe, expect, it } from "vitest";

import { createLinkSchema, escapeHtml, normalizeDestinationUrl } from "./index";

describe("shared validation", () => {
  it("normalizes http URLs and rejects dangerous schemes", () => {
    expect(normalizeDestinationUrl("example.com/path#secret")).toBe("https://example.com/path");
    expect(() => normalizeDestinationUrl("javascript:alert(1)")).toThrow("Only http/https");
  });

  it("validates link creation payloads", () => {
    const parsed = createLinkSchema.parse({
      workspace_id: "00000000-0000-4000-8000-000000000000",
      slug: "Launch_01",
      destination_url: "https://example.com"
    });

    expect(parsed.status).toBe("active");
    expect(parsed.destination_url).toBe("https://example.com/");
  });

  it("escapes HTML for redirect templates", () => {
    expect(escapeHtml(`<script>"x"</script>`)).toBe("&lt;script&gt;&quot;x&quot;&lt;/script&gt;");
  });
});
