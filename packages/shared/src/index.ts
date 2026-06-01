import { z } from "zod";

export const WORKSPACE_ROLES = ["owner", "admin", "editor", "analyst", "viewer"] as const;
export const LINK_STATUSES = ["active", "paused", "archived"] as const;
export const CAMPAIGN_STATUSES = ["draft", "active", "paused", "completed", "archived"] as const;
export const SOURCE_TYPES = ["link", "qr"] as const;
export const WEBHOOK_EVENTS = [
  "visit.created",
  "lead.created",
  "lead.updated",
  "lead.score_changed",
  "qr.scanned",
  "suspicious.detected",
  "link.blocked",
  "link.expired",
  "conversion.created",
  "visitor.identified"
] as const;

export type WorkspaceRole = (typeof WORKSPACE_ROLES)[number];
export type LinkStatus = (typeof LINK_STATUSES)[number];
export type CampaignStatus = (typeof CAMPAIGN_STATUSES)[number];
export type SourceType = (typeof SOURCE_TYPES)[number];
export type WebhookEvent = (typeof WEBHOOK_EVENTS)[number];

export type ApiEnvelope<T> = {
  data: T;
  meta?: {
    page?: number;
    per_page?: number;
    total?: number;
  };
};

export type ApiErrorEnvelope = {
  error: {
    code: string;
    message: string;
    details?: unknown;
  };
};

export type TrafficQualitySettings = {
  vpn_penalty: number;
  bot_penalty: number;
  datacenter_penalty: number;
  returning_visitor_bonus: number;
  email_captured_bonus: number;
};

export type LeadScoreSettings = {
  high_confidence_identity: number;
  email_verified: number;
  multiple_link_visits: number;
  high_engagement_dwell: number;
};

export type WorkspaceScoringSettings = {
  scoring: {
    traffic_quality: TrafficQualitySettings;
    lead_score: LeadScoreSettings;
  };
};

export const defaultWorkspaceSettings: WorkspaceScoringSettings = {
  scoring: {
    traffic_quality: {
      vpn_penalty: -30,
      bot_penalty: -50,
      datacenter_penalty: -20,
      returning_visitor_bonus: 10,
      email_captured_bonus: 20
    },
    lead_score: {
      high_confidence_identity: 40,
      email_verified: 30,
      multiple_link_visits: 15,
      high_engagement_dwell: 10
    }
  }
};

export const slugSchema = z
  .string()
  .trim()
  .min(3)
  .max(80)
  .regex(/^[A-Za-z0-9][A-Za-z0-9_-]*$/, "Slug must be alphanumeric with optional '-' or '_'.");

export const idSchema = z.string().uuid();
export const workspaceIdSchema = idSchema;

export const destinationUrlSchema = z
  .string()
  .trim()
  .min(1)
  .transform((value, ctx) => {
    try {
      return normalizeDestinationUrl(value);
    } catch (error) {
      ctx.addIssue({
        code: z.ZodIssueCode.custom,
        message: error instanceof Error ? error.message : "Invalid destination URL."
      });
      return z.NEVER;
    }
  });

export const paginationSchema = z.object({
  page: z.coerce.number().int().min(1).default(1),
  per_page: z.coerce.number().int().min(1).max(100).default(20)
});

export const accessControlConfigSchema = z
  .object({
    expires_at: z.string().datetime().optional(),
    max_clicks: z.number().int().positive().optional(),
    geo_allowlist: z.array(z.string().length(2).transform((value) => value.toUpperCase())).optional(),
    time_window: z
      .object({
        timezone: z.string().min(1).default("UTC"),
        start_hour: z.number().int().min(0).max(23),
        end_hour: z.number().int().min(0).max(23)
      })
      .optional(),
    device_types: z.array(z.enum(["mobile", "desktop", "tablet"])).optional(),
    password_gate: z.boolean().optional(),
    email_gate: z.boolean().optional(),
    captcha_gate: z.boolean().optional()
  })
  .passthrough()
  .default({});

export const routingConfigSchema = z
  .object({
    safe_url: destinationUrlSchema.optional(),
    ios_url: destinationUrlSchema.optional(),
    android_url: destinationUrlSchema.optional()
  })
  .passthrough()
  .default({});

export const notificationConfigSchema = z
  .object({
    telegram_enabled: z.boolean().optional(),
    email_enabled: z.boolean().optional(),
    webhook_events: z.array(z.enum(WEBHOOK_EVENTS)).optional()
  })
  .passthrough()
  .default({});

export const qrConfigSchema = z
  .object({
    foreground: z.string().regex(/^#[0-9A-Fa-f]{6}$/).default("#00C853"),
    background: z.string().regex(/^#[0-9A-Fa-f]{6}$/).default("#0A0A0A"),
    logo_path: z.string().optional(),
    format: z.enum(["png", "svg"]).default("png"),
    size: z.union([z.enum(["small", "medium", "large"]), z.number().int().min(128).max(4096)]).default("medium"),
    error_correction_level: z.enum(["L", "M", "Q", "H"]).default("M")
  })
  .passthrough()
  .default({});

export const flowConfigSchema = z
  .object({
    nodes: z.array(z.record(z.unknown())).default([]),
    edges: z.array(z.record(z.unknown())).default([])
  })
  .passthrough()
  .default({ nodes: [], edges: [] });

export const createLinkSchema = z.object({
  workspace_id: workspaceIdSchema,
  campaign_id: idSchema.nullish(),
  domain_id: idSchema.nullish(),
  slug: slugSchema,
  destination_url: destinationUrlSchema,
  access_control_config: accessControlConfigSchema.optional(),
  routing_config: routingConfigSchema.optional(),
  notification_config: notificationConfigSchema.optional(),
  qr_config: qrConfigSchema.optional(),
  flow_config: flowConfigSchema.optional(),
  status: z.enum(LINK_STATUSES).default("active")
});

export const updateLinkSchema = createLinkSchema
  .omit({ workspace_id: true, slug: true })
  .partial()
  .extend({
    slug: slugSchema.optional()
  });

export const createCampaignSchema = z.object({
  workspace_id: workspaceIdSchema,
  name: z.string().trim().min(1).max(160),
  description: z.string().trim().max(2000).optional(),
  status: z.enum(CAMPAIGN_STATUSES).default("draft"),
  goal: z.string().trim().max(500).optional()
});

export const createWebhookSchema = z.object({
  workspace_id: workspaceIdSchema,
  url: destinationUrlSchema,
  name: z.string().trim().min(1).max(120),
  events: z.array(z.enum(WEBHOOK_EVENTS)).min(1),
  enabled: z.boolean().default(true)
});

export const fingerprintPayloadSchema = z.object({
  visit_token: z.string().min(20).max(500),
  thumbmark: z.record(z.unknown())
});

export const workspaceSettingsSchema = z.object({
  scoring: z.object({
    traffic_quality: z.object({
      vpn_penalty: z.number().min(-100).max(0),
      bot_penalty: z.number().min(-100).max(0),
      datacenter_penalty: z.number().min(-100).max(0),
      returning_visitor_bonus: z.number().min(0).max(100),
      email_captured_bonus: z.number().min(0).max(100)
    }),
    lead_score: z.object({
      high_confidence_identity: z.number().min(0).max(100),
      email_verified: z.number().min(0).max(100),
      multiple_link_visits: z.number().min(0).max(100),
      high_engagement_dwell: z.number().min(0).max(100)
    })
  })
});

export function normalizeDestinationUrl(rawUrl: string): string {
  const trimmed = rawUrl.trim();
  if (!trimmed) {
    throw new Error("URL is required.");
  }

  const candidate = /^[a-zA-Z][a-zA-Z\d+\-.]*:/.test(trimmed) ? trimmed : `https://${trimmed}`;
  const parsed = new URL(candidate);

  if (!["http:", "https:"].includes(parsed.protocol)) {
    throw new Error("Only http/https URLs are allowed.");
  }
  if (!parsed.hostname) {
    throw new Error("URL must include a valid host.");
  }

  parsed.hash = "";
  return parsed.toString();
}

export function clampScore(score: number): number {
  return Math.max(0, Math.min(100, Math.round(score)));
}

export function escapeHtml(value: string): string {
  return value.replace(/[&<>"']/g, (char) => {
    switch (char) {
      case "&":
        return "&amp;";
      case "<":
        return "&lt;";
      case ">":
        return "&gt;";
      case '"':
        return "&quot;";
      default:
        return "&#39;";
    }
  });
}

export function toApiEnvelope<T>(
  data: T,
  meta?: ApiEnvelope<T>["meta"]
): ApiEnvelope<T> {
  return meta ? { data, meta } : { data };
}
