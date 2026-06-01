import type {
  ApiKey,
  Campaign,
  Lead,
  Link,
  Prisma,
  PrismaClient,
  Visit,
  Visitor,
  WebhookEndpoint
} from "@prisma/client";

import { prisma as defaultPrisma } from "@urltrack/db";

import type {
  ApiKeyRecord,
  CampaignRecord,
  CampaignStats,
  JsonRecord,
  LeadRecord,
  LinkCreateInput,
  LinkRecord,
  LinkStats,
  LinkUpdateInput,
  ListResult,
  UrlTrackRepository,
  VisitCreateInput,
  VisitRecord,
  VisitorRecord,
  WebhookEndpointRecord
} from "./types";

function asJsonRecord(value: Prisma.JsonValue): JsonRecord {
  return value && typeof value === "object" && !Array.isArray(value) ? (value as JsonRecord) : {};
}

function toLinkRecord(link: Link): LinkRecord {
  return {
    id: link.id,
    workspaceId: link.workspaceId,
    campaignId: link.campaignId,
    domainId: link.domainId,
    slug: link.slug,
    destinationUrl: link.destinationUrl,
    accessControlConfig: asJsonRecord(link.accessControlConfig),
    routingConfig: asJsonRecord(link.routingConfig),
    notificationConfig: asJsonRecord(link.notificationConfig),
    qrConfig: asJsonRecord(link.qrConfig),
    flowConfig: asJsonRecord(link.flowConfig),
    status: link.status,
    createdBy: link.createdBy,
    clickCount: link.clickCount,
    archivedAt: link.archivedAt,
    createdAt: link.createdAt,
    updatedAt: link.updatedAt
  };
}

function toVisitRecord(visit: Visit): VisitRecord {
  return {
    id: visit.id,
    workspaceId: visit.workspaceId,
    linkId: visit.linkId,
    visitorId: visit.visitorId,
    sourceType: visit.sourceType,
    trafficQualityScore: visit.trafficQualityScore,
    identityConfidenceScore: visit.identityConfidenceScore,
    eventType: visit.eventType,
    rawFingerprintJson: asJsonRecord(visit.rawFingerprintJson),
    ip: visit.ip,
    userAgent: visit.userAgent,
    referrer: visit.referrer,
    countryCode: visit.countryCode,
    deviceType: visit.deviceType,
    isVpn: visit.isVpn,
    isBot: visit.isBot,
    isDatacenter: visit.isDatacenter,
    visitTokenHash: visit.visitTokenHash,
    matchReasons: visit.matchReasons,
    reviewSuggested: visit.reviewSuggested,
    createdAt: visit.createdAt,
    updatedAt: visit.updatedAt
  };
}

function toCampaignRecord(campaign: Campaign): CampaignRecord {
  return {
    id: campaign.id,
    workspaceId: campaign.workspaceId,
    name: campaign.name,
    description: campaign.description,
    status: campaign.status,
    goal: campaign.goal,
    createdAt: campaign.createdAt,
    updatedAt: campaign.updatedAt
  };
}

function toWebhookRecord(webhook: WebhookEndpoint): WebhookEndpointRecord {
  return {
    id: webhook.id,
    workspaceId: webhook.workspaceId,
    url: webhook.url,
    secret: webhook.secret,
    name: webhook.name,
    enabled: webhook.enabled,
    events: webhook.events,
    createdAt: webhook.createdAt,
    updatedAt: webhook.updatedAt
  };
}

function toVisitorRecord(visitor: Visitor): VisitorRecord {
  return {
    id: visitor.id,
    workspaceId: visitor.workspaceId,
    primaryEmail: visitor.primaryEmail,
    primaryIp: visitor.primaryIp,
    primaryCanvasHash: visitor.primaryCanvasHash,
    primaryFingerprintHash: visitor.primaryFingerprintHash,
    firstSeen: visitor.firstSeen,
    lastSeen: visitor.lastSeen,
    totalVisits: visitor.totalVisits,
    confidenceScore: visitor.confidenceScore,
    trafficQualityAverage: visitor.trafficQualityAverage,
    attributesJson: asJsonRecord(visitor.attributesJson)
  };
}

function toLeadRecord(lead: Lead): LeadRecord {
  return {
    id: lead.id,
    workspaceId: lead.workspaceId,
    visitorId: lead.visitorId,
    score: lead.score,
    confidenceScore: lead.confidenceScore,
    tags: lead.tags,
    lifecycleStage: lead.lifecycleStage,
    consentStatus: lead.consentStatus,
    customFieldsJson: asJsonRecord(lead.customFieldsJson),
    createdAt: lead.createdAt,
    updatedAt: lead.updatedAt
  };
}

export class PrismaRepository implements UrlTrackRepository {
  constructor(private readonly db: PrismaClient = defaultPrisma) {}

  async archiveLink(workspaceId: string, id: string): Promise<LinkRecord | undefined> {
    const existing = await this.getLink(workspaceId, id);
    if (!existing) {
      return undefined;
    }
    const link = await this.db.link.update({
      where: { id },
      data: { archivedAt: new Date(), status: "archived" }
    });
    return toLinkRecord(link);
  }

  async createCampaign(input: Omit<CampaignRecord, "id" | "createdAt" | "updatedAt">): Promise<CampaignRecord> {
    const campaign = await this.db.campaign.create({
      data: {
        workspaceId: input.workspaceId,
        name: input.name,
        description: input.description,
        status: input.status as Campaign["status"],
        goal: input.goal
      }
    });
    return toCampaignRecord(campaign);
  }

  async createLink(input: LinkCreateInput): Promise<LinkRecord> {
    const link = await this.db.link.create({
      data: {
        workspaceId: input.workspaceId,
        campaignId: input.campaignId,
        domainId: input.domainId,
        slug: input.slug,
        destinationUrl: input.destinationUrl,
        accessControlConfig: input.accessControlConfig as Prisma.InputJsonValue,
        routingConfig: input.routingConfig as Prisma.InputJsonValue,
        notificationConfig: input.notificationConfig as Prisma.InputJsonValue,
        qrConfig: input.qrConfig as Prisma.InputJsonValue,
        flowConfig: input.flowConfig as Prisma.InputJsonValue,
        status: input.status,
        createdBy: input.createdBy
      }
    });
    return toLinkRecord(link);
  }

  async createVisit(input: VisitCreateInput): Promise<VisitRecord> {
    const visit = await this.db.visit.create({
      data: {
        workspaceId: input.workspaceId,
        linkId: input.linkId,
        sourceType: input.sourceType,
        eventType: input.eventType,
        ip: input.ip,
        userAgent: input.userAgent,
        referrer: input.referrer,
        countryCode: input.countryCode,
        deviceType: input.deviceType,
        isBot: input.isBot ?? false,
        isVpn: input.isVpn ?? false,
        isDatacenter: input.isDatacenter ?? false,
        visitTokenHash: input.visitTokenHash
      }
    });
    await this.db.link.update({
      where: { id: input.linkId },
      data: { clickCount: { increment: 1 } }
    });
    return toVisitRecord(visit);
  }

  async createWebhook(input: Omit<WebhookEndpointRecord, "id" | "createdAt" | "updatedAt">): Promise<WebhookEndpointRecord> {
    const webhook = await this.db.webhookEndpoint.create({
      data: input
    });
    return toWebhookRecord(webhook);
  }

  async findApiKeyByHash(keyHash: string): Promise<ApiKeyRecord | undefined> {
    const apiKey = await this.db.apiKey.findUnique({ where: { keyHash } });
    if (!apiKey || (apiKey.expiresAt && apiKey.expiresAt < new Date())) {
      return undefined;
    }
    return toApiKeyRecord(apiKey);
  }

  async findLinkBySlug(slug: string): Promise<LinkRecord | undefined> {
    const link = await this.db.link.findFirst({
      where: {
        slug,
        archivedAt: null
      }
    });
    return link ? toLinkRecord(link) : undefined;
  }

  async getCampaignStats(workspaceId: string, campaignId: string): Promise<CampaignStats> {
    const links = await this.db.link.findMany({
      where: { workspaceId, campaignId },
      select: { id: true }
    });
    const linkIds = links.map((link) => link.id);
    const [visits, leads] = await Promise.all([
      this.db.visit.count({ where: { workspaceId, linkId: { in: linkIds } } }),
      this.db.lead.count({ where: { workspaceId } })
    ]);
    return { links: links.length, visits, leads };
  }

  async getLink(workspaceId: string, id: string): Promise<LinkRecord | undefined> {
    const link = await this.db.link.findFirst({ where: { id, workspaceId } });
    return link ? toLinkRecord(link) : undefined;
  }

  async getLinkStats(workspaceId: string, id: string): Promise<LinkStats> {
    const [totalClicks, suspiciousClicks, qrClicks, uniqueVisitors] = await Promise.all([
      this.db.visit.count({ where: { workspaceId, linkId: id } }),
      this.db.visit.count({
        where: {
          workspaceId,
          linkId: id,
          OR: [{ isBot: true }, { isVpn: true }, { isDatacenter: true }]
        }
      }),
      this.db.visit.count({ where: { workspaceId, linkId: id, sourceType: "qr" } }),
      this.db.visit.findMany({
        where: { workspaceId, linkId: id },
        distinct: ["visitorId"],
        select: { visitorId: true }
      })
    ]);

    return {
      total_clicks: totalClicks,
      unique_visitors: uniqueVisitors.length,
      suspicious_clicks: suspiciousClicks,
      qr_clicks: qrClicks
    };
  }

  async isWorkspaceMember(workspaceId: string, userId: string): Promise<boolean> {
    const [ownedWorkspace, teamMember] = await Promise.all([
      this.db.workspace.findFirst({ where: { id: workspaceId, ownerUserId: userId }, select: { id: true } }),
      this.db.teamMember.findFirst({ where: { workspaceId, userId }, select: { id: true } })
    ]);
    return Boolean(ownedWorkspace || teamMember);
  }

  async listCampaigns(workspaceId: string): Promise<CampaignRecord[]> {
    const campaigns = await this.db.campaign.findMany({
      where: { workspaceId },
      orderBy: { createdAt: "desc" }
    });
    return campaigns.map(toCampaignRecord);
  }

  async listLeads(workspaceId: string, page: number, perPage: number): Promise<ListResult<LeadRecord>> {
    const [items, total] = await Promise.all([
      this.db.lead.findMany({
        where: { workspaceId },
        orderBy: { score: "desc" },
        skip: (page - 1) * perPage,
        take: perPage
      }),
      this.db.lead.count({ where: { workspaceId } })
    ]);
    return { items: items.map(toLeadRecord), total };
  }

  async listLinks(workspaceId: string, page: number, perPage: number): Promise<ListResult<LinkRecord>> {
    const [items, total] = await Promise.all([
      this.db.link.findMany({
        where: { workspaceId, archivedAt: null },
        orderBy: { createdAt: "desc" },
        skip: (page - 1) * perPage,
        take: perPage
      }),
      this.db.link.count({ where: { workspaceId, archivedAt: null } })
    ]);
    return { items: items.map(toLinkRecord), total };
  }

  async listVisitors(workspaceId: string, page: number, perPage: number): Promise<ListResult<VisitorRecord>> {
    const [items, total] = await Promise.all([
      this.db.visitor.findMany({
        where: { workspaceId },
        orderBy: { lastSeen: "desc" },
        skip: (page - 1) * perPage,
        take: perPage
      }),
      this.db.visitor.count({ where: { workspaceId } })
    ]);
    return { items: items.map(toVisitorRecord), total };
  }

  async listVisits(workspaceId: string, linkId: string, page: number, perPage: number): Promise<ListResult<VisitRecord>> {
    const [items, total] = await Promise.all([
      this.db.visit.findMany({
        where: { workspaceId, linkId },
        orderBy: { createdAt: "desc" },
        skip: (page - 1) * perPage,
        take: perPage
      }),
      this.db.visit.count({ where: { workspaceId, linkId } })
    ]);
    return { items: items.map(toVisitRecord), total };
  }

  async listWebhooks(workspaceId: string): Promise<WebhookEndpointRecord[]> {
    const webhooks = await this.db.webhookEndpoint.findMany({
      where: { workspaceId },
      orderBy: { createdAt: "desc" }
    });
    return webhooks.map(toWebhookRecord);
  }

  async touchApiKey(id: string): Promise<void> {
    await this.db.apiKey.update({
      where: { id },
      data: { lastUsedAt: new Date() }
    });
  }

  async updateLink(workspaceId: string, id: string, input: LinkUpdateInput): Promise<LinkRecord | undefined> {
    const existing = await this.getLink(workspaceId, id);
    if (!existing) {
      return undefined;
    }

    const data: Prisma.LinkUncheckedUpdateInput = {};
    if (input.campaignId !== undefined) data.campaignId = input.campaignId;
    if (input.domainId !== undefined) data.domainId = input.domainId;
    if (input.slug !== undefined) data.slug = input.slug;
    if (input.destinationUrl !== undefined) data.destinationUrl = input.destinationUrl;
    if (input.accessControlConfig !== undefined) data.accessControlConfig = input.accessControlConfig as Prisma.InputJsonValue;
    if (input.routingConfig !== undefined) data.routingConfig = input.routingConfig as Prisma.InputJsonValue;
    if (input.notificationConfig !== undefined) data.notificationConfig = input.notificationConfig as Prisma.InputJsonValue;
    if (input.qrConfig !== undefined) data.qrConfig = input.qrConfig as Prisma.InputJsonValue;
    if (input.flowConfig !== undefined) data.flowConfig = input.flowConfig as Prisma.InputJsonValue;
    if (input.status !== undefined) data.status = input.status;

    const link = await this.db.link.update({ where: { id }, data });
    return toLinkRecord(link);
  }

  async updateVisitFingerprint(visitId: string, rawFingerprintJson: JsonRecord): Promise<VisitRecord | undefined> {
    const visit = await this.db.visit
      .update({
        where: { id: visitId },
        data: { rawFingerprintJson: rawFingerprintJson as Prisma.InputJsonValue }
      })
      .catch(() => undefined);
    return visit ? toVisitRecord(visit) : undefined;
  }

  async updateVisitTokenHash(visitId: string, tokenHash: string): Promise<void> {
    await this.db.visit.update({
      where: { id: visitId },
      data: { visitTokenHash: tokenHash }
    });
  }
}

function toApiKeyRecord(apiKey: ApiKey): ApiKeyRecord {
  return {
    id: apiKey.id,
    workspaceId: apiKey.workspaceId,
    keyHash: apiKey.keyHash,
    scopes: apiKey.scopes,
    expiresAt: apiKey.expiresAt
  };
}
