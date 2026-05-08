# ── Build stage ───────────────────────────────────────────────────────────
FROM node:18-alpine AS builder

WORKDIR /app

# Install dependencies
COPY package.json package-lock.json* ./
RUN npm ci

# Copy source
COPY . .

# Build args for RUM (baked in at build time)
ARG NEXT_PUBLIC_DD_APP_ID=94797379-4fae-4278-8cb4-1832fb6f3860
ARG NEXT_PUBLIC_DD_CLIENT_TOKEN=pub90993195e58a0783b852841cfc9d1339
ARG NEXT_PUBLIC_DD_ENV=dev
ARG NEXT_PUBLIC_ODDS_ENGINE_URL=http://localhost:8001
ARG NEXT_PUBLIC_BET_SERVICE_URL=http://localhost:8002

ENV NEXT_PUBLIC_DD_APP_ID=$NEXT_PUBLIC_DD_APP_ID
ENV NEXT_PUBLIC_DD_CLIENT_TOKEN=$NEXT_PUBLIC_DD_CLIENT_TOKEN
ENV NEXT_PUBLIC_DD_ENV=$NEXT_PUBLIC_DD_ENV
ENV NEXT_PUBLIC_ODDS_ENGINE_URL=$NEXT_PUBLIC_ODDS_ENGINE_URL
ENV NEXT_PUBLIC_BET_SERVICE_URL=$NEXT_PUBLIC_BET_SERVICE_URL

RUN npm run build

# ── Runtime stage ─────────────────────────────────────────────────────────
FROM node:18-alpine AS runner

WORKDIR /app

ENV NODE_ENV=production

# Copy built output (standalone mode)
COPY --from=builder /app/.next/standalone ./
COPY --from=builder /app/.next/static ./.next/static
COPY --from=builder /app/public ./public

EXPOSE 3000

CMD ["node", "server.js"]
