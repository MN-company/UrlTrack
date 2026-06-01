import { randomBytes } from "node:crypto";

import cors from "@fastify/cors";
import helmet from "@fastify/helmet";
import rateLimit from "@fastify/rate-limit";
import swagger from "@fastify/swagger";
import swaggerUi from "@fastify/swagger-ui";
import Fastify, { type FastifyInstance } from "fastify";
import { ZodError } from "zod";

import {
  createCampaignSchema,
  createLinkSchema,
  createWebhookSchema,
  fingerprintPayloadSchema,
  paginationSchema,
  updateLinkSchema
} from "@urltrack/shared";

import { evaluateAccessControl } from "./access-control";
import { createAuthContext, requireAuth, requireWorkspace } from "./auth";
import type { ApiConfig } from "./config";
import { createVisitToken, hashSecret, verifyVisitToken } from "./crypto";
import { sendData, sendError } from "./http";
import { createEnrichmentEnqueuer, type EnqueueEnrichment } from "./queue";
import { InMemoryRepository } from "./repositories/memory";
import { PrismaRepository } from "./repositories/prisma";
import type {
  CampaignRecord,
  LinkRecord,
  UrlTrackRepository,
  VisitRecord,
  WebhookEndpointRecord
} from "./repositories/types";
import { RepositoryConflictError } from "./repositories/types";
import { buildRedirectPage } from "./redirect-page";

export type BuildServerOptions = {
  config: ApiConfig;
  enqueueEnrichment?: EnqueueEnrichment;
  repository?: UrlTrackRepository;
};

export async function buildServer(options: BuildServerOptions): Promise<FastifyInstance> {
  const repository =
    options.repository ??
    (options.config.URLTRACK_REPOSITORY === "memory" ? new InMemoryRepository() : new PrismaRepository());
  const enqueueEnrichment = options.enqueueEnrichment ?? createEnrichmentEnqueuer(options.config.REDIS_URL);
  const authContext = createAuthContext(options.config, repository);
  const app = Fastify({
    logger: true,
    trustProxy: options.config.API_TRUST_PROXY
  });

  app.addContentTypeParser("text/plain", { parseAs: "string" }, (_request, body, done) => {
    try {
      const text = typeof body === "string" ? body : body.toString("utf8");
      done(null, JSON.parse(text));
    } catch {
      done(null, body);
    }
  });

  await app.register(helmet, {
    contentSecurityPolicy: false
  });
  await app.register(cors, {
    credentials: true,
    origin: [options.config.BASE_DOMAIN, options.config.API_PUBLIC_URL]
  });
  await app.register(rateLimit, {
    max: options.config.API_RATE_LIMIT_MAX,
    timeWindow: "1 minute"
  });
  await app.register(swagger, {
    openapi: {
      info: {
        title: "UrlTrack V2 API",
        version: "2.0.0"
      },
      servers: [{ url: options.config.API_PUBLIC_URL }],
      components: {
        securitySchemes: {
          ApiKeyAuth: { type: "apiKey", in: "header", name: "X-Api-Key" },
          SupabaseBearer: { type: "http", scheme: "bearer" }
        }
      },
      security: [{ ApiKeyAuth: [] }, { SupabaseBearer: [] }]
    }
  });
  await app.register(swaggerUi, {
    routePrefix: "/api/docs"
  });

  const auth = requireAuth(authContext);

  app.get("/health", { schema: { hide: true } }, async (_request, reply) => sendData(reply, { ok: true }));

  app.post("/api/v1/links", { preHandler: auth, schema: { tags: ["links"], summary: "Create link" } }, async (request, reply) => {
    try {
      const parsed = createLinkSchema.parse(request.body);
      const workspaceId = requireWorkspace(request, parsed.workspace_id);
      const link = await repository.createLink({
        workspaceId,
        campaignId: parsed.campaign_id ?? null,
        domainId: parsed.domain_id ?? null,
        slug: parsed.slug,
        destinationUrl: parsed.destination_url,
        accessControlConfig: parsed.access_control_config ?? {},
        routingConfig: parsed.routing_config ?? {},
        notificationConfig: parsed.notification_config ?? {},
        qrConfig: parsed.qr_config ?? {},
        flowConfig: parsed.flow_config ?? { nodes: [], edges: [] },
        status: parsed.status,
        createdBy: request.principal?.userId ?? request.principal?.apiKeyId ?? "api"
      });
      return sendData(reply.status(201), serializeLink(link));
    } catch (error) {
      return handleRouteError(error, reply);
    }
  });

  app.get("/api/v1/links", { preHandler: auth, schema: { tags: ["links"], summary: "List links" } }, async (request, reply) => {
    const { page, per_page: perPage } = paginationSchema.parse(request.query);
    const workspaceId = requireWorkspace(request);
    const result = await repository.listLinks(workspaceId, page, perPage);
    return sendData(reply, result.items.map(serializeLink), { page, per_page: perPage, total: result.total });
  });

  app.get("/api/v1/links/:id", { preHandler: auth, schema: { tags: ["links"], summary: "Get link" } }, async (request, reply) => {
    const id = routeParam(request.params, "id");
    const workspaceId = requireWorkspace(request);
    const link = await repository.getLink(workspaceId, id);
    if (!link) {
      return sendError(reply, 404, "not_found", "Link not found.");
    }
    return sendData(reply, serializeLink(link));
  });

  app.patch("/api/v1/links/:id", { preHandler: auth, schema: { tags: ["links"], summary: "Update link" } }, async (request, reply) => {
    try {
      const parsed = updateLinkSchema.parse(request.body);
      const id = routeParam(request.params, "id");
      const workspaceId = requireWorkspace(request);
      const link = await repository.updateLink(workspaceId, id, {
        campaignId: parsed.campaign_id,
        domainId: parsed.domain_id,
        slug: parsed.slug,
        destinationUrl: parsed.destination_url,
        accessControlConfig: parsed.access_control_config,
        routingConfig: parsed.routing_config,
        notificationConfig: parsed.notification_config,
        qrConfig: parsed.qr_config,
        flowConfig: parsed.flow_config,
        status: parsed.status
      });
      if (!link) {
        return sendError(reply, 404, "not_found", "Link not found.");
      }
      return sendData(reply, serializeLink(link));
    } catch (error) {
      return handleRouteError(error, reply);
    }
  });

  app.delete("/api/v1/links/:id", { preHandler: auth, schema: { tags: ["links"], summary: "Archive link" } }, async (request, reply) => {
    const id = routeParam(request.params, "id");
    const workspaceId = requireWorkspace(request);
    const link = await repository.archiveLink(workspaceId, id);
    if (!link) {
      return sendError(reply, 404, "not_found", "Link not found.");
    }
    return sendData(reply, serializeLink(link));
  });

  app.get("/api/v1/links/:id/stats", { preHandler: auth, schema: { tags: ["links"], summary: "Link stats" } }, async (request, reply) => {
    const id = routeParam(request.params, "id");
    const workspaceId = requireWorkspace(request);
    return sendData(reply, await repository.getLinkStats(workspaceId, id));
  });

  app.get("/api/v1/links/:id/visits", { preHandler: auth, schema: { tags: ["links"], summary: "Link visits" } }, async (request, reply) => {
    const id = routeParam(request.params, "id");
    const workspaceId = requireWorkspace(request);
    const { page, per_page: perPage } = paginationSchema.parse(request.query);
    const result = await repository.listVisits(workspaceId, id, page, perPage);
    return sendData(reply, result.items.map(serializeVisit), { page, per_page: perPage, total: result.total });
  });

  app.get("/api/v1/campaigns", { preHandler: auth, schema: { tags: ["campaigns"], summary: "List campaigns" } }, async (request, reply) => {
    const workspaceId = requireWorkspace(request);
    return sendData(reply, (await repository.listCampaigns(workspaceId)).map(serializeCampaign));
  });

  app.post("/api/v1/campaigns", { preHandler: auth, schema: { tags: ["campaigns"], summary: "Create campaign" } }, async (request, reply) => {
    try {
      const parsed = createCampaignSchema.parse(request.body);
      const workspaceId = requireWorkspace(request, parsed.workspace_id);
      const campaign = await repository.createCampaign({
        workspaceId,
        name: parsed.name,
        description: parsed.description ?? null,
        status: parsed.status,
        goal: parsed.goal ?? null
      });
      return sendData(reply.status(201), serializeCampaign(campaign));
    } catch (error) {
      return handleRouteError(error, reply);
    }
  });

  app.get("/api/v1/campaigns/:id/stats", { preHandler: auth, schema: { tags: ["campaigns"], summary: "Campaign stats" } }, async (request, reply) => {
    const id = routeParam(request.params, "id");
    const workspaceId = requireWorkspace(request);
    return sendData(reply, await repository.getCampaignStats(workspaceId, id));
  });

  app.get("/api/v1/visitors", { preHandler: auth, schema: { tags: ["visitors"], summary: "List visitors" } }, async (request, reply) => {
    const workspaceId = requireWorkspace(request);
    const { page, per_page: perPage } = paginationSchema.parse(request.query);
    const result = await repository.listVisitors(workspaceId, page, perPage);
    return sendData(reply, result.items, { page, per_page: perPage, total: result.total });
  });

  app.get("/api/v1/visitors/:id", { preHandler: auth, schema: { tags: ["visitors"], summary: "Visitor detail" } }, async (_request, reply) => {
    return sendError(reply, 501, "not_implemented", "Visitor detail is backed by the visitors list in this MVP.");
  });

  app.get("/api/v1/leads", { preHandler: auth, schema: { tags: ["leads"], summary: "List leads" } }, async (request, reply) => {
    const workspaceId = requireWorkspace(request);
    const { page, per_page: perPage } = paginationSchema.parse(request.query);
    const result = await repository.listLeads(workspaceId, page, perPage);
    return sendData(reply, result.items, { page, per_page: perPage, total: result.total });
  });

  app.get("/api/v1/webhooks", { preHandler: auth, schema: { tags: ["webhooks"], summary: "List webhooks" } }, async (request, reply) => {
    const workspaceId = requireWorkspace(request);
    return sendData(reply, (await repository.listWebhooks(workspaceId)).map((webhook) => serializeWebhook(webhook, false)));
  });

  app.post("/api/v1/webhooks", { preHandler: auth, schema: { tags: ["webhooks"], summary: "Register webhook" } }, async (request, reply) => {
    try {
      const parsed = createWebhookSchema.parse(request.body);
      const workspaceId = requireWorkspace(request, parsed.workspace_id);
      const webhook = await repository.createWebhook({
        workspaceId,
        url: parsed.url,
        name: parsed.name,
        enabled: parsed.enabled,
        events: parsed.events,
        secret: randomBytes(32).toString("hex")
      });
      return sendData(reply.status(201), serializeWebhook(webhook, true));
    } catch (error) {
      return handleRouteError(error, reply);
    }
  });

  app.post(
    "/api/v1/fp",
    {
      config: { rateLimit: { max: 60, timeWindow: "1 minute" } },
      schema: { security: [], tags: ["fingerprint"], summary: "Receive ThumbmarkJS fingerprint" }
    },
    async (request, reply) => {
      try {
        const parsed = fingerprintPayloadSchema.parse(request.body);
        const verified = verifyVisitToken(parsed.visit_token, options.config.visitTokenSecret);
        if (!verified) {
          return sendError(reply, 403, "invalid_visit_token", "Visit token is invalid or expired.");
        }
        const visit = await repository.updateVisitFingerprint(verified.visitId, parsed.thumbmark);
        if (!visit) {
          return sendError(reply, 404, "not_found", "Visit not found.");
        }
        await enqueueEnrichment(visit.id);
        return sendData(reply, { ok: true });
      } catch (error) {
        return handleRouteError(error, reply);
      }
    }
  );

  app.get("/:slug", { schema: { security: [], tags: ["redirect"], summary: "Public redirect" } }, async (request, reply) => {
    const slug = routeParam(request.params, "slug");
    const link = await repository.findLinkBySlug(slug);
    if (!link) {
      return reply.status(404).type("text/plain").send("Not found");
    }

    const decision = evaluateAccessControl(link, request);
    const visit = await repository.createVisit({
      workspaceId: link.workspaceId,
      linkId: link.id,
      sourceType: request.url.includes("source=qr") ? "qr" : "link",
      eventType: decision.allowed ? "visit.created" : decision.eventType,
      ip: request.ip,
      userAgent: request.headers["user-agent"]?.toString() ?? null,
      referrer: request.headers.referer?.toString() ?? null,
      countryCode: request.headers["cf-ipcountry"]?.toString() ?? null,
      deviceType: decision.allowed ? decision.deviceType : null
    });

    if (!decision.allowed) {
      await enqueueEnrichment(visit.id);
      return reply
        .status(decision.statusCode)
        .type("text/html")
        .send(`<html><body><h1>${decision.reason}</h1></body></html>`);
    }

    const visitToken = createVisitToken(visit.id, options.config.visitTokenSecret);
    await repository.updateVisitTokenHash(visit.id, hashSecret(visitToken));
    await enqueueEnrichment(visit.id);
    const page = buildRedirectPage({
      destinationUrl: decision.destinationUrl,
      visitToken
    });

    return reply
      .header(
        "content-security-policy",
        `default-src 'none'; script-src 'nonce-${page.nonce}' https://cdn.jsdelivr.net; style-src 'nonce-${page.nonce}'; connect-src 'self'; img-src 'self' data:; base-uri 'none'; object-src 'none'; frame-ancestors 'none'; form-action 'none'`
      )
      .header("cache-control", "no-store")
      .type("text/html")
      .send(page.html);
  });

  app.setErrorHandler((error, _request, reply) => {
    if (error instanceof ZodError) {
      return sendError(reply, 400, "validation_error", "Invalid request payload.", error.flatten());
    }
    app.log.error(error);
    return sendError(reply, 500, "internal_error", "Unexpected server error.");
  });

  return app;
}

function routeParam(params: unknown, key: string): string {
  if (!params || typeof params !== "object") {
    return "";
  }
  const value = (params as Record<string, unknown>)[key];
  return typeof value === "string" ? value : "";
}

function handleRouteError(error: unknown, reply: Parameters<typeof sendError>[0]) {
  if (error instanceof ZodError) {
    return sendError(reply, 400, "validation_error", "Invalid request payload.", error.flatten());
  }
  if (error instanceof RepositoryConflictError) {
    return sendError(reply, 409, "conflict", error.message);
  }
  if (error instanceof Error && error.message.includes("workspace_id")) {
    return sendError(reply, 403, "workspace_mismatch", error.message);
  }
  throw error;
}

function serializeLink(link: LinkRecord) {
  return {
    id: link.id,
    workspace_id: link.workspaceId,
    campaign_id: link.campaignId,
    domain_id: link.domainId,
    slug: link.slug,
    destination_url: link.destinationUrl,
    access_control_config: link.accessControlConfig,
    routing_config: link.routingConfig,
    notification_config: link.notificationConfig,
    qr_config: link.qrConfig,
    flow_config: link.flowConfig,
    status: link.status,
    click_count: link.clickCount,
    archived_at: link.archivedAt,
    created_at: link.createdAt,
    updated_at: link.updatedAt
  };
}

function serializeVisit(visit: VisitRecord) {
  return {
    id: visit.id,
    workspace_id: visit.workspaceId,
    link_id: visit.linkId,
    visitor_id: visit.visitorId,
    source_type: visit.sourceType,
    traffic_quality_score: visit.trafficQualityScore,
    identity_confidence_score: visit.identityConfidenceScore,
    event_type: visit.eventType,
    raw_fingerprint_json: visit.rawFingerprintJson,
    ip: visit.ip,
    user_agent: visit.userAgent,
    referrer: visit.referrer,
    country_code: visit.countryCode,
    device_type: visit.deviceType,
    is_vpn: visit.isVpn,
    is_bot: visit.isBot,
    is_datacenter: visit.isDatacenter,
    match_reasons: visit.matchReasons,
    review_suggested: visit.reviewSuggested,
    created_at: visit.createdAt
  };
}

function serializeCampaign(campaign: CampaignRecord) {
  return {
    id: campaign.id,
    workspace_id: campaign.workspaceId,
    name: campaign.name,
    description: campaign.description,
    status: campaign.status,
    goal: campaign.goal,
    created_at: campaign.createdAt,
    updated_at: campaign.updatedAt
  };
}

function serializeWebhook(webhook: WebhookEndpointRecord, includeSecret: boolean) {
  return {
    id: webhook.id,
    workspace_id: webhook.workspaceId,
    url: webhook.url,
    name: webhook.name,
    enabled: webhook.enabled,
    events: webhook.events,
    created_at: webhook.createdAt,
    updated_at: webhook.updatedAt,
    ...(includeSecret ? { secret: webhook.secret } : {})
  };
}
