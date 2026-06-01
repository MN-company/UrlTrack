import { Queue } from "bullmq";
import IORedis from "ioredis";

import { QUEUE_NAMES } from "@urltrack/worker";

export type EnqueueEnrichment = (visitId: string) => Promise<void>;

export function createEnrichmentEnqueuer(redisUrl?: string): EnqueueEnrichment {
  if (!redisUrl) {
    return async () => undefined;
  }

  const connection = new IORedis(redisUrl, { maxRetriesPerRequest: null });
  const queue = new Queue(QUEUE_NAMES.enrichment, { connection });

  return async (visitId: string) => {
    await queue.add("enrichVisit", { visitId });
  };
}
