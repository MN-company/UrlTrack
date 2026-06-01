import { readFileSync } from "node:fs";
import { join } from "node:path";

import { describe, expect, it } from "vitest";

const schema = readFileSync(join(process.cwd(), "prisma/schema.prisma"), "utf8");

describe("Prisma schema", () => {
  it("keeps core entities scoped to workspace_id", () => {
    for (const model of [
      "Campaign",
      "Domain",
      "Link",
      "Visit",
      "Visitor",
      "VisitorSignal",
      "Lead",
      "ApiKey",
      "WebhookEndpoint",
      "WebhookDelivery",
      "NotificationRule",
      "AIInsight",
      "AuditLog"
    ]) {
      const match = schema.match(new RegExp(`model ${model} \\{([\\s\\S]*?)\\n\\}`));
      expect(match?.[1]).toContain("workspaceId");
    }
  });

  it("does not define a global user model because Supabase Auth owns users", () => {
    expect(schema).not.toMatch(/model\s+User\s+\{/);
  });
});
