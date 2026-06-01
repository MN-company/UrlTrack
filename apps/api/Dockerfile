FROM node:22-alpine

WORKDIR /app

RUN corepack enable

COPY package.json pnpm-workspace.yaml turbo.json tsconfig.base.json ./
COPY packages ./packages
COPY apps/api ./apps/api
COPY apps/dashboard/package.json ./apps/dashboard/package.json

RUN pnpm install --frozen-lockfile

EXPOSE 8000

CMD ["pnpm", "--filter", "@urltrack/api", "start"]
