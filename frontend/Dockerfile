# Stage 1: Build the SvelteKit application
FROM node:20-alpine AS build

ARG VITE_API_BASE_URL
WORKDIR /app

# Install dependencies
COPY package.json package-lock.json ./
RUN npm ci

# Copy source and build
COPY . .
RUN npm run build

# Stage 2: Production image
FROM node:20-alpine

WORKDIR /app

# Copy production artifacts
COPY --from=build /app/build ./build
COPY --from=build /app/package.json ./package.json
COPY --from=build /app/node_modules ./node_modules

ENV NODE_ENV=production
EXPOSE 3000

CMD ["node", "build"]
