# Cloudtop Architecture Design

## Core Provider Interface

```go
package provider

import (
    "context"
    "time"

    "github.com/adsops/cloudtop/internal/metrics"
)

// Provider is the core interface that all cloud providers must implement
type Provider interface {
    // Name returns the provider identifier (e.g., "cloudflare", "oracle")
    Name() string

    // Initialize sets up the provider with credentials and config
    Initialize(ctx context.Context, config *ProviderConfig) error

    // HealthCheck verifies the provider is accessible
    HealthCheck(ctx context.Context) error

    // ListServices returns available services for this provider
    ListServices(ctx context.Context) ([]Service, error)

    // GetMetrics retrieves metrics for specified resources
    GetMetrics(ctx context.Context, req *MetricsRequest) (*MetricsResponse, error)

    // ListResources lists all resources (VMs, containers, functions)
    ListResources(ctx context.Context, filter *ResourceFilter) ([]Resource, error)

    // Close cleans up resources
    Close() error
}

// ComputeProvider extends Provider with compute-specific capabilities
type ComputeProvider interface {
    Provider

    // ListInstances returns compute instances (VMs, containers)
    ListInstances(ctx context.Context, filter *InstanceFilter) ([]Instance, error)

    // GetInstanceMetrics retrieves metrics for specific instance
    GetInstanceMetrics(ctx context.Context, instanceID string) (*metrics.ComputeMetrics, error)
}

// GPUProvider extends Provider with GPU-specific capabilities
type GPUProvider interface {
    Provider

    // ListGPUInstances returns GPU-enabled instances
    ListGPUInstances(ctx context.Context, filter *GPUFilter) ([]GPUInstance, error)

    // GetGPUMetrics retrieves GPU utilization metrics
    GetGPUMetrics(ctx context.Context, instanceID string) (*metrics.GPUMetrics, error)

    // GetGPUAvailability returns available GPU types and pricing
    GetGPUAvailability(ctx context.Context) ([]GPUOffering, error)
}

// ServerlessProvider extends Provider with serverless capabilities
type ServerlessProvider interface {
    Provider

    // ListFunctions returns serverless functions
    ListFunctions(ctx context.Context, filter *FunctionFilter) ([]Function, error)

    // GetFunctionMetrics retrieves function execution metrics
    GetFunctionMetrics(ctx context.Context, functionID string) (*metrics.FunctionMetrics, error)
}

// StorageProvider extends Provider with storage capabilities
type StorageProvider interface {
    Provider

    // ListBuckets returns storage buckets
    ListBuckets(ctx context.Context) ([]Bucket, error)

    // GetStorageMetrics retrieves storage usage metrics
    GetStorageMetrics(ctx context.Context, bucketID string) (*metrics.StorageMetrics, error)
}

// DatabaseProvider extends Provider with database capabilities
type DatabaseProvider interface {
    Provider

    // ListDatabases returns database instances
    ListDatabases(ctx context.Context) ([]Database, error)

    // GetDatabaseMetrics retrieves database metrics
    GetDatabaseMetrics(ctx context.Context, dbID string) (*metrics.DatabaseMetrics, error)
}
```

## Core Types

```go
package provider

import (
    "time"
)

// ProviderConfig holds provider-specific configuration
type ProviderConfig struct {
    Name        string                 `json:"name"`
    Enabled     bool                   `json:"enabled"`
    Credentials map[string]string      `json:"credentials"`
    Options     map[string]interface{} `json:"options"`
    RateLimit   *RateLimitConfig       `json:"rate_limit,omitempty"`
    Cache       *CacheConfig           `json:"cache,omitempty"`
}

// RateLimitConfig defines rate limiting parameters
type RateLimitConfig struct {
    RequestsPerSecond float64       `json:"requests_per_second"`
    Burst             int           `json:"burst"`
    Timeout           time.Duration `json:"timeout"`
}

// CacheConfig defines caching parameters
type CacheConfig struct {
    Enabled bool          `json:"enabled"`
    TTL     time.Duration `json:"ttl"`
    MaxSize int           `json:"max_size"`
}

// Service represents a cloud service (e.g., "compute", "storage")
type Service struct {
    ID          string   `json:"id"`
    Name        string   `json:"name"`
    Type        string   `json:"type"`
    Capabilities []string `json:"capabilities"`
}

// Resource is a generic cloud resource
type Resource struct {
    ID           string            `json:"id"`
    Name         string            `json:"name"`
    Type         string            `json:"type"`
    Provider     string            `json:"provider"`
    Region       string            `json:"region"`
    Status       string            `json:"status"`
    Tags         map[string]string `json:"tags"`
    CreatedAt    time.Time         `json:"created_at"`
    UpdatedAt    time.Time         `json:"updated_at"`
}

// Instance represents a compute instance
type Instance struct {
    Resource
    InstanceType string  `json:"instance_type"`
    PublicIP     string  `json:"public_ip,omitempty"`
    PrivateIP    string  `json:"private_ip,omitempty"`
    CPUCores     int     `json:"cpu_cores"`
    MemoryGB     float64 `json:"memory_gb"`
    State        string  `json:"state"` // running, stopped, etc.
}

// GPUInstance represents a GPU-enabled instance
type GPUInstance struct {
    Instance
    GPUType      string  `json:"gpu_type"`
    GPUCount     int     `json:"gpu_count"`
    GPUMemoryGB  float64 `json:"gpu_memory_gb"`
    PricePerHour float64 `json:"price_per_hour,omitempty"`
}

// GPUOffering represents available GPU instance types
type GPUOffering struct {
    Provider     string  `json:"provider"`
    GPUType      string  `json:"gpu_type"`
    GPUCount     int     `json:"gpu_count"`
    GPUMemoryGB  float64 `json:"gpu_memory_gb"`
    CPUCores     int     `json:"cpu_cores"`
    MemoryGB     float64 `json:"memory_gb"`
    PricePerHour float64 `json:"price_per_hour"`
    Available    bool    `json:"available"`
    Region       string  `json:"region"`
}

// Function represents a serverless function
type Function struct {
    Resource
    Runtime      string `json:"runtime"`
    MemoryMB     int    `json:"memory_mb"`
    Timeout      int    `json:"timeout"`
    LastModified time.Time `json:"last_modified"`
}

// Bucket represents a storage bucket
type Bucket struct {
    Resource
    SizeBytes    int64  `json:"size_bytes"`
    ObjectCount  int64  `json:"object_count"`
    StorageClass string `json:"storage_class"`
}

// Database represents a database instance
type Database struct {
    Resource
    Engine      string  `json:"engine"`
    Version     string  `json:"version"`
    SizeGB      float64 `json:"size_gb"`
    Connections int     `json:"connections"`
}

// MetricsRequest specifies what metrics to collect
type MetricsRequest struct {
    ResourceIDs []string          `json:"resource_ids"`
    MetricNames []string          `json:"metric_names"`
    StartTime   time.Time         `json:"start_time"`
    EndTime     time.Time         `json:"end_time"`
    Granularity time.Duration     `json:"granularity"`
    Filters     map[string]string `json:"filters"`
}

// MetricsResponse contains collected metrics
type MetricsResponse struct {
    Provider  string                 `json:"provider"`
    Metrics   map[string]interface{} `json:"metrics"`
    Timestamp time.Time              `json:"timestamp"`
    Cached    bool                   `json:"cached"`
}

// ResourceFilter for filtering resources
type ResourceFilter struct {
    Types    []string          `json:"types,omitempty"`
    Regions  []string          `json:"regions,omitempty"`
    Tags     map[string]string `json:"tags,omitempty"`
    Status   []string          `json:"status,omitempty"`
    NamePattern string         `json:"name_pattern,omitempty"`
}

// InstanceFilter for filtering instances
type InstanceFilter struct {
    ResourceFilter
    States        []string `json:"states,omitempty"` // running, stopped, etc.
    InstanceTypes []string `json:"instance_types,omitempty"`
}

// GPUFilter for filtering GPU instances
type GPUFilter struct {
    InstanceFilter
    GPUTypes     []string `json:"gpu_types,omitempty"`
    MinGPUMemory float64  `json:"min_gpu_memory,omitempty"`
    MaxPrice     float64  `json:"max_price,omitempty"`
}

// FunctionFilter for filtering functions
type FunctionFilter struct {
    ResourceFilter
    Runtimes []string `json:"runtimes,omitempty"`
}
```

## Metrics Types

```go
package metrics

import (
    "time"
)

// ComputeMetrics represents compute instance metrics
type ComputeMetrics struct {
    ResourceID    string    `json:"resource_id"`
    Provider      string    `json:"provider"`
    Timestamp     time.Time `json:"timestamp"`

    // CPU Metrics
    CPUUsagePercent     float64 `json:"cpu_usage_percent"`
    CPUCores            int     `json:"cpu_cores"`
    CPUCreditsRemaining float64 `json:"cpu_credits_remaining,omitempty"` // For burstable instances

    // Memory Metrics
    MemoryUsedBytes      int64   `json:"memory_used_bytes"`
    MemoryTotalBytes     int64   `json:"memory_total_bytes"`
    MemoryUsagePercent   float64 `json:"memory_usage_percent"`
    SwapUsedBytes        int64   `json:"swap_used_bytes,omitempty"`

    // Disk I/O Metrics
    DiskReadBytesPerSec  int64   `json:"disk_read_bytes_per_sec"`
    DiskWriteBytesPerSec int64   `json:"disk_write_bytes_per_sec"`
    DiskReadOpsPerSec    float64 `json:"disk_read_ops_per_sec"`
    DiskWriteOpsPerSec   float64 `json:"disk_write_ops_per_sec"`

    // Network Metrics
    NetworkInBytesPerSec  int64   `json:"network_in_bytes_per_sec"`
    NetworkOutBytesPerSec int64   `json:"network_out_bytes_per_sec"`
    NetworkInPacketsPerSec float64 `json:"network_in_packets_per_sec"`
    NetworkOutPacketsPerSec float64 `json:"network_out_packets_per_sec"`
}

// GPUMetrics represents GPU-specific metrics
type GPUMetrics struct {
    ResourceID  string    `json:"resource_id"`
    Provider    string    `json:"provider"`
    Timestamp   time.Time `json:"timestamp"`

    // Per-GPU Metrics (array for multi-GPU instances)
    GPUs []GPUDeviceMetrics `json:"gpus"`
}

// GPUDeviceMetrics represents metrics for a single GPU
type GPUDeviceMetrics struct {
    DeviceID           int     `json:"device_id"`
    Name               string  `json:"name"`

    // Utilization
    GPUUtilization     float64 `json:"gpu_utilization_percent"`
    MemoryUtilization  float64 `json:"memory_utilization_percent"`

    // Memory
    MemoryUsedBytes    int64   `json:"memory_used_bytes"`
    MemoryTotalBytes   int64   `json:"memory_total_bytes"`

    // Temperature and Power
    TemperatureCelsius float64 `json:"temperature_celsius"`
    PowerUsageWatts    float64 `json:"power_usage_watts"`
    PowerLimitWatts    float64 `json:"power_limit_watts"`

    // Performance
    ClockSpeedMHz      int     `json:"clock_speed_mhz"`
    MemoryClockMHz     int     `json:"memory_clock_mhz"`
}

// FunctionMetrics represents serverless function metrics
type FunctionMetrics struct {
    ResourceID       string    `json:"resource_id"`
    Provider         string    `json:"provider"`
    Timestamp        time.Time `json:"timestamp"`

    // Invocation Metrics
    InvocationCount  int64   `json:"invocation_count"`
    ErrorCount       int64   `json:"error_count"`
    ThrottleCount    int64   `json:"throttle_count"`

    // Duration Metrics (milliseconds)
    AvgDuration      float64 `json:"avg_duration_ms"`
    MaxDuration      float64 `json:"max_duration_ms"`
    MinDuration      float64 `json:"min_duration_ms"`

    // Resource Usage
    AvgMemoryUsedMB  float64 `json:"avg_memory_used_mb"`
    ConcurrentExecs  int     `json:"concurrent_executions"`
}

// StorageMetrics represents storage metrics
type StorageMetrics struct {
    ResourceID       string    `json:"resource_id"`
    Provider         string    `json:"provider"`
    Timestamp        time.Time `json:"timestamp"`

    // Storage Usage
    TotalSizeBytes   int64   `json:"total_size_bytes"`
    ObjectCount      int64   `json:"object_count"`

    // Request Metrics
    GetRequests      int64   `json:"get_requests"`
    PutRequests      int64   `json:"put_requests"`
    DeleteRequests   int64   `json:"delete_requests"`
    ListRequests     int64   `json:"list_requests"`

    // Bandwidth
    BytesDownloaded  int64   `json:"bytes_downloaded"`
    BytesUploaded    int64   `json:"bytes_uploaded"`
}

// DatabaseMetrics represents database metrics
type DatabaseMetrics struct {
    ResourceID          string    `json:"resource_id"`
    Provider            string    `json:"provider"`
    Timestamp           time.Time `json:"timestamp"`

    // Connection Metrics
    ActiveConnections   int     `json:"active_connections"`
    MaxConnections      int     `json:"max_connections"`
    IdleConnections     int     `json:"idle_connections"`

    // Query Performance
    QueriesPerSecond    float64 `json:"queries_per_second"`
    AvgQueryDurationMs  float64 `json:"avg_query_duration_ms"`
    SlowQueries         int64   `json:"slow_queries"`

    // Storage
    DatabaseSizeBytes   int64   `json:"database_size_bytes"`

    // Cache (if applicable)
    CacheHitRatio       float64 `json:"cache_hit_ratio,omitempty"`

    // Replication (if applicable)
    ReplicationLagMs    float64 `json:"replication_lag_ms,omitempty"`
}
```

## Configuration Schema

```go
package config

import (
    "time"
)

// Config represents the root cloudtop configuration
type Config struct {
    Version   string              `json:"version"`
    Providers map[string]Provider `json:"providers"`
    Defaults  Defaults            `json:"defaults"`
    Output    OutputConfig        `json:"output"`
    Cache     GlobalCacheConfig   `json:"cache"`
}

// Provider represents a single provider configuration
type Provider struct {
    Enabled     bool              `json:"enabled"`
    Auth        AuthConfig        `json:"auth"`
    Regions     []string          `json:"regions,omitempty"`
    Services    []string          `json:"services,omitempty"`
    RateLimit   *RateLimitConfig  `json:"rate_limit,omitempty"`
    Timeout     time.Duration     `json:"timeout,omitempty"`
    Options     map[string]interface{} `json:"options,omitempty"`
}

// AuthConfig handles multiple authentication methods
type AuthConfig struct {
    Method string            `json:"method"` // "api_key", "oauth", "service_account", "env"

    // For API Key authentication
    APIKey       string `json:"api_key,omitempty"`
    APISecret    string `json:"api_secret,omitempty"`

    // For OAuth
    ClientID     string `json:"client_id,omitempty"`
    ClientSecret string `json:"client_secret,omitempty"`
    TokenURL     string `json:"token_url,omitempty"`

    // For Service Account (GCP, Azure)
    KeyFile      string `json:"key_file,omitempty"`

    // Environment variable references
    EnvAPIKey    string `json:"env_api_key,omitempty"`
    EnvSecret    string `json:"env_secret,omitempty"`
}

// RateLimitConfig defines rate limiting
type RateLimitConfig struct {
    RequestsPerSecond float64       `json:"requests_per_second"`
    Burst             int           `json:"burst"`
    Timeout           time.Duration `json:"timeout"`
}

// Defaults for CLI behavior
type Defaults struct {
    RefreshInterval time.Duration `json:"refresh_interval"`
    OutputFormat    string        `json:"output_format"` // "table", "wide", "json"
    ShowCached      bool          `json:"show_cached"`
}

// OutputConfig controls output formatting
type OutputConfig struct {
    ColorEnabled bool              `json:"color_enabled"`
    Timestamps   bool              `json:"timestamps"`
    Columns      map[string][]string `json:"columns,omitempty"` // Custom column sets
}

// GlobalCacheConfig for global cache settings
type GlobalCacheConfig struct {
    Enabled  bool          `json:"enabled"`
    Backend  string        `json:"backend"` // "memory", "redis", "file"
    TTL      time.Duration `json:"ttl"`
    MaxSize  int           `json:"max_size"`

    // For Redis backend
    RedisURL string `json:"redis_url,omitempty"`

    // For File backend
    CacheDir string `json:"cache_dir,omitempty"`
}
```

## Provider Registry Pattern

```go
package provider

import (
    "context"
    "fmt"
    "sync"
)

var (
    registry = &Registry{
        providers: make(map[string]Factory),
    }
)

// Factory is a function that creates a new provider instance
type Factory func() Provider

// Registry manages provider registration and creation
type Registry struct {
    mu        sync.RWMutex
    providers map[string]Factory
}

// Register adds a provider factory to the registry
func Register(name string, factory Factory) {
    registry.mu.Lock()
    defer registry.mu.Unlock()
    registry.providers[name] = factory
}

// Get retrieves a provider factory by name
func (r *Registry) Get(name string) (Factory, error) {
    r.mu.RLock()
    defer r.mu.RUnlock()

    factory, ok := r.providers[name]
    if !ok {
        return nil, fmt.Errorf("provider %s not registered", name)
    }
    return factory, nil
}

// List returns all registered provider names
func (r *Registry) List() []string {
    r.mu.RLock()
    defer r.mu.RUnlock()

    names := make([]string, 0, len(r.providers))
    for name := range r.providers {
        names = append(names, name)
    }
    return names
}

// Create instantiates a provider by name
func Create(name string) (Provider, error) {
    factory, err := registry.Get(name)
    if err != nil {
        return nil, err
    }
    return factory(), nil
}

// GetRegistry returns the global registry instance
func GetRegistry() *Registry {
    return registry
}
```

## Collector Pattern with Concurrency

```go
package collector

import (
    "context"
    "fmt"
    "sync"
    "time"

    "github.com/adsops/cloudtop/internal/metrics"
    "github.com/adsops/cloudtop/internal/provider"
)

// Collector orchestrates data collection from multiple providers
type Collector struct {
    providers map[string]provider.Provider
    cache     Cache
    aggregator *Aggregator
}

// CollectRequest specifies what to collect
type CollectRequest struct {
    Providers   []string
    Services    []string
    MetricTypes []string
    Filters     *provider.ResourceFilter
    Timeout     time.Duration
}

// CollectResponse contains aggregated results
type CollectResponse struct {
    Results   map[string]*ProviderResult
    Errors    map[string]error
    Timestamp time.Time
    Duration  time.Duration
}

// ProviderResult contains results from a single provider
type ProviderResult struct {
    Provider  string
    Resources []provider.Resource
    Metrics   map[string]interface{}
    Cached    bool
    Duration  time.Duration
}

// NewCollector creates a new collector instance
func NewCollector(providers map[string]provider.Provider, cache Cache) *Collector {
    return &Collector{
        providers:  providers,
        cache:      cache,
        aggregator: NewAggregator(),
    }
}

// Collect gathers data from all specified providers concurrently
func (c *Collector) Collect(ctx context.Context, req *CollectRequest) (*CollectResponse, error) {
    start := time.Now()

    // Set default timeout if not specified
    if req.Timeout == 0 {
        req.Timeout = 30 * time.Second
    }

    // Create context with timeout
    ctx, cancel := context.WithTimeout(ctx, req.Timeout)
    defer cancel()

    // Determine which providers to query
    providersToQuery := c.getProvidersToQuery(req.Providers)

    // Collect from providers concurrently
    results := make(map[string]*ProviderResult)
    errors := make(map[string]error)

    var wg sync.WaitGroup
    var mu sync.Mutex

    for _, providerName := range providersToQuery {
        wg.Add(1)

        go func(name string) {
            defer wg.Done()

            result, err := c.collectFromProvider(ctx, name, req)

            mu.Lock()
            defer mu.Unlock()

            if err != nil {
                errors[name] = err
            } else {
                results[name] = result
            }
        }(providerName)
    }

    wg.Wait()

    return &CollectResponse{
        Results:   results,
        Errors:    errors,
        Timestamp: time.Now(),
        Duration:  time.Since(start),
    }, nil
}

// collectFromProvider collects data from a single provider
func (c *Collector) collectFromProvider(ctx context.Context, providerName string, req *CollectRequest) (*ProviderResult, error) {
    start := time.Now()

    // Check cache first
    cacheKey := c.buildCacheKey(providerName, req)
    if cached, ok := c.cache.Get(cacheKey); ok {
        result := cached.(*ProviderResult)
        result.Cached = true
        return result, nil
    }

    // Get provider
    p, ok := c.providers[providerName]
    if !ok {
        return nil, fmt.Errorf("provider %s not found", providerName)
    }

    // Check provider health
    if err := p.HealthCheck(ctx); err != nil {
        return nil, fmt.Errorf("provider health check failed: %w", err)
    }

    // List resources
    resources, err := p.ListResources(ctx, req.Filters)
    if err != nil {
        return nil, fmt.Errorf("failed to list resources: %w", err)
    }

    // Collect metrics for resources
    metricsData := make(map[string]interface{})

    if len(req.MetricTypes) > 0 {
        for _, resource := range resources {
            metricsReq := &provider.MetricsRequest{
                ResourceIDs: []string{resource.ID},
                MetricNames: req.MetricTypes,
                StartTime:   time.Now().Add(-5 * time.Minute),
                EndTime:     time.Now(),
                Granularity: 1 * time.Minute,
            }

            metricsResp, err := p.GetMetrics(ctx, metricsReq)
            if err != nil {
                // Log error but continue with other resources
                continue
            }

            metricsData[resource.ID] = metricsResp.Metrics
        }
    }

    result := &ProviderResult{
        Provider:  providerName,
        Resources: resources,
        Metrics:   metricsData,
        Cached:    false,
        Duration:  time.Since(start),
    }

    // Cache the result
    c.cache.Set(cacheKey, result)

    return result, nil
}

// getProvidersToQuery determines which providers to query
func (c *Collector) getProvidersToQuery(requested []string) []string {
    if len(requested) == 0 {
        // Return all providers
        providers := make([]string, 0, len(c.providers))
        for name := range c.providers {
            providers = append(providers, name)
        }
        return providers
    }
    return requested
}

// buildCacheKey creates a cache key from request parameters
func (c *Collector) buildCacheKey(provider string, req *CollectRequest) string {
    // Simple implementation - in production, use a more robust hashing
    return fmt.Sprintf("%s:%v:%v", provider, req.Services, req.MetricTypes)
}
```

## Cache Implementation

```go
package collector

import (
    "sync"
    "time"
)

// Cache interface for flexible caching backends
type Cache interface {
    Get(key string) (interface{}, bool)
    Set(key string, value interface{})
    Delete(key string)
    Clear()
}

// MemoryCache is an in-memory cache with TTL
type MemoryCache struct {
    mu      sync.RWMutex
    items   map[string]*cacheItem
    ttl     time.Duration
    maxSize int
}

type cacheItem struct {
    value      interface{}
    expiration time.Time
}

// NewMemoryCache creates a new in-memory cache
func NewMemoryCache(ttl time.Duration, maxSize int) *MemoryCache {
    cache := &MemoryCache{
        items:   make(map[string]*cacheItem),
        ttl:     ttl,
        maxSize: maxSize,
    }

    // Start cleanup goroutine
    go cache.cleanup()

    return cache
}

// Get retrieves a value from cache
func (c *MemoryCache) Get(key string) (interface{}, bool) {
    c.mu.RLock()
    defer c.mu.RUnlock()

    item, ok := c.items[key]
    if !ok {
        return nil, false
    }

    if time.Now().After(item.expiration) {
        return nil, false
    }

    return item.value, true
}

// Set stores a value in cache
func (c *MemoryCache) Set(key string, value interface{}) {
    c.mu.Lock()
    defer c.mu.Unlock()

    // Simple eviction: if cache is full, clear it
    // In production, use LRU or similar
    if len(c.items) >= c.maxSize {
        c.items = make(map[string]*cacheItem)
    }

    c.items[key] = &cacheItem{
        value:      value,
        expiration: time.Now().Add(c.ttl),
    }
}

// Delete removes a value from cache
func (c *MemoryCache) Delete(key string) {
    c.mu.Lock()
    defer c.mu.Unlock()
    delete(c.items, key)
}

// Clear removes all items from cache
func (c *MemoryCache) Clear() {
    c.mu.Lock()
    defer c.mu.Unlock()
    c.items = make(map[string]*cacheItem)
}

// cleanup periodically removes expired items
func (c *MemoryCache) cleanup() {
    ticker := time.NewTicker(1 * time.Minute)
    defer ticker.Stop()

    for range ticker.C {
        c.mu.Lock()
        now := time.Now()
        for key, item := range c.items {
            if now.After(item.expiration) {
                delete(c.items, key)
            }
        }
        c.mu.Unlock()
    }
}
```

## Error Handling Strategy

```go
package errors

import (
    "fmt"
)

// ErrorType represents different categories of errors
type ErrorType int

const (
    ErrorTypeAuth ErrorType = iota
    ErrorTypeNetwork
    ErrorTypeRateLimit
    ErrorTypeNotFound
    ErrorTypePermission
    ErrorTypeValidation
    ErrorTypeInternal
)

// CloudtopError is a custom error type with metadata
type CloudtopError struct {
    Type     ErrorType
    Provider string
    Message  string
    Err      error
    Retryable bool
}

// Error implements the error interface
func (e *CloudtopError) Error() string {
    if e.Provider != "" {
        return fmt.Sprintf("[%s] %s: %v", e.Provider, e.Message, e.Err)
    }
    return fmt.Sprintf("%s: %v", e.Message, e.Err)
}

// Unwrap implements error unwrapping
func (e *CloudtopError) Unwrap() error {
    return e.Err
}

// IsRetryable returns whether the error can be retried
func (e *CloudtopError) IsRetryable() bool {
    return e.Retryable
}

// Constructor functions for common error types

func NewAuthError(provider string, err error) *CloudtopError {
    return &CloudtopError{
        Type:      ErrorTypeAuth,
        Provider:  provider,
        Message:   "authentication failed",
        Err:       err,
        Retryable: false,
    }
}

func NewNetworkError(provider string, err error) *CloudtopError {
    return &CloudtopError{
        Type:      ErrorTypeNetwork,
        Provider:  provider,
        Message:   "network error",
        Err:       err,
        Retryable: true,
    }
}

func NewRateLimitError(provider string, err error) *CloudtopError {
    return &CloudtopError{
        Type:      ErrorTypeRateLimit,
        Provider:  provider,
        Message:   "rate limit exceeded",
        Err:       err,
        Retryable: true,
    }
}

func NewNotFoundError(provider string, resource string) *CloudtopError {
    return &CloudtopError{
        Type:      ErrorTypeNotFound,
        Provider:  provider,
        Message:   fmt.Sprintf("resource not found: %s", resource),
        Retryable: false,
    }
}

// ErrorHandler manages error handling strategies
type ErrorHandler struct {
    degradeGracefully bool
}

// NewErrorHandler creates a new error handler
func NewErrorHandler(degradeGracefully bool) *ErrorHandler {
    return &ErrorHandler{
        degradeGracefully: degradeGracefully,
    }
}

// Handle processes an error and returns whether to continue
func (h *ErrorHandler) Handle(err error) bool {
    if err == nil {
        return true
    }

    ctErr, ok := err.(*CloudtopError)
    if !ok {
        // Unknown error type
        return !h.degradeGracefully
    }

    switch ctErr.Type {
    case ErrorTypeAuth, ErrorTypePermission:
        // Fatal errors - always fail
        return false
    case ErrorTypeNetwork, ErrorTypeRateLimit:
        // Retryable errors - can continue in degraded mode
        return h.degradeGracefully
    case ErrorTypeNotFound:
        // Resource not found - can continue
        return true
    default:
        return h.degradeGracefully
    }
}
```

## Recommended Third-Party Libraries

```go
// In go.mod

require (
    // CLI framework
    github.com/spf13/cobra v1.8.0
    github.com/spf13/viper v1.18.2

    // Cloud provider SDKs
    github.com/cloudflare/cloudflare-go v0.86.0
    github.com/oracle/oci-go-sdk/v65 v65.60.0
    github.com/Azure/azure-sdk-for-go/sdk/azidentity v1.5.1
    github.com/Azure/azure-sdk-for-go/sdk/resourcemanager/compute/armcompute/v5 v5.4.0
    cloud.google.com/go/compute v1.23.4

    // Rate limiting
    golang.org/x/time v0.5.0

    // Retry with backoff
    github.com/cenkalti/backoff/v4 v4.2.1

    // Table output
    github.com/olekukonko/tablewriter v0.0.5

    // JSON schema validation
    github.com/xeipuuv/gojsonschema v1.2.0

    // Concurrent operations
    golang.org/x/sync v0.6.0

    // HTTP client with retry
    github.com/hashicorp/go-retryablehttp v0.7.5

    // Logging
    go.uber.org/zap v1.26.0

    // Configuration
    github.com/kelseyhightower/envconfig v1.4.0
)
```

## Sample cloudtop.json Configuration

```json
{
  "version": "1.0",
  "defaults": {
    "refresh_interval": "30s",
    "output_format": "table",
    "show_cached": true
  },
  "cache": {
    "enabled": true,
    "backend": "memory",
    "ttl": "5m",
    "max_size": 1000
  },
  "output": {
    "color_enabled": true,
    "timestamps": true,
    "columns": {
      "compute": ["name", "status", "cpu", "memory", "region"],
      "gpu": ["name", "gpu_type", "gpu_count", "utilization", "price"]
    }
  },
  "providers": {
    "cloudflare": {
      "enabled": true,
      "auth": {
        "method": "api_key",
        "env_api_key": "CLOUDFLARE_API_TOKEN"
      },
      "services": ["workers", "r2", "ai"],
      "rate_limit": {
        "requests_per_second": 4,
        "burst": 10,
        "timeout": "30s"
      }
    },
    "oracle": {
      "enabled": true,
      "auth": {
        "method": "service_account",
        "key_file": "~/.oci/config"
      },
      "regions": ["us-ashburn-1", "us-phoenix-1"],
      "services": ["compute", "containers", "autonomous_db"],
      "rate_limit": {
        "requests_per_second": 10,
        "burst": 20,
        "timeout": "30s"
      }
    },
    "azure": {
      "enabled": true,
      "auth": {
        "method": "service_account",
        "key_file": "~/.azure/credentials.json"
      },
      "services": ["vms", "aks", "functions"],
      "options": {
        "subscription_id": "your-subscription-id"
      }
    },
    "gcp": {
      "enabled": true,
      "auth": {
        "method": "service_account",
        "key_file": "~/.gcp/service-account.json"
      },
      "services": ["compute", "gke", "functions"],
      "options": {
        "project_id": "your-project-id"
      }
    },
    "neon": {
      "enabled": true,
      "auth": {
        "method": "api_key",
        "env_api_key": "NEON_API_KEY"
      }
    },
    "vastai": {
      "enabled": true,
      "auth": {
        "method": "api_key",
        "env_api_key": "VASTAI_API_KEY"
      }
    },
    "runpod": {
      "enabled": true,
      "auth": {
        "method": "api_key",
        "env_api_key": "RUNPOD_API_KEY"
      }
    }
  }
}
```

## Authentication Strategy

Each provider implements credential handling through the AuthConfig pattern:

1. **API Key Authentication** (Cloudflare, Neon, Vast.ai, RunPod):
   - Support both direct config and environment variables
   - Environment variable references preferred for security

2. **Service Account** (Oracle, Azure, GCP):
   - Use provider-specific key files
   - Support standard credential locations (~/.oci, ~/.azure, ~/.gcp)

3. **OAuth** (if needed):
   - Implement token refresh logic
   - Cache tokens with expiration

4. **Credential Chain**:
   - Priority: Environment variables → Config file → Default locations → Interactive prompt

## Rate Limiting Strategy

```go
package ratelimit

import (
    "context"
    "time"

    "golang.org/x/time/rate"
)

// Limiter wraps rate.Limiter with provider-specific config
type Limiter struct {
    limiter *rate.Limiter
    timeout time.Duration
}

// NewLimiter creates a rate limiter
func NewLimiter(requestsPerSecond float64, burst int, timeout time.Duration) *Limiter {
    return &Limiter{
        limiter: rate.NewLimiter(rate.Limit(requestsPerSecond), burst),
        timeout: timeout,
    }
}

// Wait blocks until request can proceed
func (l *Limiter) Wait(ctx context.Context) error {
    ctx, cancel := context.WithTimeout(ctx, l.timeout)
    defer cancel()
    return l.limiter.Wait(ctx)
}

// Allow returns true if request can proceed immediately
func (l *Limiter) Allow() bool {
    return l.limiter.Allow()
}
```

## Retry Strategy with Exponential Backoff

```go
package retry

import (
    "context"
    "time"

    "github.com/cenkalti/backoff/v4"
)

// Config defines retry parameters
type Config struct {
    MaxRetries      int
    InitialInterval time.Duration
    MaxInterval     time.Duration
    Multiplier      float64
}

// DefaultConfig returns sensible defaults
func DefaultConfig() Config {
    return Config{
        MaxRetries:      3,
        InitialInterval: 1 * time.Second,
        MaxInterval:     30 * time.Second,
        Multiplier:      2.0,
    }
}

// Do executes operation with retry logic
func Do(ctx context.Context, config Config, operation func() error) error {
    b := backoff.NewExponentialBackOff()
    b.InitialInterval = config.InitialInterval
    b.MaxInterval = config.MaxInterval
    b.Multiplier = config.Multiplier
    b.MaxElapsedTime = 0 // Rely on MaxRetries instead

    return backoff.Retry(operation, backoff.WithContext(
        backoff.WithMaxRetries(b, uint64(config.MaxRetries)),
        ctx,
    ))
}
```

## Plugin Architecture for New Providers

To add a new provider:

1. Create a new package under `internal/provider/<provider-name>/`
2. Implement the Provider interface (and any specialized interfaces)
3. Register the provider in an init() function:

```go
package newprovider

import "github.com/adsops/cloudtop/internal/provider"

func init() {
    provider.Register("newprovider", func() provider.Provider {
        return &NewProvider{}
    })
}

type NewProvider struct {
    // implementation
}

// Implement Provider interface methods...
```

4. Import the package in main.go to trigger registration:

```go
import (
    _ "github.com/adsops/cloudtop/internal/provider/newprovider"
)
```

This design provides:
- **Extensibility**: Easy to add new providers via plugin pattern
- **Concurrency**: Parallel API calls with proper error handling
- **Resilience**: Rate limiting, retry logic, and graceful degradation
- **Maintainability**: Clear separation of concerns, interface-driven design
- **Performance**: Caching layer with configurable backends
- **Security**: Multiple auth methods with environment variable support
- **Observability**: Structured errors with provider context

The architecture scales from single-provider queries to enterprise-wide multi-cloud monitoring.
