import { createHmac } from "node:crypto";

import { describe, expect, it } from "vitest";

import { retryDelayForAttempt, signWebhookPayload } from "./webhook-delivery";

describe("webhook delivery", () => {
  it("signs payloads with HMAC-SHA256", () => {
    const body = JSON.stringify({ event: "visit.created" });
    const expected = createHmac("sha256", "secret").update(body).digest("hex");

    expect(signWebhookPayload("secret", body)).toBe(`sha256=${expected}`);
  });

  it("uses the required retry schedule", () => {
    expect(retryDelayForAttempt(1)).toBe(30_000);
    expect(retryDelayForAttempt(2)).toBe(5 * 60_000);
    expect(retryDelayForAttempt(5)).toBe(24 * 60 * 60_000);
    expect(retryDelayForAttempt(6)).toBeUndefined();
  });
});
