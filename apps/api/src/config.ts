import { z } from "zod";

const devVisitSecret = "dev-only-urltrack-visit-token-secret-change-before-production";

const envSchema = z.object({
  API_CACHE_TTL_SECONDS: z.coerce.number().int().min(1).default(60),
  API_HOST: z.string().default("0.0.0.0"),
  API_PORT: z.coerce.number().int().min(1).max(65_535).default(8000),
  API_PUBLIC_URL: z.string().url().default("http://localhost:8000"),
  API_RATE_LIMIT_MAX: z.coerce.number().int().min(1).default(120),
  API_TRUST_PROXY: z
    .string()
    .optional()
    .transform((value) => value === "true"),
  BASE_DOMAIN: z.string().url().default("http://localhost:3000"),
  NODE_ENV: z.string().default("development"),
  REDIS_URL: z.string().optional(),
  SUPABASE_ANON_KEY: z.string().optional(),
  SUPABASE_SERVICE_ROLE_KEY: z.string().optional(),
  SUPABASE_URL: z.string().url().optional(),
  URLTRACK_REPOSITORY: z.enum(["prisma", "memory"]).default("prisma"),
  VISIT_TOKEN_SECRET: z.string().min(32).optional()
});

export type ApiConfig = z.infer<typeof envSchema> & {
  visitTokenSecret: string;
};

export function loadConfig(env: NodeJS.ProcessEnv = process.env): ApiConfig {
  const parsed = envSchema.parse(env);
  const visitTokenSecret = parsed.VISIT_TOKEN_SECRET ?? (parsed.NODE_ENV === "production" ? "" : devVisitSecret);

  if (!visitTokenSecret) {
    throw new Error("VISIT_TOKEN_SECRET must be set in production.");
  }

  return {
    ...parsed,
    visitTokenSecret
  };
}
