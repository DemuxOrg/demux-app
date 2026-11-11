# Frontend image. Dev-oriented: the compose file bind-mounts ./frontend over /app and
# runs `next dev`, so only node_modules is baked in here. The compose anonymous volume at
# /app/node_modules keeps the image's copy from being shadowed by the host's.
FROM node:22-alpine

WORKDIR /app

# pnpm version matches the packageManager field in package.json.
RUN corepack enable && corepack prepare pnpm@11.25.0 --activate

# Dependencies first so this layer is cached independently of source changes.
COPY package.json pnpm-lock.yaml pnpm-workspace.yaml ./
RUN pnpm install --frozen-lockfile

COPY . .

EXPOSE 3000

# Bind 0.0.0.0 so the published port is reachable from the host.
CMD ["pnpm", "dev", "--hostname", "0.0.0.0", "--port", "3000"]
