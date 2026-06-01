import { createHmac, randomUUID } from "node:crypto";

export const WEBHOOK_RETRY_DELAYS_MS = [
  30_000,
  5 * 60_000,
  30 * 60_000,
  2 * 60 * 60_000,
  24 * 60 * 60_000
] as const;

export type WebhookDeliveryInput = {
  deliveryId?: string;
  endpointUrl: string;
  secret: string;
  eventType: string;
  payload: unknown;
  attempt: number;
};

export type WebhookDeliveryResult =
  | { status: "delivered"; responseCode: number }
  | { status: "retrying"; responseCode?: number; nextRetryAt: Date; attempts: number }
  | { status: "failed"; responseCode?: number; disabledEndpoint: boolean; attempts: number };

export function serializeWebhookPayload(eventType: string, payload: unknown): string {
  return JSON.stringify({
    id: randomUUID(),
    event: eventType,
    created_at: new Date().toISOString(),
    data: payload
  });
}

export function signWebhookPayload(secret: string, body: string): string {
  const signature = createHmac("sha256", secret).update(body).digest("hex");
  return `sha256=${signature}`;
}

export function retryDelayForAttempt(attempt: number): number | undefined {
  return WEBHOOK_RETRY_DELAYS_MS[attempt - 1];
}

export async function deliverWebhook(input: WebhookDeliveryInput): Promise<WebhookDeliveryResult> {
  const body = serializeWebhookPayload(input.eventType, input.payload);
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 8_000);

  try {
    const response = await fetch(input.endpointUrl, {
      method: "POST",
      body,
      headers: {
        "content-type": "application/json",
        "user-agent": "UrlTrack-Webhook/2.0",
        "x-urltrack-event": input.eventType,
        "x-urltrack-delivery": input.deliveryId ?? randomUUID(),
        "x-urltrack-signature": signWebhookPayload(input.secret, body)
      },
      signal: controller.signal
    });

    if (response.ok) {
      return { status: "delivered", responseCode: response.status };
    }

    return buildRetryResult(input.attempt + 1, response.status);
  } catch {
    return buildRetryResult(input.attempt + 1);
  } finally {
    clearTimeout(timeout);
  }
}

function buildRetryResult(attempts: number, responseCode?: number): WebhookDeliveryResult {
  const delay = retryDelayForAttempt(attempts);
  if (delay === undefined) {
    return {
      status: "failed",
      responseCode,
      disabledEndpoint: true,
      attempts
    };
  }

  return {
    status: "retrying",
    responseCode,
    attempts,
    nextRetryAt: new Date(Date.now() + delay)
  };
}
