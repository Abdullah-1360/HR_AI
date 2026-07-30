# Stage 1: Build the Next.js app
FROM node:20-alpine AS builder
WORKDIR /app

# Install dependencies first (better Docker caching)
COPY package.json package-lock.json ./
RUN npm ci

# Copy source files
COPY . .

# Set env during build time
ENV NEXT_TELEMETRY_DISABLED=1
ENV NODE_ENV=production
ARG NEXT_PUBLIC_API_URL=http://localhost:8000
ENV NEXT_PUBLIC_API_URL=$NEXT_PUBLIC_API_URL

# Build Next.js
RUN npm run build

# Stage 2: Final minimal runner image
FROM node:20-alpine AS runner
WORKDIR /app

ENV NODE_ENV=production
ENV PORT=3000
ENV HOSTNAME="0.0.0.0"

# Copy Next.js standalone folder and assets
COPY --from=builder /app/public ./public
COPY --from=builder /app/.next/standalone ./
COPY --from=builder /app/.next/static ./.next/static

EXPOSE 3000

CMD ["node", "server.js"]
