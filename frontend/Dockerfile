# Frontend image.
#
# Targets:
#   dev  – `next dev`; compose bind-mounts ./frontend over /app and keeps the image's
#          node_modules alive with an anonymous volume.
#   prod – `next build` + `next start`. NEXT_PUBLIC_API_URL is inlined into the browser
#          bundle at build time, so pass it as a build arg (the public backend URL).
#          Login settings (AUTH_DATABASE_URL, BETTER_AUTH_*, SMTP_*) are read at runtime.

FROM node:22-alpine AS base
WORKDIR /app
ENV NEXT_TELEMETRY_DISABLED=1
# pnpm version matches the packageManager field in package.json.
RUN corepack enable && corepack prepare pnpm@11.25.0 --activate


FROM base AS deps
# Dependencies first so this layer is cached independently of source changes.
COPY package.json pnpm-lock.yaml pnpm-workspace.yaml ./
RUN pnpm install --frozen-lockfile


FROM deps AS dev
COPY . .
EXPOSE 3000
# Bind 0.0.0.0 so the published port is reachable from the host.
CMD ["pnpm", "dev", "--hostname", "0.0.0.0", "--port", "3000"]


FROM deps AS build
ARG NEXT_PUBLIC_API_URL=http://localhost:8000
ENV NEXT_PUBLIC_API_URL=$NEXT_PUBLIC_API_URL
COPY . .
# Build-time placeholder (the build stage is not shipped); the real secret comes from the
# runtime environment.
RUN BETTER_AUTH_SECRET=build-only-placeholder pnpm build


FROM node:22-alpine AS prod
WORKDIR /app
ENV NODE_ENV=production NEXT_TELEMETRY_DISABLED=1
COPY --from=build --chown=node:node /app/package.json ./
COPY --from=build --chown=node:node /app/node_modules ./node_modules
COPY --from=build --chown=node:node /app/public ./public
COPY --from=build --chown=node:node /app/.next ./.next
USER node
EXPOSE 3000
CMD ["node_modules/.bin/next", "start", "--hostname", "0.0.0.0", "--port", "3000"]
