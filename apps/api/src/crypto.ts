import { createHash, createHmac, randomBytes, timingSafeEqual } from "node:crypto";

export function hashSecret(value: string): string {
  return createHash("sha256").update(value).digest("hex");
}

export function safeEqual(first: string, second: string): boolean {
  const firstBuffer = Buffer.from(first);
  const secondBuffer = Buffer.from(second);
  if (firstBuffer.length !== secondBuffer.length) {
    return false;
  }
  return timingSafeEqual(firstBuffer, secondBuffer);
}

export function createVisitToken(visitId: string, secret: string, ttlSeconds = 3600): string {
  const payload = {
    exp: Math.floor(Date.now() / 1000) + ttlSeconds,
    nonce: randomBytes(12).toString("hex"),
    visit_id: visitId
  };
  const body = Buffer.from(JSON.stringify(payload)).toString("base64url");
  const signature = createHmac("sha256", secret).update(body).digest("base64url");
  return `${body}.${signature}`;
}

export function verifyVisitToken(token: string, secret: string): { visitId: string } | undefined {
  try {
    const [body, signature] = token.split(".");
    if (!body || !signature) {
      return undefined;
    }

    const expected = createHmac("sha256", secret).update(body).digest("base64url");
    if (!safeEqual(signature, expected)) {
      return undefined;
    }

    const payload = JSON.parse(Buffer.from(body, "base64url").toString("utf8")) as {
      exp?: unknown;
      visit_id?: unknown;
    };
    if (typeof payload.exp !== "number" || payload.exp < Math.floor(Date.now() / 1000)) {
      return undefined;
    }
    if (typeof payload.visit_id !== "string") {
      return undefined;
    }

    return { visitId: payload.visit_id };
  } catch {
    return undefined;
  }
}
