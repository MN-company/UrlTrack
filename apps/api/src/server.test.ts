import { describe, expect, it } from "vitest";

import { loadConfig } from "./config";
import { hashSecret } from "./crypto";
import { InMemoryRepository } from "./repositories/memory";
import { buildServer } from "./server";

const workspaceId = "00000000-0000-4000-8000-000000000000";

async function testApp() {
  const repository = new InMemoryRepository();
  repository.seedApiKey({
    id: "api-key-1",
    workspaceId,
    keyHash: hashSecret("ut_test_key"),
    scopes: ["*"],
    expiresAt: null
  });

  const app = await buildServer({
    config: loadConfig({
      NODE_ENV: "test",
      API_PUBLIC_URL: "http://localhost:8000",
      BASE_DOMAIN: "http://localhost:3000",
      URLTRACK_REPOSITORY: "memory",
      VISIT_TOKEN_SECRET: "test-secret-that-is-long-enough-for-urltrack"
    }),
    enqueueEnrichment: async () => undefined,
    repository
  });

  return { app, repository };
}

describe("UrlTrack API", () => {
  it("creates and lists links with API key auth", async () => {
    const { app } = await testApp();

    const createResponse = await app.inject({
      method: "POST",
      url: "/api/v1/links",
      headers: { "x-api-key": "ut_test_key" },
      payload: {
        workspace_id: workspaceId,
        slug: "launch",
        destination_url: "example.com/demo"
      }
    });

    expect(createResponse.statusCode).toBe(201);
    expect(createResponse.json().data.destination_url).toBe("https://example.com/demo");

    const listResponse = await app.inject({
      method: "GET",
      url: "/api/v1/links",
      headers: { "x-api-key": "ut_test_key" }
    });
    expect(listResponse.statusCode).toBe(200);
    expect(listResponse.json().meta.total).toBe(1);

    await app.close();
  });

  it("serves a ThumbmarkJS bounce page and accepts the beacon", async () => {
    const { app, repository } = await testApp();
    await repository.createLink({
      workspaceId,
      campaignId: null,
      domainId: null,
      slug: "abc",
      destinationUrl: "https://example.com/",
      accessControlConfig: {},
      routingConfig: {},
      notificationConfig: {},
      qrConfig: {},
      flowConfig: { nodes: [], edges: [] },
      status: "active",
      createdBy: "test"
    });

    const redirectResponse = await app.inject({
      method: "GET",
      url: "/abc",
      headers: { "user-agent": "Mozilla/5.0" }
    });

    expect(redirectResponse.statusCode).toBe(200);
    expect(redirectResponse.headers["content-security-policy"]).toContain("cdn.jsdelivr.net");
    expect(redirectResponse.body).toContain("@thumbmarkjs/thumbmarkjs");
    expect(redirectResponse.body).toContain("https://example.com/");

    const visit = [...repository.visits.values()][0];
    expect(visit).toBeDefined();
    const token = redirectResponse.body.match(/const visitToken = "([^"]+)"/)?.[1];
    expect(token).toBeDefined();

    const fpResponse = await app.inject({
      method: "POST",
      url: "/api/v1/fp",
      payload: {
        visit_token: token,
        thumbmark: { hash: "thumbmark-hash" }
      }
    });

    expect(fpResponse.statusCode).toBe(200);
    expect(repository.visits.get(visit!.id)?.rawFingerprintJson).toEqual({ hash: "thumbmark-hash" });

    await app.close();
  });

  it("rejects mismatched workspace IDs", async () => {
    const { app } = await testApp();
    const response = await app.inject({
      method: "POST",
      url: "/api/v1/links",
      headers: { "x-api-key": "ut_test_key" },
      payload: {
        workspace_id: "11111111-1111-4111-8111-111111111111",
        slug: "blocked",
        destination_url: "https://example.com"
      }
    });

    expect(response.statusCode).toBe(403);
    await app.close();
  });
});
