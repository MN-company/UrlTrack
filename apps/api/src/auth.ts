import { createClient, type SupabaseClient } from "@supabase/supabase-js";
import type { FastifyReply, FastifyRequest } from "fastify";

import { hashSecret } from "./crypto";
import { sendError } from "./http";
import type { AuthenticatedPrincipal, UrlTrackRepository } from "./repositories/types";
import type { ApiConfig } from "./config";

declare module "fastify" {
  interface FastifyRequest {
    principal?: AuthenticatedPrincipal;
  }
}

export type AuthContext = {
  config: ApiConfig;
  repository: UrlTrackRepository;
  supabase?: SupabaseClient;
};

export function createAuthContext(config: ApiConfig, repository: UrlTrackRepository): AuthContext {
  const supabase =
    config.SUPABASE_URL && config.SUPABASE_ANON_KEY
      ? createClient(config.SUPABASE_URL, config.SUPABASE_ANON_KEY, {
          auth: { persistSession: false }
        })
      : undefined;

  return { config, repository, supabase };
}

export function requireAuth(context: AuthContext) {
  return async (request: FastifyRequest, reply: FastifyReply) => {
    const principal = await resolvePrincipal(request, context);
    if (!principal) {
      return sendError(reply, 401, "unauthorized", "A valid X-Api-Key or Supabase Bearer token is required.");
    }
    request.principal = principal;
  };
}

export async function resolvePrincipal(
  request: FastifyRequest,
  context: AuthContext
): Promise<AuthenticatedPrincipal | undefined> {
  const apiKeyHeader = request.headers["x-api-key"];
  const apiKey = Array.isArray(apiKeyHeader) ? apiKeyHeader[0] : apiKeyHeader;
  if (apiKey) {
    const record = await context.repository.findApiKeyByHash(hashSecret(apiKey));
    if (!record) {
      return undefined;
    }
    await context.repository.touchApiKey(record.id);
    return {
      apiKeyId: record.id,
      workspaceId: record.workspaceId,
      scopes: record.scopes
    };
  }

  const authorization = request.headers.authorization;
  const token = authorization?.startsWith("Bearer ") ? authorization.slice("Bearer ".length) : undefined;
  if (!token || !context.supabase) {
    return undefined;
  }

  const workspaceHeader = request.headers["x-workspace-id"];
  const workspaceId = Array.isArray(workspaceHeader) ? workspaceHeader[0] : workspaceHeader;
  if (!workspaceId) {
    return undefined;
  }

  const { data, error } = await context.supabase.auth.getUser(token);
  if (error || !data.user) {
    return undefined;
  }

  const isMember = await context.repository.isWorkspaceMember(workspaceId, data.user.id);
  if (!isMember) {
    return undefined;
  }

  return {
    userId: data.user.id,
    workspaceId,
    scopes: ["*"]
  };
}

export function requireWorkspace(request: FastifyRequest, bodyWorkspaceId?: string): string {
  const workspaceId = request.principal?.workspaceId;
  if (!workspaceId) {
    throw new Error("Missing authenticated workspace.");
  }
  if (bodyWorkspaceId && bodyWorkspaceId !== workspaceId) {
    throw new Error("Payload workspace_id does not match the authenticated workspace.");
  }
  return workspaceId;
}
