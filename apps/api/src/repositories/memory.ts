import { randomUUID } from "node:crypto";

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
import { RepositoryConflictError } from "./types";

const now = () => new Date();

function paginate<T>(items: T[], page: number, perPage: number): ListResult<T> {
  const start = (page - 1) * perPage;
  return {
    items: items.slice(start, start + perPage),
    total: items.length
  };
}

export class InMemoryRepository implements UrlTrackRepository {
  readonly apiKeys = new Map<string, ApiKeyRecord>();
  readonly campaigns = new Map<string, CampaignRecord>();
  readonly links = new Map<string, LinkRecord>();
  readonly visits = new Map<string, VisitRecord>();
  readonly visitors = new Map<string, VisitorRecord>();
  readonly leads = new Map<string, LeadRecord>();
  readonly webhooks = new Map<string, WebhookEndpointRecord>();
  readonly workspaceMembers = new Map<string, Set<string>>();

  seedApiKey(record: ApiKeyRecord): void {
    this.apiKeys.set(record.keyHash, record);
  }

  seedWorkspaceMember(workspaceId: string, userId: string): void {
    const members = this.workspaceMembers.get(workspaceId) ?? new Set<string>();
    members.add(userId);
    this.workspaceMembers.set(workspaceId, members);
  }

  async archiveLink(workspaceId: string, id: string): Promise<LinkRecord | undefined> {
    const link = await this.getLink(workspaceId, id);
    if (!link) {
      return undefined;
    }
    const archived = { ...link, status: "archived" as const, archivedAt: now(), updatedAt: now() };
    this.links.set(id, archived);
    return archived;
  }

  async createCampaign(input: Omit<CampaignRecord, "id" | "createdAt" | "updatedAt">): Promise<CampaignRecord> {
    const campaign: CampaignRecord = {
      ...input,
      id: randomUUID(),
      createdAt: now(),
      updatedAt: now()
    };
    this.campaigns.set(campaign.id, campaign);
    return campaign;
  }

  async createLink(input: LinkCreateInput): Promise<LinkRecord> {
    const duplicate = [...this.links.values()].find(
      (link) => link.workspaceId === input.workspaceId && link.slug === input.slug && link.archivedAt === null
    );
    if (duplicate) {
      throw new RepositoryConflictError(`Slug '${input.slug}' already exists in this workspace.`);
    }

    const link: LinkRecord = {
      ...input,
      id: randomUUID(),
      clickCount: 0,
      archivedAt: null,
      createdAt: now(),
      updatedAt: now()
    };
    this.links.set(link.id, link);
    return link;
  }

  async createVisit(input: VisitCreateInput): Promise<VisitRecord> {
    const visit: VisitRecord = {
      ...input,
      id: randomUUID(),
      visitorId: null,
      trafficQualityScore: 100,
      identityConfidenceScore: 0,
      rawFingerprintJson: {},
      isBot: input.isBot ?? false,
      isVpn: input.isVpn ?? false,
      isDatacenter: input.isDatacenter ?? false,
      visitTokenHash: input.visitTokenHash ?? null,
      matchReasons: [],
      reviewSuggested: false,
      createdAt: now(),
      updatedAt: now()
    };
    this.visits.set(visit.id, visit);

    const link = this.links.get(input.linkId);
    if (link) {
      this.links.set(link.id, { ...link, clickCount: link.clickCount + 1, updatedAt: now() });
    }

    return visit;
  }

  async createWebhook(input: Omit<WebhookEndpointRecord, "id" | "createdAt" | "updatedAt">): Promise<WebhookEndpointRecord> {
    const webhook: WebhookEndpointRecord = {
      ...input,
      id: randomUUID(),
      createdAt: now(),
      updatedAt: now()
    };
    this.webhooks.set(webhook.id, webhook);
    return webhook;
  }

  async findApiKeyByHash(keyHash: string): Promise<ApiKeyRecord | undefined> {
    const record = this.apiKeys.get(keyHash);
    if (!record || (record.expiresAt && record.expiresAt < now())) {
      return undefined;
    }
    return record;
  }

  async findLinkBySlug(slug: string): Promise<LinkRecord | undefined> {
    return [...this.links.values()].find((link) => link.slug === slug && link.status !== "archived");
  }

  async getCampaignStats(workspaceId: string, campaignId: string): Promise<CampaignStats> {
    const links = [...this.links.values()].filter((link) => link.workspaceId === workspaceId && link.campaignId === campaignId);
    const linkIds = new Set(links.map((link) => link.id));
    const visits = [...this.visits.values()].filter((visit) => linkIds.has(visit.linkId));
    const leads = [...this.leads.values()].filter((lead) => lead.workspaceId === workspaceId).length;
    return { links: links.length, visits: visits.length, leads };
  }

  async getLink(workspaceId: string, id: string): Promise<LinkRecord | undefined> {
    const link = this.links.get(id);
    return link?.workspaceId === workspaceId ? link : undefined;
  }

  async getLinkStats(workspaceId: string, id: string): Promise<LinkStats> {
    const visits = [...this.visits.values()].filter((visit) => visit.workspaceId === workspaceId && visit.linkId === id);
    return {
      total_clicks: visits.length,
      unique_visitors: new Set(visits.map((visit) => visit.visitorId ?? visit.id)).size,
      suspicious_clicks: visits.filter((visit) => visit.isBot || visit.isVpn || visit.isDatacenter).length,
      qr_clicks: visits.filter((visit) => visit.sourceType === "qr").length
    };
  }

  async isWorkspaceMember(workspaceId: string, userId: string): Promise<boolean> {
    return this.workspaceMembers.get(workspaceId)?.has(userId) ?? false;
  }

  async listCampaigns(workspaceId: string): Promise<CampaignRecord[]> {
    return [...this.campaigns.values()].filter((campaign) => campaign.workspaceId === workspaceId);
  }

  async listLeads(workspaceId: string, page: number, perPage: number): Promise<ListResult<LeadRecord>> {
    return paginate(
      [...this.leads.values()].filter((lead) => lead.workspaceId === workspaceId),
      page,
      perPage
    );
  }

  async listLinks(workspaceId: string, page: number, perPage: number): Promise<ListResult<LinkRecord>> {
    return paginate(
      [...this.links.values()].filter((link) => link.workspaceId === workspaceId && link.archivedAt === null),
      page,
      perPage
    );
  }

  async listVisitors(workspaceId: string, page: number, perPage: number): Promise<ListResult<VisitorRecord>> {
    return paginate(
      [...this.visitors.values()].filter((visitor) => visitor.workspaceId === workspaceId),
      page,
      perPage
    );
  }

  async listVisits(workspaceId: string, linkId: string, page: number, perPage: number): Promise<ListResult<VisitRecord>> {
    return paginate(
      [...this.visits.values()].filter((visit) => visit.workspaceId === workspaceId && visit.linkId === linkId),
      page,
      perPage
    );
  }

  async listWebhooks(workspaceId: string): Promise<WebhookEndpointRecord[]> {
    return [...this.webhooks.values()].filter((webhook) => webhook.workspaceId === workspaceId);
  }

  async touchApiKey(_id: string): Promise<void> {
    return;
  }

  async updateLink(workspaceId: string, id: string, input: LinkUpdateInput): Promise<LinkRecord | undefined> {
    const existing = await this.getLink(workspaceId, id);
    if (!existing) {
      return undefined;
    }
    const updated = {
      ...existing,
      ...input,
      updatedAt: now()
    };
    this.links.set(id, updated);
    return updated;
  }

  async updateVisitFingerprint(visitId: string, rawFingerprintJson: JsonRecord): Promise<VisitRecord | undefined> {
    const existing = this.visits.get(visitId);
    if (!existing) {
      return undefined;
    }
    const updated = {
      ...existing,
      rawFingerprintJson,
      updatedAt: now()
    };
    this.visits.set(visitId, updated);
    return updated;
  }

  async updateVisitTokenHash(visitId: string, tokenHash: string): Promise<void> {
    const existing = this.visits.get(visitId);
    if (existing) {
      this.visits.set(visitId, { ...existing, visitTokenHash: tokenHash, updatedAt: now() });
    }
  }
}
