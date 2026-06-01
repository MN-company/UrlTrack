import type { LinkStatus, SourceType, WebhookEvent } from "@urltrack/shared";

export type JsonRecord = Record<string, unknown>;

export type ListResult<T> = {
  items: T[];
  total: number;
};

export class RepositoryConflictError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "RepositoryConflictError";
  }
}

export type ApiKeyRecord = {
  id: string;
  workspaceId: string;
  keyHash: string;
  scopes: string[];
  expiresAt: Date | null;
};

export type AuthenticatedPrincipal = {
  workspaceId: string;
  userId?: string;
  apiKeyId?: string;
  scopes: string[];
};

export type LinkRecord = {
  id: string;
  workspaceId: string;
  campaignId: string | null;
  domainId: string | null;
  slug: string;
  destinationUrl: string;
  accessControlConfig: JsonRecord;
  routingConfig: JsonRecord;
  notificationConfig: JsonRecord;
  qrConfig: JsonRecord;
  flowConfig: JsonRecord;
  status: LinkStatus;
  createdBy: string;
  clickCount: number;
  archivedAt: Date | null;
  createdAt: Date;
  updatedAt: Date;
};

export type LinkCreateInput = Omit<LinkRecord, "id" | "clickCount" | "archivedAt" | "createdAt" | "updatedAt">;
export type LinkUpdateInput = Partial<Omit<LinkCreateInput, "workspaceId" | "createdBy">>;

export type VisitRecord = {
  id: string;
  workspaceId: string;
  linkId: string;
  visitorId: string | null;
  sourceType: SourceType;
  trafficQualityScore: number;
  identityConfidenceScore: number;
  eventType: string;
  rawFingerprintJson: JsonRecord;
  ip: string | null;
  userAgent: string | null;
  referrer: string | null;
  countryCode: string | null;
  deviceType: string | null;
  isVpn: boolean;
  isBot: boolean;
  isDatacenter: boolean;
  visitTokenHash: string | null;
  matchReasons: string[];
  reviewSuggested: boolean;
  createdAt: Date;
  updatedAt: Date;
};

export type VisitCreateInput = Pick<
  VisitRecord,
  "workspaceId" | "linkId" | "sourceType" | "eventType" | "ip" | "userAgent" | "referrer" | "countryCode" | "deviceType"
> &
  Partial<Pick<VisitRecord, "isBot" | "isVpn" | "isDatacenter" | "visitTokenHash">>;

export type CampaignRecord = {
  id: string;
  workspaceId: string;
  name: string;
  description: string | null;
  status: string;
  goal: string | null;
  createdAt: Date;
  updatedAt: Date;
};

export type WebhookEndpointRecord = {
  id: string;
  workspaceId: string;
  url: string;
  secret: string;
  name: string;
  enabled: boolean;
  events: string[];
  createdAt: Date;
  updatedAt: Date;
};

export type VisitorRecord = {
  id: string;
  workspaceId: string;
  primaryEmail: string | null;
  primaryIp: string | null;
  primaryCanvasHash: string | null;
  primaryFingerprintHash: string | null;
  firstSeen: Date;
  lastSeen: Date;
  totalVisits: number;
  confidenceScore: number;
  trafficQualityAverage: number;
  attributesJson: JsonRecord;
};

export type LeadRecord = {
  id: string;
  workspaceId: string;
  visitorId: string | null;
  score: number;
  confidenceScore: number;
  tags: string[];
  lifecycleStage: string;
  consentStatus: string;
  customFieldsJson: JsonRecord;
  createdAt: Date;
  updatedAt: Date;
};

export type LinkStats = {
  total_clicks: number;
  unique_visitors: number;
  suspicious_clicks: number;
  qr_clicks: number;
};

export type CampaignStats = {
  links: number;
  visits: number;
  leads: number;
};

export interface UrlTrackRepository {
  archiveLink(workspaceId: string, id: string): Promise<LinkRecord | undefined>;
  createCampaign(input: Omit<CampaignRecord, "id" | "createdAt" | "updatedAt">): Promise<CampaignRecord>;
  createLink(input: LinkCreateInput): Promise<LinkRecord>;
  createVisit(input: VisitCreateInput): Promise<VisitRecord>;
  createWebhook(input: Omit<WebhookEndpointRecord, "id" | "createdAt" | "updatedAt">): Promise<WebhookEndpointRecord>;
  findApiKeyByHash(keyHash: string): Promise<ApiKeyRecord | undefined>;
  findLinkBySlug(slug: string): Promise<LinkRecord | undefined>;
  getCampaignStats(workspaceId: string, campaignId: string): Promise<CampaignStats>;
  getLink(workspaceId: string, id: string): Promise<LinkRecord | undefined>;
  getLinkStats(workspaceId: string, id: string): Promise<LinkStats>;
  isWorkspaceMember(workspaceId: string, userId: string): Promise<boolean>;
  listCampaigns(workspaceId: string): Promise<CampaignRecord[]>;
  listLeads(workspaceId: string, page: number, perPage: number): Promise<ListResult<LeadRecord>>;
  listLinks(workspaceId: string, page: number, perPage: number): Promise<ListResult<LinkRecord>>;
  listVisitors(workspaceId: string, page: number, perPage: number): Promise<ListResult<VisitorRecord>>;
  listVisits(workspaceId: string, linkId: string, page: number, perPage: number): Promise<ListResult<VisitRecord>>;
  listWebhooks(workspaceId: string): Promise<WebhookEndpointRecord[]>;
  touchApiKey(id: string): Promise<void>;
  updateLink(workspaceId: string, id: string, input: LinkUpdateInput): Promise<LinkRecord | undefined>;
  updateVisitFingerprint(visitId: string, rawFingerprintJson: JsonRecord): Promise<VisitRecord | undefined>;
  updateVisitTokenHash(visitId: string, tokenHash: string): Promise<void>;
}
