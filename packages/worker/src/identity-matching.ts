import { createHash, createHmac } from "node:crypto";

import { clampScore } from "@urltrack/shared";

export type FingerprintSignals = {
  email?: string;
  canvasHash?: string;
  webglHash?: string;
  audioFingerprint?: string;
  thumbmarkHash?: string;
  webrtcIps?: string[];
  timezone?: string;
  language?: string;
  screen?: string;
  ip?: string;
  userAgent?: string;
  ispOrg?: string;
  isMobile?: boolean;
  isVpnOrDatacenter?: boolean;
};

export type IdentityVisitInput = FingerprintSignals & {
  workspaceId: string;
  visitId: string;
};

export type VisitorCandidate = FingerprintSignals & {
  visitorId: string;
};

export type IdentityMatchResult = {
  visitorId?: string;
  confidenceScore: number;
  matchReasons: string[];
  reviewSuggested: boolean;
  action: "match_confirmed" | "review_suggested" | "new_visitor";
};

function normalizeText(value: unknown): string | undefined {
  if (typeof value !== "string") {
    return undefined;
  }
  const normalized = value.trim().toLowerCase();
  return normalized || undefined;
}

function normalizeList(value: unknown): string[] | undefined {
  if (!Array.isArray(value)) {
    return undefined;
  }
  const normalized = value.map(normalizeText).filter((item): item is string => Boolean(item));
  return normalized.length > 0 ? normalized : undefined;
}

function readRecord(value: unknown): Record<string, unknown> {
  return value && typeof value === "object" && !Array.isArray(value) ? (value as Record<string, unknown>) : {};
}

function stringFromPaths(source: Record<string, unknown>, paths: string[][]): string | undefined {
  for (const path of paths) {
    let cursor: unknown = source;
    for (const segment of path) {
      cursor = readRecord(cursor)[segment];
    }
    const normalized = normalizeText(cursor);
    if (normalized) {
      return normalized;
    }
  }
  return undefined;
}

export function hashSignal(value: string, secret?: string): string {
  const normalized = value.trim().toLowerCase();
  if (secret) {
    return createHmac("sha256", secret).update(normalized).digest("hex");
  }
  return createHash("sha256").update(normalized).digest("hex");
}

export function extractSignals(rawFingerprint: unknown, base: Partial<FingerprintSignals> = {}): FingerprintSignals {
  const root = readRecord(rawFingerprint);
  const thumbmark = readRecord(root.thumbmark ?? root);
  const components = readRecord(thumbmark.components);
  const screen = readRecord(components.screen ?? thumbmark.screen);
  const webgl = readRecord(components.webgl ?? thumbmark.webgl);
  const canvas = readRecord(components.canvas ?? thumbmark.canvas);
  const audio = readRecord(components.audio ?? thumbmark.audio);
  const network = readRecord(components.network ?? thumbmark.network);

  return {
    ...base,
    email: normalizeText(base.email ?? root.email),
    canvasHash:
      base.canvasHash ??
      stringFromPaths(canvas, [["hash"], ["value"], ["canvas_hash"]]) ??
      stringFromPaths(thumbmark, [["canvasHash"], ["canvas_hash"]]),
    webglHash:
      base.webglHash ??
      stringFromPaths(webgl, [["hash"], ["rendererHash"], ["webgl_hash"]]) ??
      stringFromPaths(thumbmark, [["webglHash"], ["webgl_hash"]]),
    audioFingerprint:
      base.audioFingerprint ??
      stringFromPaths(audio, [["hash"], ["fingerprint"], ["audio_fp"]]) ??
      stringFromPaths(thumbmark, [["audioFingerprint"], ["audio_fingerprint"], ["audio_fp"]]),
    thumbmarkHash:
      base.thumbmarkHash ??
      stringFromPaths(thumbmark, [["hash"], ["fingerprint"], ["visitorId"], ["id"]]),
    webrtcIps: base.webrtcIps ?? normalizeList(network.webrtcIps ?? thumbmark.webrtcIps ?? root.webrtc_ips),
    timezone:
      base.timezone ??
      stringFromPaths(thumbmark, [["timezone"], ["timeZone"]]) ??
      stringFromPaths(screen, [["timezone"], ["timeZone"]]),
    language:
      base.language ??
      stringFromPaths(thumbmark, [["language"], ["locale"]]) ??
      stringFromPaths(screen, [["language"], ["locale"]]),
    screen:
      base.screen ??
      stringFromPaths(screen, [["resolution"], ["size"], ["screen"]]) ??
      stringFromPaths(thumbmark, [["screen"], ["screenResolution"]]),
    ip: normalizeText(base.ip ?? root.ip),
    userAgent: normalizeText(base.userAgent ?? root.user_agent),
    ispOrg: normalizeText(base.ispOrg ?? root.isp_org ?? root.org),
    isMobile: base.isMobile,
    isVpnOrDatacenter: base.isVpnOrDatacenter
  };
}

function sameValue(first?: string, second?: string): boolean {
  return Boolean(first && second && first === second);
}

function overlaps(first?: string[], second?: string[]): boolean {
  if (!first?.length || !second?.length) {
    return false;
  }
  const secondSet = new Set(second);
  return first.some((value) => secondSet.has(value));
}

export function scoreCandidate(visit: FingerprintSignals, candidate: VisitorCandidate): Omit<IdentityMatchResult, "visitorId" | "action" | "reviewSuggested"> {
  let score = 0;
  const reasons: string[] = [];

  if (sameValue(visit.email, candidate.email)) {
    score += 40;
    reasons.push("same_email");
  }
  if (sameValue(visit.canvasHash, candidate.canvasHash) && sameValue(visit.webglHash, candidate.webglHash)) {
    score += 30;
    reasons.push("same_canvas_and_webgl");
  }
  if (sameValue(visit.audioFingerprint, candidate.audioFingerprint)) {
    score += 20;
    reasons.push("same_audio_fingerprint");
  }
  if (sameValue(visit.thumbmarkHash, candidate.thumbmarkHash)) {
    score += 15;
    reasons.push("same_thumbmark_hash");
  }
  if (overlaps(visit.webrtcIps, candidate.webrtcIps)) {
    score += 10;
    reasons.push("same_webrtc_ip");
  }
  if (
    sameValue(visit.timezone, candidate.timezone) &&
    sameValue(visit.language, candidate.language) &&
    sameValue(visit.screen, candidate.screen)
  ) {
    score += 8;
    reasons.push("same_timezone_language_screen");
  }
  if (sameValue(visit.ip, candidate.ip) && !visit.isMobile && !visit.isVpnOrDatacenter) {
    score += 5;
    reasons.push("same_stable_ip");
  }
  if (sameValue(visit.userAgent, candidate.userAgent)) {
    score += 3;
    reasons.push("same_user_agent");
  }
  if (sameValue(visit.ispOrg, candidate.ispOrg)) {
    score += 2;
    reasons.push("same_isp_org");
  }

  const hasStrongSignal = reasons.some((reason) =>
    ["same_email", "same_canvas_and_webgl", "same_audio_fingerprint", "same_thumbmark_hash"].includes(reason)
  );
  if (visit.isVpnOrDatacenter && !hasStrongSignal) {
    score -= 10;
    reasons.push("vpn_or_datacenter_penalty");
  }

  return {
    confidenceScore: clampScore(score),
    matchReasons: reasons
  };
}

export function matchIdentity(visit: IdentityVisitInput, candidates: VisitorCandidate[]): IdentityMatchResult {
  let bestCandidate: VisitorCandidate | undefined;
  let bestScore = 0;
  let bestReasons: string[] = [];

  for (const candidate of candidates) {
    const scored = scoreCandidate(visit, candidate);
    if (scored.confidenceScore > bestScore) {
      bestCandidate = candidate;
      bestScore = scored.confidenceScore;
      bestReasons = scored.matchReasons;
    }
  }

  if (bestCandidate && bestScore >= 60) {
    return {
      visitorId: bestCandidate.visitorId,
      confidenceScore: bestScore,
      matchReasons: bestReasons,
      reviewSuggested: false,
      action: "match_confirmed"
    };
  }

  if (bestCandidate && bestScore >= 30) {
    return {
      visitorId: bestCandidate.visitorId,
      confidenceScore: bestScore,
      matchReasons: bestReasons,
      reviewSuggested: true,
      action: "review_suggested"
    };
  }

  return {
    confidenceScore: bestScore,
    matchReasons: bestReasons,
    reviewSuggested: false,
    action: "new_visitor"
  };
}
