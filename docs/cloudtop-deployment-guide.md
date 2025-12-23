# Cloudtop Deployment and Testing Guide

## Build and Installation

### Development Setup

```bash
# Clone repository
git clone https://github.com/yourusername/cloudtop.git
cd cloudtop

# Install dependencies
go mod download

# Build for development
make build

# Run tests
make test

# Run with race detector
make test-race

# Generate code coverage
make coverage
```

### Makefile

```makefile
.PHONY: build test test-race coverage install clean lint fmt vet

BINARY_NAME=cloudtop
VERSION=$(shell git describe --tags --always --dirty)
BUILD_TIME=$(shell date -u '+%Y-%m-%d_%H:%M:%S')
LDFLAGS=-ldflags "-X main.Version=$(VERSION) -X main.BuildTime=$(BUILD_TIME)"

build:
	go build $(LDFLAGS) -o bin/$(BINARY_NAME) cmd/cloudtop/main.go

install:
	go install $(LDFLAGS) cmd/cloudtop/main.go

test:
	go test -v ./...

test-race:
	go test -race -v ./...

coverage:
	go test -coverprofile=coverage.out ./...
	go tool cover -html=coverage.out -o coverage.html

bench:
	go test -bench=. -benchmem ./...

lint:
	golangci-lint run

fmt:
	go fmt ./...

vet:
	go vet ./...

clean:
	rm -rf bin/
	rm -f coverage.out coverage.html

# Cross-compilation targets
build-all: build-linux build-darwin build-windows

build-linux:
	GOOS=linux GOARCH=amd64 go build $(LDFLAGS) -o bin/$(BINARY_NAME)-linux-amd64 cmd/cloudtop/main.go
	GOOS=linux GOARCH=arm64 go build $(LDFLAGS) -o bin/$(BINARY_NAME)-linux-arm64 cmd/cloudtop/main.go

build-darwin:
	GOOS=darwin GOARCH=amd64 go build $(LDFLAGS) -o bin/$(BINARY_NAME)-darwin-amd64 cmd/cloudtop/main.go
	GOOS=darwin GOARCH=arm64 go build $(LDFLAGS) -o bin/$(BINARY_NAME)-darwin-arm64 cmd/cloudtop/main.go

build-windows:
	GOOS=windows GOARCH=amd64 go build $(LDFLAGS) -o bin/$(BINARY_NAME)-windows-amd64.exe cmd/cloudtop/main.go

# Docker targets
docker-build:
	docker build -t cloudtop:$(VERSION) .

docker-run:
	docker run --rm -v $(HOME)/.cloudtop.json:/root/.cloudtop.json cloudtop:$(VERSION)

# Release targets
release: clean test build-all
	mkdir -p dist
	tar czf dist/$(BINARY_NAME)-$(VERSION)-linux-amd64.tar.gz -C bin $(BINARY_NAME)-linux-amd64
	tar czf dist/$(BINARY_NAME)-$(VERSION)-linux-arm64.tar.gz -C bin $(BINARY_NAME)-linux-arm64
	tar czf dist/$(BINARY_NAME)-$(VERSION)-darwin-amd64.tar.gz -C bin $(BINARY_NAME)-darwin-amd64
	tar czf dist/$(BINARY_NAME)-$(VERSION)-darwin-arm64.tar.gz -C bin $(BINARY_NAME)-darwin-arm64
	zip dist/$(BINARY_NAME)-$(VERSION)-windows-amd64.zip bin/$(BINARY_NAME)-windows-amd64.exe

# CI/CD helpers
ci-test:
	go test -race -coverprofile=coverage.out -covermode=atomic ./...

ci-lint:
	golangci-lint run --out-format=github-actions
```

## Dockerfile for Containerized Deployment

```dockerfile
# Multi-stage build for minimal image size

# Build stage
FROM golang:1.21-alpine AS builder

# Install build dependencies
RUN apk add --no-cache git make

WORKDIR /app

# Copy go mod files
COPY go.mod go.sum ./
RUN go mod download

# Copy source code
COPY . .

# Build binary
RUN make build

# Runtime stage
FROM alpine:latest

# Install ca-certificates for HTTPS
RUN apk add --no-cache ca-certificates

# Create non-root user
RUN addgroup -S cloudtop && adduser -S cloudtop -G cloudtop

WORKDIR /home/cloudtop

# Copy binary from builder
COPY --from=builder /app/bin/cloudtop /usr/local/bin/cloudtop

# Set ownership
RUN chown -R cloudtop:cloudtop /home/cloudtop

# Switch to non-root user
USER cloudtop

# Set entrypoint
ENTRYPOINT ["/usr/local/bin/cloudtop"]
CMD ["--help"]
```

## Configuration Management

### Environment-Specific Configurations

```bash
# configs/production.json
{
  "version": "1.0",
  "defaults": {
    "refresh_interval": "60s",
    "output_format": "json",
    "show_cached": false
  },
  "cache": {
    "enabled": true,
    "backend": "redis",
    "redis_url": "${REDIS_URL}",
    "ttl": "10m",
    "max_size": 10000
  },
  "providers": {
    "cloudflare": {
      "enabled": true,
      "auth": {
        "method": "api_key",
        "env_api_key": "CLOUDFLARE_API_TOKEN"
      },
      "rate_limit": {
        "requests_per_second": 4,
        "burst": 10,
        "timeout": "30s"
      }
    }
  }
}
```

### Credential Management Best Practices

```go
// internal/config/credentials.go

package config

import (
    "fmt"
    "os"
    "strings"
)

// ToCredentials converts AuthConfig to a credential map
func (a *AuthConfig) ToCredentials() map[string]string {
    creds := make(map[string]string)

    switch a.Method {
    case "api_key":
        // Check environment variable reference
        if a.EnvAPIKey != "" {
            apiKey := os.Getenv(a.EnvAPIKey)
            if apiKey == "" {
                fmt.Fprintf(os.Stderr, "Warning: environment variable %s not set\n", a.EnvAPIKey)
            }
            creds["api_token"] = apiKey
        } else if a.APIKey != "" {
            creds["api_token"] = a.APIKey
        }

        if a.EnvSecret != "" {
            secret := os.Getenv(a.EnvSecret)
            if secret == "" {
                fmt.Fprintf(os.Stderr, "Warning: environment variable %s not set\n", a.EnvSecret)
            }
            creds["api_secret"] = secret
        } else if a.APISecret != "" {
            creds["api_secret"] = a.APISecret
        }

    case "oauth":
        creds["client_id"] = a.ClientID
        creds["client_secret"] = a.ClientSecret
        creds["token_url"] = a.TokenURL

    case "service_account":
        // Expand home directory
        keyFile := expandPath(a.KeyFile)
        creds["key_file"] = keyFile

    case "env":
        // All credentials come from environment
        for k, v := range a.EnvVars {
            creds[k] = os.Getenv(v)
        }
    }

    return creds
}

func expandPath(path string) string {
    if strings.HasPrefix(path, "~/") {
        home, err := os.UserHomeDir()
        if err != nil {
            return path
        }
        return strings.Replace(path, "~", home, 1)
    }
    return path
}
```

## Testing Strategy

### Unit Tests

```go
// internal/provider/cloudflare/cloudflare_test.go

package cloudflare

import (
    "context"
    "testing"

    "github.com/stretchr/testify/assert"
    "github.com/stretchr/testify/require"

    "github.com/adsops/cloudtop/internal/provider"
)

func TestCloudflareProvider_Name(t *testing.T) {
    p := &CloudflareProvider{}
    assert.Equal(t, "cloudflare", p.Name())
}

func TestCloudflareProvider_Initialize(t *testing.T) {
    tests := []struct {
        name    string
        config  *provider.ProviderConfig
        wantErr bool
    }{
        {
            name: "valid api token",
            config: &provider.ProviderConfig{
                Name:    "cloudflare",
                Enabled: true,
                Credentials: map[string]string{
                    "api_token": "test-token",
                },
                Options: map[string]interface{}{
                    "account_id": "test-account",
                },
            },
            wantErr: false,
        },
        {
            name: "missing api token",
            config: &provider.ProviderConfig{
                Name:        "cloudflare",
                Enabled:     true,
                Credentials: map[string]string{},
            },
            wantErr: true,
        },
    }

    for _, tt := range tests {
        t.Run(tt.name, func(t *testing.T) {
            p := &CloudflareProvider{}
            err := p.Initialize(context.Background(), tt.config)

            if tt.wantErr {
                assert.Error(t, err)
            } else {
                assert.NoError(t, err)
            }
        })
    }
}

func TestCloudflareProvider_ListServices(t *testing.T) {
    p := &CloudflareProvider{}

    services, err := p.ListServices(context.Background())
    require.NoError(t, err)

    assert.NotEmpty(t, services)
    assert.Contains(t, getServiceIDs(services), "workers")
    assert.Contains(t, getServiceIDs(services), "r2")
}

func getServiceIDs(services []provider.Service) []string {
    ids := make([]string, len(services))
    for i, s := range services {
        ids[i] = s.ID
    }
    return ids
}
```

### Integration Tests

```go
// internal/provider/cloudflare/integration_test.go
// +build integration

package cloudflare

import (
    "context"
    "os"
    "testing"

    "github.com/stretchr/testify/assert"
    "github.com/stretchr/testify/require"

    "github.com/adsops/cloudtop/internal/provider"
)

func TestCloudflareProvider_Integration(t *testing.T) {
    // Skip if no API token
    apiToken := os.Getenv("CLOUDFLARE_API_TOKEN")
    if apiToken == "" {
        t.Skip("CLOUDFLARE_API_TOKEN not set")
    }

    accountID := os.Getenv("CLOUDFLARE_ACCOUNT_ID")
    if accountID == "" {
        t.Skip("CLOUDFLARE_ACCOUNT_ID not set")
    }

    ctx := context.Background()

    config := &provider.ProviderConfig{
        Name:    "cloudflare",
        Enabled: true,
        Credentials: map[string]string{
            "api_token": apiToken,
        },
        Options: map[string]interface{}{
            "account_id": accountID,
        },
    }

    p := &CloudflareProvider{}
    err := p.Initialize(ctx, config)
    require.NoError(t, err)

    // Test health check
    err = p.HealthCheck(ctx)
    assert.NoError(t, err)

    // Test listing resources
    resources, err := p.ListResources(ctx, nil)
    assert.NoError(t, err)
    t.Logf("Found %d resources", len(resources))

    // Test listing services
    services, err := p.ListServices(ctx)
    assert.NoError(t, err)
    assert.NotEmpty(t, services)
}
```

### Benchmark Tests

```go
// internal/collector/collector_bench_test.go

package collector

import (
    "context"
    "testing"
    "time"

    "github.com/adsops/cloudtop/internal/provider"
)

func BenchmarkCollector_Collect(b *testing.B) {
    // Setup mock providers
    providers := setupMockProviders(10) // 10 mock providers

    cache := NewMemoryCache(5*time.Minute, 1000)
    col := NewCollector(providers, cache)

    req := &CollectRequest{
        Providers: []string{"mock1", "mock2", "mock3"},
        Timeout:   30 * time.Second,
    }

    ctx := context.Background()

    b.ResetTimer()
    for i := 0; i < b.N; i++ {
        _, err := col.Collect(ctx, req)
        if err != nil {
            b.Fatal(err)
        }
    }
}

func BenchmarkMemoryCache_Get(b *testing.B) {
    cache := NewMemoryCache(5*time.Minute, 10000)

    // Populate cache
    for i := 0; i < 1000; i++ {
        cache.Set(fmt.Sprintf("key-%d", i), "value")
    }

    b.ResetTimer()
    for i := 0; i < b.N; i++ {
        cache.Get(fmt.Sprintf("key-%d", i%1000))
    }
}

func setupMockProviders(count int) map[string]provider.Provider {
    providers := make(map[string]provider.Provider)
    for i := 0; i < count; i++ {
        providers[fmt.Sprintf("mock%d", i)] = &MockProvider{
            name: fmt.Sprintf("mock%d", i),
        }
    }
    return providers
}
```

### Test Coverage Goals

- **Unit tests**: 80%+ coverage for core logic
- **Integration tests**: All provider implementations
- **Benchmark tests**: Critical paths (collection, caching)
- **Load tests**: Concurrent provider queries

## Monitoring and Observability

### Structured Logging

```go
// internal/logger/logger.go

package logger

import (
    "go.uber.org/zap"
    "go.uber.org/zap/zapcore"
)

var log *zap.Logger

func init() {
    config := zap.NewProductionConfig()
    config.EncoderConfig.TimeKey = "timestamp"
    config.EncoderConfig.EncodeTime = zapcore.ISO8601TimeEncoder

    var err error
    log, err = config.Build()
    if err != nil {
        panic(err)
    }
}

func Get() *zap.Logger {
    return log
}

func Info(msg string, fields ...zap.Field) {
    log.Info(msg, fields...)
}

func Error(msg string, fields ...zap.Field) {
    log.Error(msg, fields...)
}

func Debug(msg string, fields ...zap.Field) {
    log.Debug(msg, fields...)
}

func Warn(msg string, fields ...zap.Field) {
    log.Warn(msg, fields...)
}

func With(fields ...zap.Field) *zap.Logger {
    return log.With(fields...)
}
```

### Usage in Providers

```go
func (p *CloudflareProvider) ListResources(ctx context.Context, filter *provider.ResourceFilter) ([]provider.Resource, error) {
    logger := logger.Get().With(
        zap.String("provider", "cloudflare"),
        zap.String("method", "ListResources"),
    )

    logger.Debug("listing resources",
        zap.Any("filter", filter),
    )

    start := time.Now()
    defer func() {
        logger.Debug("list resources completed",
            zap.Duration("duration", time.Since(start)),
        )
    }()

    // ... implementation
}
```

### Metrics Collection

```go
// internal/metrics/prometheus.go

package metrics

import (
    "github.com/prometheus/client_golang/prometheus"
    "github.com/prometheus/client_golang/prometheus/promauto"
)

var (
    providerRequests = promauto.NewCounterVec(
        prometheus.CounterOpts{
            Name: "cloudtop_provider_requests_total",
            Help: "Total number of requests to cloud providers",
        },
        []string{"provider", "method"},
    )

    providerErrors = promauto.NewCounterVec(
        prometheus.CounterOpts{
            Name: "cloudtop_provider_errors_total",
            Help: "Total number of errors from cloud providers",
        },
        []string{"provider", "method", "error_type"},
    )

    providerDuration = promauto.NewHistogramVec(
        prometheus.HistogramOpts{
            Name:    "cloudtop_provider_duration_seconds",
            Help:    "Duration of provider API calls",
            Buckets: prometheus.DefBuckets,
        },
        []string{"provider", "method"},
    )

    cacheHits = promauto.NewCounter(
        prometheus.CounterOpts{
            Name: "cloudtop_cache_hits_total",
            Help: "Total number of cache hits",
        },
    )

    cacheMisses = promauto.NewCounter(
        prometheus.CounterOpts{
            Name: "cloudtop_cache_misses_total",
            Help: "Total number of cache misses",
        },
    )
)

func RecordProviderRequest(provider, method string) {
    providerRequests.WithLabelValues(provider, method).Inc()
}

func RecordProviderError(provider, method, errorType string) {
    providerErrors.WithLabelValues(provider, method, errorType).Inc()
}

func RecordProviderDuration(provider, method string, duration float64) {
    providerDuration.WithLabelValues(provider, method).Observe(duration)
}

func RecordCacheHit() {
    cacheHits.Inc()
}

func RecordCacheMiss() {
    cacheMisses.Inc()
}
```

## CI/CD Pipeline

### GitHub Actions Workflow

```yaml
# .github/workflows/ci.yml

name: CI

on:
  push:
    branches: [ main ]
  pull_request:
    branches: [ main ]

jobs:
  test:
    name: Test
    runs-on: ubuntu-latest
    steps:
    - name: Checkout code
      uses: actions/checkout@v4

    - name: Set up Go
      uses: actions/setup-go@v4
      with:
        go-version: '1.21'

    - name: Cache Go modules
      uses: actions/cache@v3
      with:
        path: ~/go/pkg/mod
        key: ${{ runner.os }}-go-${{ hashFiles('**/go.sum') }}
        restore-keys: |
          ${{ runner.os }}-go-

    - name: Download dependencies
      run: go mod download

    - name: Run tests
      run: make ci-test

    - name: Upload coverage
      uses: codecov/codecov-action@v3
      with:
        file: ./coverage.out

  lint:
    name: Lint
    runs-on: ubuntu-latest
    steps:
    - name: Checkout code
      uses: actions/checkout@v4

    - name: Set up Go
      uses: actions/setup-go@v4
      with:
        go-version: '1.21'

    - name: Run golangci-lint
      uses: golangci/golangci-lint-action@v3
      with:
        version: latest

  build:
    name: Build
    runs-on: ubuntu-latest
    needs: [test, lint]
    steps:
    - name: Checkout code
      uses: actions/checkout@v4

    - name: Set up Go
      uses: actions/setup-go@v4
      with:
        go-version: '1.21'

    - name: Build
      run: make build-all

    - name: Upload artifacts
      uses: actions/upload-artifact@v3
      with:
        name: binaries
        path: bin/

  integration-test:
    name: Integration Tests
    runs-on: ubuntu-latest
    if: github.event_name == 'push' && github.ref == 'refs/heads/main'
    needs: [build]
    steps:
    - name: Checkout code
      uses: actions/checkout@v4

    - name: Set up Go
      uses: actions/setup-go@v4
      with:
        go-version: '1.21'

    - name: Run integration tests
      run: go test -tags=integration -v ./...
      env:
        CLOUDFLARE_API_TOKEN: ${{ secrets.CLOUDFLARE_API_TOKEN }}
        CLOUDFLARE_ACCOUNT_ID: ${{ secrets.CLOUDFLARE_ACCOUNT_ID }}
```

### Release Workflow

```yaml
# .github/workflows/release.yml

name: Release

on:
  push:
    tags:
      - 'v*'

jobs:
  release:
    name: Create Release
    runs-on: ubuntu-latest
    steps:
    - name: Checkout code
      uses: actions/checkout@v4
      with:
        fetch-depth: 0

    - name: Set up Go
      uses: actions/setup-go@v4
      with:
        go-version: '1.21'

    - name: Run tests
      run: make test

    - name: Build release binaries
      run: make release

    - name: Create Release
      uses: softprops/action-gh-release@v1
      with:
        files: dist/*
        generate_release_notes: true
      env:
        GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
```

## Performance Optimization

### Concurrent API Calls Pattern

```go
// internal/collector/parallel.go

package collector

import (
    "context"
    "sync"

    "golang.org/x/sync/errgroup"
)

// ParallelExecutor executes tasks concurrently with error handling
type ParallelExecutor struct {
    maxConcurrency int
}

// NewParallelExecutor creates a new parallel executor
func NewParallelExecutor(maxConcurrency int) *ParallelExecutor {
    return &ParallelExecutor{
        maxConcurrency: maxConcurrency,
    }
}

// Execute runs tasks concurrently
func (e *ParallelExecutor) Execute(ctx context.Context, tasks []func() error) error {
    g, ctx := errgroup.WithContext(ctx)
    g.SetLimit(e.maxConcurrency)

    for _, task := range tasks {
        task := task // Capture loop variable
        g.Go(func() error {
            return task()
        })
    }

    return g.Wait()
}

// ExecuteWithResults runs tasks concurrently and collects results
func (e *ParallelExecutor) ExecuteWithResults(ctx context.Context, tasks []func() (interface{}, error)) ([]interface{}, []error) {
    var mu sync.Mutex
    results := make([]interface{}, len(tasks))
    errors := make([]error, len(tasks))

    g, ctx := errgroup.WithContext(ctx)
    g.SetLimit(e.maxConcurrency)

    for i, task := range tasks {
        i, task := i, task // Capture loop variables
        g.Go(func() error {
            result, err := task()

            mu.Lock()
            results[i] = result
            errors[i] = err
            mu.Unlock()

            return nil // Don't propagate errors, collect them instead
        })
    }

    g.Wait()

    return results, errors
}
```

### Connection Pooling for HTTP Clients

```go
// pkg/httpclient/client.go

package httpclient

import (
    "net"
    "net/http"
    "time"
)

// NewHTTPClient creates an optimized HTTP client
func NewHTTPClient() *http.Client {
    return &http.Client{
        Transport: &http.Transport{
            Proxy: http.ProxyFromEnvironment,
            DialContext: (&net.Dialer{
                Timeout:   30 * time.Second,
                KeepAlive: 30 * time.Second,
            }).DialContext,
            MaxIdleConns:          100,
            MaxIdleConnsPerHost:   10,
            IdleConnTimeout:       90 * time.Second,
            TLSHandshakeTimeout:   10 * time.Second,
            ExpectContinueTimeout: 1 * time.Second,
            ForceAttemptHTTP2:     true,
        },
        Timeout: 60 * time.Second,
    }
}
```

## Production Deployment Checklist

### Pre-Deployment

- [ ] All tests passing (unit, integration, benchmarks)
- [ ] Code coverage meets threshold (80%+)
- [ ] Security scan completed (gosec, snyk)
- [ ] Dependencies updated and audited
- [ ] Documentation updated
- [ ] Configuration validated for all environments
- [ ] Credentials properly secured (secrets management)
- [ ] Rate limits configured appropriately
- [ ] Monitoring and alerting configured

### Deployment Steps

1. **Build release binaries**
   ```bash
   make release
   ```

2. **Verify checksums**
   ```bash
   sha256sum dist/*
   ```

3. **Test binary on staging**
   ```bash
   ./bin/cloudtop --config configs/staging.json --all
   ```

4. **Deploy to production**
   ```bash
   # For binary distribution
   sudo cp bin/cloudtop /usr/local/bin/
   sudo chmod +x /usr/local/bin/cloudtop

   # For Docker
   docker build -t cloudtop:v1.0.0 .
   docker push yourregistry/cloudtop:v1.0.0
   ```

5. **Verify deployment**
   ```bash
   cloudtop --version
   cloudtop --config ~/.cloudtop.json --all
   ```

### Post-Deployment

- [ ] Monitor error rates
- [ ] Check API rate limit usage
- [ ] Verify cache hit rates
- [ ] Monitor response times
- [ ] Review logs for warnings/errors
- [ ] Validate metrics collection
- [ ] Test rollback procedure

## Troubleshooting

### Common Issues

**Issue: Rate limit exceeded**
```bash
# Solution: Adjust rate limits in config
{
  "providers": {
    "cloudflare": {
      "rate_limit": {
        "requests_per_second": 2,  # Reduce from 4
        "burst": 5                  # Reduce from 10
      }
    }
  }
}
```

**Issue: Authentication failed**
```bash
# Solution: Verify credentials
export CLOUDFLARE_API_TOKEN="your-token"
cloudtop --cloudflare --list

# Check credential file permissions
chmod 600 ~/.oci/config
```

**Issue: High memory usage**
```bash
# Solution: Reduce cache size
{
  "cache": {
    "max_size": 500,  # Reduce from 1000
    "ttl": "3m"       # Reduce from 5m
  }
}
```

**Issue: Slow response times**
```bash
# Solution: Enable concurrent collection and caching
{
  "cache": {
    "enabled": true,
    "ttl": "5m"
  }
}

# Use parallel mode
cloudtop --all --json  # Queries all providers concurrently
```

This deployment guide provides everything needed to build, test, deploy, and operate cloudtop in production at enterprise scale.
