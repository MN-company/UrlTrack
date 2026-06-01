FROM node:22-alpine AS deps

WORKDIR /app
RUN corepack enable

COPY package.json pnpm-workspace.yaml turbo.json tsconfig.base.json ./
COPY packages ./packages
COPY apps/dashboard ./apps/dashboard
COPY apps/api/package.json ./apps/api/package.json
RUN pnpm install --frozen-lockfile

FROM node:22-alpine AS runner

WORKDIR /app
ENV NODE_ENV=production
RUN corepack enable

COPY --from=deps /app ./
RUN pnpm --filter @urltrack/dashboard build

EXPOSE 3000

CMD ["pnpm", "--filter", "@urltrack/dashboard", "start"]
