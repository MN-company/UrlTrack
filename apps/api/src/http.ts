import type { FastifyReply } from "fastify";

import { type ApiErrorEnvelope, toApiEnvelope } from "@urltrack/shared";

export function sendData<T>(reply: FastifyReply, data: T, meta?: Parameters<typeof toApiEnvelope<T>>[1]) {
  return reply.type("application/json").send(toApiEnvelope(data, meta));
}

export function sendError(reply: FastifyReply, statusCode: number, code: string, message: string, details?: unknown) {
  const payload: ApiErrorEnvelope = {
    error: {
      code,
      message,
      ...(details === undefined ? {} : { details })
    }
  };
  return reply.status(statusCode).type("application/json").send(payload);
}
