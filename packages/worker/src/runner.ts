import { Worker, type ConnectionOptions } from "bullmq";
import pino from "pino";

import { prisma } from "@urltrack/db";

import { createRedisConnection, QUEUE_NAMES } from "./queues";

const logger = pino({ name: "urltrack-worker" });
const connection = createRedisConnection();

const enrichmentWorker = new Worker(
  QUEUE_NAMES.enrichment,
  async (job) => {
    logger.info({ jobId: job.id, data: job.data }, "processing enrichment job");
    const visitId = typeof job.data === "object" && job.data ? (job.data as { visitId?: string }).visitId : undefined;
    if (!visitId) {
      return;
    }
    await prisma.visit.update({
      where: { id: visitId },
      data: { updatedAt: new Date() }
    });
  },
  { connection: connection as ConnectionOptions }
);

const shutdown = async () => {
  await enrichmentWorker.close();
  await connection.quit();
  await prisma.$disconnect();
};

process.on("SIGINT", () => void shutdown().then(() => process.exit(0)));
process.on("SIGTERM", () => void shutdown().then(() => process.exit(0)));

logger.info("UrlTrack worker started");
