# Build stage
FROM golang:1.24-alpine AS builder

WORKDIR /app

# Download dependencies first for caching
COPY go.mod go.sum ./
RUN go mod download

# Copy source code and build statically linked binary
COPY . .
RUN CGO_ENABLED=0 GOOS=linux go build -ldflags="-s -w" -o indicator-service .

# Run stage
FROM alpine:3.21

WORKDIR /app

# Install certificates, timezone data, and wget for healthchecks
RUN apk --no-cache add ca-certificates tzdata wget && \
    addgroup -S appgroup && adduser -S appuser -G appgroup

COPY --from=builder /app/indicator-service .

USER appuser

EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
  CMD wget -qO- http://localhost:8080/health || exit 1

CMD ["./indicator-service"]
