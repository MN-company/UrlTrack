import { Queue, type ConnectionOptions, type JobsOptions } from "bullmq";
import IORedis from "ioredis";

export const QUEUE_NAMES = {
  enrichment: "enrichment",
  webhooks: "webhooks",
  notifications: "notifications",
  aiInsights: "ai-insights",
  cleanup: "cleanup",
  reports: "reports"
} as const;

export type QueueName = (typeof QUEUE_NAMES)[keyof typeof QUEUE_NAMES];

export function createRedisConnection(redisUrl = process.env.REDIS_URL ?? "redis://127.0.0.1:6379"): IORedis {
  return new IORedis(redisUrl, {
    maxRetriesPerRequest: null
  });
}

export function createQueue(name: QueueName, redisUrl?: string): Queue {
  return new Queue(name, {
    connection: createRedisConnection(redisUrl) as ConnectionOptions,
    defaultJobOptions: defaultJobOptions()
  });
}

function defaultJobOptions(): JobsOptions {
  return {
    attempts: 5,
    backoff: {
      type: "exponential",
      delay: 30_000
    },
    removeOnComplete: 1_000,
    removeOnFail: 5_000
  };
}
