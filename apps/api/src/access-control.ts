import type { FastifyRequest } from "fastify";
import { UAParser } from "ua-parser-js";

import type { LinkRecord } from "./repositories/types";

type AccessDecision =
  | { allowed: true; deviceType: "mobile" | "tablet" | "desktop"; destinationUrl: string }
  | { allowed: false; statusCode: number; reason: string; eventType: string };

function stringArray(value: unknown): string[] {
  return Array.isArray(value) ? value.filter((item): item is string => typeof item === "string") : [];
}

function detectDeviceType(userAgent: string): "mobile" | "tablet" | "desktop" {
  const parser = new UAParser(userAgent);
  const type = parser.getDevice().type;
  if (type === "mobile") return "mobile";
  if (type === "tablet") return "tablet";
  return "desktop";
}

function requestCountry(request: FastifyRequest): string | undefined {
  const header =
    request.headers["cf-ipcountry"] ??
    request.headers["x-vercel-ip-country"] ??
    request.headers["x-urltrack-country"];
  const value = Array.isArray(header) ? header[0] : header;
  return typeof value === "string" && value.length === 2 ? value.toUpperCase() : undefined;
}

function isWithinTimeWindow(config: Record<string, unknown>): boolean {
  const window = config.time_window;
  if (!window || typeof window !== "object" || Array.isArray(window)) {
    return true;
  }
  const record = window as Record<string, unknown>;
  const start = typeof record.start_hour === "number" ? record.start_hour : undefined;
  const end = typeof record.end_hour === "number" ? record.end_hour : undefined;
  if (start === undefined || end === undefined) {
    return true;
  }
  const hour = new Date().getUTCHours();
  return start <= end ? hour >= start && hour < end : hour >= start || hour < end;
}

export function evaluateAccessControl(link: LinkRecord, request: FastifyRequest): AccessDecision {
  const config = link.accessControlConfig;
  const routing = link.routingConfig;
  const userAgent = request.headers["user-agent"] ?? "";
  const userAgentString = Array.isArray(userAgent) ? userAgent.join(" ") : userAgent;
  const deviceType = detectDeviceType(userAgentString);

  if (link.status !== "active") {
    return { allowed: false, statusCode: 404, reason: "Link is not active.", eventType: "link.blocked" };
  }

  const expiresAt = typeof config.expires_at === "string" ? new Date(config.expires_at) : undefined;
  if (expiresAt && Number.isFinite(expiresAt.getTime()) && expiresAt < new Date()) {
    return { allowed: false, statusCode: 410, reason: "Link expired.", eventType: "link.expired" };
  }

  const maxClicks = typeof config.max_clicks === "number" ? config.max_clicks : undefined;
  if (maxClicks !== undefined && link.clickCount >= maxClicks) {
    return { allowed: false, statusCode: 410, reason: "Link click limit reached.", eventType: "link.expired" };
  }

  const allowlist = stringArray(config.geo_allowlist).map((country) => country.toUpperCase());
  if (allowlist.length > 0) {
    const country = requestCountry(request);
    if (!country || !allowlist.includes(country)) {
      return { allowed: false, statusCode: 403, reason: "Country not allowed.", eventType: "link.blocked" };
    }
  }

  const allowedDevices = stringArray(config.device_types);
  if (allowedDevices.length > 0 && !allowedDevices.includes(deviceType)) {
    return { allowed: false, statusCode: 403, reason: "Device type not allowed.", eventType: "link.blocked" };
  }

  if (!isWithinTimeWindow(config)) {
    return { allowed: false, statusCode: 403, reason: "Link is outside the allowed time window.", eventType: "link.blocked" };
  }

  for (const gate of ["password_gate", "email_gate", "captcha_gate"]) {
    if (config[gate] === true) {
      return { allowed: false, statusCode: 401, reason: `${gate.replace("_", " ")} required.`, eventType: "link.blocked" };
    }
  }

  let destinationUrl = link.destinationUrl;
  if (deviceType === "mobile" && typeof routing.ios_url === "string" && /iPhone|iPad|iPod/i.test(userAgentString)) {
    destinationUrl = routing.ios_url;
  } else if (deviceType === "mobile" && typeof routing.android_url === "string" && /Android/i.test(userAgentString)) {
    destinationUrl = routing.android_url;
  }

  return { allowed: true, deviceType, destinationUrl };
}
