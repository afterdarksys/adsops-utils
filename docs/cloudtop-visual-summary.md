# Cloudtop Visual Architecture Summary

## High-Level System Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                            CLI Interface                                │
│  cloudtop --all --gpu --refresh 30s --json                             │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                         Command Parser                                  │
│  • Flag parsing (Cobra)                                                │
│  • Config loading (Viper)                                              │
│  • Provider selection                                                   │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                          Collector Layer                                │
│  • Orchestrates data collection                                        │
│  • Manages concurrency                                                 │
│  • Handles caching                                                     │
│  • Aggregates results                                                  │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
            ┌───────────────────────┴───────────────────────┐
            ▼                       ▼                       ▼
    ┌───────────────┐      ┌───────────────┐      ┌───────────────┐
    │  Cache Layer  │      │  Rate Limiter │      │  Retry Logic  │
    ├───────────────┤      ├───────────────┤      ├───────────────┤
    │ • Memory      │      │ • Token bucket│      │ • Exponential │
    │ • Redis       │      │ • Per-provider│      │   backoff     │
    │ • File        │      │ • Configurable│      │ • Max retries │
    └───────────────┘      └───────────────┘      └───────────────┘
                                    │
            ┌───────────────────────┴───────────────────────┐
            ▼                                               ▼
┌─────────────────────────────┐                 ┌─────────────────────────┐
│    Provider Registry        │                 │   Error Handler         │
│  • Factory pattern          │                 │  • Graceful degradation │
│  • Plugin architecture      │                 │  • Error categorization │
│  • Auto-registration        │                 │  • Retry decisions      │
└─────────────────────────────┘                 └─────────────────────────┘
                │
    ┌───────────┴──────────┬──────────┬──────────┬──────────┬──────────┐
    ▼                      ▼          ▼          ▼          ▼          ▼
┌─────────┐          ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐
│Cloudflare│          │ Oracle  │ │  Azure  │ │   GCP   │ │  Neon   │ │ Vast.ai │
│Provider │          │ Provider│ │ Provider│ │ Provider│ │ Provider│ │ Provider│
├─────────┤          ├─────────┤ ├─────────┤ ├─────────┤ ├─────────┤ ├─────────┤
│Workers  │          │Compute  │ │   VMs   │ │Compute  │ │Postgres │ │GPU Rent │
│R2       │          │GPU      │ │  AKS    │ │  GKE    │ │Serverless│ │Pricing  │
│AI       │          │Containers│ │Functions│ │Functions│ │         │ │Avail.   │
└─────────┘          └─────────┘ └─────────┘ └─────────┘ └─────────┘ └─────────┘
    │                      │          │          │          │          │
    └──────────────────────┴──────────┴──────────┴──────────┴──────────┘
                                    │
                                    ▼
                        ┌───────────────────────┐
                        │   Metrics Aggregator  │
                        │  • CPU, Memory, Net   │
                        │  • GPU utilization    │
                        │  • Database metrics   │
                        │  • Function metrics   │
                        └───────────────────────┘
                                    │
                                    ▼
                        ┌───────────────────────┐
                        │  Output Formatters    │
                        ├───────────────────────┤
                        │ • Table               │
                        │ • Wide Table          │
                        │ • JSON                │
                        └───────────────────────┘
                                    │
                                    ▼
                            [Terminal Output]
```

## Data Flow Diagram

```
User Command
    │
    ├─→ Parse Flags ──→ Load Config ──→ Validate Credentials
    │                                            │
    ▼                                            ▼
Select Providers                        Initialize Providers
    │                                            │
    ▼                                            ▼
Build Request ────────────────────────→  Create Collector
    │                                            │
    ▼                                            ▼
┌────────────────────────────────────────────────────────┐
│              CONCURRENT COLLECTION PHASE               │
│                                                        │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐            │
│  │Provider 1│  │Provider 2│  │Provider N│            │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘            │
│       │             │             │                   │
│  Check Cache   Check Cache   Check Cache             │
│       │             │             │                   │
│  [Cache Hit?] [Cache Hit?] [Cache Hit?]              │
│    Yes│  No     Yes│  No     Yes│  No                │
│       │   │        │   │        │   │                │
│    Return │     Return │     Return │                │
│       │   │        │   │        │   │                │
│       │   └→ Rate  │   └→ Rate  │   └→ Rate          │
│       │      Limit │      Limit │      Limit         │
│       │         │  │         │  │         │          │
│       │         ▼  │         ▼  │         ▼          │
│       │      API   │      API   │      API           │
│       │      Call  │      Call  │      Call          │
│       │         │  │         │  │         │          │
│       │    [Success?]  [Success?]  [Success?]        │
│       │     Yes│ No   Yes│ No   Yes│ No              │
│       │        │  │      │  │      │  │              │
│       │        │  └─Retry│  └─Retry│  └─Retry        │
│       │        │         │         │                 │
│       └────────┴─────────┴─────────┴─────────────────┤
│                          │                           │
│                     Cache Results                    │
│                          │                           │
└──────────────────────────┼───────────────────────────┘
                           │
                           ▼
                    Aggregate Results
                           │
                ┌──────────┴──────────┐
                ▼                     ▼
          Successful Results    Failed Providers
                │                     │
                └──────────┬──────────┘
                           ▼
                    Format Output
                           │
                           ▼
                    Display to User
```

## Provider Interface Hierarchy

```
┌─────────────────────────────────────────────────────────────┐
│                      Provider (Base)                        │
├─────────────────────────────────────────────────────────────┤
│ • Name() string                                            │
│ • Initialize(ctx, config) error                           │
│ • HealthCheck(ctx) error                                  │
│ • ListServices(ctx) ([]Service, error)                   │
│ • GetMetrics(ctx, req) (*MetricsResponse, error)         │
│ • ListResources(ctx, filter) ([]Resource, error)         │
│ • Close() error                                           │
└─────────────────────────────────────────────────────────────┘
                           │
        ┌──────────────────┴──────────────────┬──────────────┐
        ▼                                     ▼              ▼
┌────────────────┐                  ┌────────────────┐  ┌──────────────┐
│ComputeProvider │                  │ GPUProvider    │  │DBProvider    │
├────────────────┤                  ├────────────────┤  ├──────────────┤
│ Extends Base   │                  │ Extends Base   │  │ Extends Base │
├────────────────┤                  ├────────────────┤  ├──────────────┤
│ListInstances() │                  │ListGPUInstances│  │ListDatabases │
│GetInstanceMetrics                 │GetGPUMetrics   │  │GetDBMetrics  │
└────────────────┘                  │GetGPUAvailability └──────────────┘
        │                           └────────────────┘
        │                                    │
        ▼                                    ▼
┌─────────────────────────────────┐  ┌──────────────────────────────┐
│    Cloudflare Provider          │  │     Oracle Provider          │
├─────────────────────────────────┤  ├──────────────────────────────┤
│ Implements: Provider            │  │ Implements: Provider         │
│            ServerlessProvider   │  │            ComputeProvider   │
│            StorageProvider      │  │            GPUProvider       │
├─────────────────────────────────┤  │            DatabaseProvider  │
│ • Workers                       │  ├──────────────────────────────┤
│ • R2 Buckets                    │  │ • Compute Instances          │
│ • D1 Databases                  │  │ • GPU Instances (A10, A100)  │
│ • KV Namespaces                 │  │ • Container Engine           │
│ • AI Models                     │  │ • Autonomous Database        │
└─────────────────────────────────┘  └──────────────────────────────┘
```

## Concurrency Pattern

```
Main Thread
    │
    ├─→ Create Collector
    │
    ├─→ Build Request with Provider List
    │       [cloudflare, oracle, azure, gcp, neon, vastai, runpod]
    │
    └─→ collector.Collect(ctx, request)
            │
            ├─→ Create Goroutine Pool (WaitGroup + Mutex)
            │
            ├─→ For Each Provider:
            │       │
            │       ├─→ Spawn Goroutine
            │       │       │
            │       │       ├─→ Check Cache (Lock-Free Read)
            │       │       │       │
            │       │       │       ├─→ [Cache Hit] → Return Immediately
            │       │       │       │
            │       │       │       └─→ [Cache Miss] → Continue
            │       │       │
            │       │       ├─→ Wait for Rate Limiter Token
            │       │       │
            │       │       ├─→ Execute API Call
            │       │       │       │
            │       │       │       ├─→ [Success] → Cache Result
            │       │       │       │
            │       │       │       └─→ [Error] → Retry Logic
            │       │       │               │
            │       │       │               ├─→ Network Error → Retry
            │       │       │               ├─→ Rate Limit → Backoff
            │       │       │               └─→ Auth Error → Fail
            │       │       │
            │       │       └─→ Store Result (Mutex Protected)
            │       │
            │       └─→ WaitGroup.Done()
            │
            ├─→ WaitGroup.Wait() [Block until all complete]
            │
            └─→ Return Aggregated Results
                    │
                    ├─→ Successful Results Map
                    └─→ Error Map (per provider)
```

## Rate Limiting Flow

```
API Request
    │
    ▼
┌──────────────────────┐
│   Rate Limiter       │
│  (Token Bucket)      │
├──────────────────────┤
│ Rate: 4 req/sec      │
│ Burst: 10 tokens     │
│ Timeout: 30s         │
└──────────────────────┘
    │
    ├─→ Check Token Availability
    │       │
    │       ├─→ [Tokens Available]
    │       │       │
    │       │       ├─→ Consume Token
    │       │       └─→ Execute Request
    │       │
    │       └─→ [No Tokens]
    │               │
    │               ├─→ Wait for Token Refill
    │               │       │
    │               │       ├─→ [Token Available] → Execute
    │               │       │
    │               │       └─→ [Timeout Exceeded] → Error
    │               │
    │               └─→ Return Rate Limit Error
    │
    ▼
API Call Result
    │
    ├─→ [429 Too Many Requests]
    │       │
    │       └─→ Exponential Backoff
    │               │
    │               ├─→ Wait: 1s → 2s → 4s → 8s
    │               └─→ Retry (Max 3 attempts)
    │
    └─→ [Success] → Return Data
```

## Cache Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                      Cache Interface                        │
├─────────────────────────────────────────────────────────────┤
│ • Get(key string) (interface{}, bool)                      │
│ • Set(key string, value interface{})                       │
│ • Delete(key string)                                       │
│ • Clear()                                                  │
└─────────────────────────────────────────────────────────────┘
                           │
        ┌──────────────────┴──────────────────┐
        ▼                                     ▼
┌────────────────────┐              ┌────────────────────┐
│   Memory Cache     │              │   Redis Cache      │
├────────────────────┤              ├────────────────────┤
│ • In-process       │              │ • Distributed      │
│ • Fast (10µs)      │              │ • Shared state     │
│ • TTL support      │              │ • Persistent       │
│ • LRU eviction     │              │ • ~1ms latency     │
│ • Max size limit   │              │ • Pub/sub support  │
└────────────────────┘              └────────────────────┘

Cache Key Generation:
    provider:service:filter:hash
    ↓
    Example: "cloudflare:workers:all:a3f5c2d1"

Cache Entry Structure:
    {
        "key": "cloudflare:workers:all:a3f5c2d1",
        "value": {
            "provider": "cloudflare",
            "resources": [...],
            "metrics": {...}
        },
        "expiration": "2025-01-01T12:35:00Z",
        "created": "2025-01-01T12:30:00Z"
    }
```

## Authentication Flow

```
┌─────────────────────────────────────────────────────────────┐
│                   Authentication Strategy                   │
└─────────────────────────────────────────────────────────────┘
                           │
        ┌──────────────────┼──────────────────┬──────────────┐
        ▼                  ▼                  ▼              ▼
┌───────────────┐  ┌───────────────┐  ┌──────────────┐  ┌─────────┐
│   API Key     │  │Service Account│  │    OAuth     │  │   Env   │
├───────────────┤  ├───────────────┤  ├──────────────┤  ├─────────┤
│ • Cloudflare  │  │ • Oracle OCI  │  │ • Azure AD   │  │ • All   │
│ • Neon        │  │ • GCP         │  │ • Google     │  │ providers│
│ • Vast.ai     │  │ • Azure       │  │   OAuth      │  │ if set  │
│ • RunPod      │  │               │  │              │  │         │
└───────────────┘  └───────────────┘  └──────────────┘  └─────────┘
        │                  │                  │              │
        ▼                  ▼                  ▼              ▼
┌─────────────────────────────────────────────────────────────┐
│              Credential Resolution Order                    │
├─────────────────────────────────────────────────────────────┤
│ 1. Environment Variable (highest priority)                 │
│ 2. Config File                                             │
│ 3. Default Location (~/.oci/config, ~/.azure/*, etc.)     │
│ 4. Interactive Prompt (if allowed)                         │
└─────────────────────────────────────────────────────────────┘
```

## Metrics Collection Pipeline

```
Resource Discovery
        │
        ▼
┌────────────────────────────────────────────────────┐
│         ListResources(filter)                      │
│  Returns: [Instance1, Instance2, ...]             │
└────────────────────────────────────────────────────┘
        │
        ▼
For Each Resource
        │
        ├─→ GetMetrics(resourceID, metricNames)
        │       │
        │       ▼
        │   ┌────────────────────────────────┐
        │   │    Provider Metrics API        │
        │   ├────────────────────────────────┤
        │   │ • Query last 5 minutes         │
        │   │ • Granularity: 1 minute        │
        │   │ • Aggregate: avg/max/min       │
        │   └────────────────────────────────┘
        │       │
        │       ▼
        │   Transform to Standard Format
        │       │
        │       ├─→ ComputeMetrics
        │       │   • CPU%
        │       │   • Memory%
        │       │   • Disk I/O
        │       │   • Network I/O
        │       │
        │       ├─→ GPUMetrics
        │       │   • GPU Utilization%
        │       │   • GPU Memory%
        │       │   • Temperature
        │       │   • Power Usage
        │       │
        │       ├─→ FunctionMetrics
        │       │   • Invocations
        │       │   • Duration
        │       │   • Errors
        │       │
        │       └─→ DatabaseMetrics
        │           • Connections
        │           • QPS
        │           • Replication Lag
        │
        └─→ Aggregate All Metrics
                │
                ▼
        ┌────────────────────────────────┐
        │   Combined Metrics Response    │
        ├────────────────────────────────┤
        │ {                              │
        │   "provider": "oracle",        │
        │   "resources": [...],          │
        │   "metrics": {                 │
        │     "inst-1": {...},           │
        │     "inst-2": {...}            │
        │   }                            │
        │ }                              │
        └────────────────────────────────┘
```

## Output Formatting Pipeline

```
Aggregated Results
        │
        ▼
┌──────────────────────────┐
│   Format Selection       │
├──────────────────────────┤
│ • --table (default)      │
│ • --wide                 │
│ • --json                 │
└──────────────────────────┘
        │
        ├─→ [Table Format]
        │       │
        │       ├─→ Group by Provider
        │       │
        │       ├─→ Create Table per Provider
        │       │       │
        │       │       ├─→ Headers: [Name, Status, CPU%, Memory%]
        │       │       │
        │       │       ├─→ Rows: Resource data
        │       │       │
        │       │       └─→ Format: ASCII table
        │       │
        │       └─→ Combine Tables
        │
        ├─→ [Wide Format]
        │       │
        │       └─→ Extended Columns
        │               [ID, Name, Type, Region, Status, CPU%,
        │                Memory%, Network In, Network Out, Created]
        │
        └─→ [JSON Format]
                │
                └─→ Structured JSON
                        {
                          "timestamp": "...",
                          "duration": "...",
                          "providers": {
                            "cloudflare": {
                              "resources": [...],
                              "metrics": {...},
                              "cached": false
                            }
                          },
                          "errors": {}
                        }
```

## Error Handling Decision Tree

```
Error Occurs
    │
    ▼
Categorize Error Type
    │
    ├─→ [Authentication Error]
    │       │
    │       ├─→ Log Error
    │       ├─→ Mark Provider as Failed
    │       └─→ Do NOT Retry
    │
    ├─→ [Rate Limit Error]
    │       │
    │       ├─→ Log Warning
    │       ├─→ Extract Retry-After Header
    │       ├─→ Wait (Retry-After or Exponential Backoff)
    │       └─→ Retry (up to 3 times)
    │
    ├─→ [Network Error]
    │       │
    │       ├─→ Log Warning
    │       ├─→ Exponential Backoff (1s → 2s → 4s)
    │       └─→ Retry (up to 3 times)
    │
    ├─→ [Not Found Error]
    │       │
    │       ├─→ Log Debug
    │       └─→ Continue (resource may have been deleted)
    │
    ├─→ [Permission Error]
    │       │
    │       ├─→ Log Warning
    │       ├─→ Mark Resource as Inaccessible
    │       └─→ Continue with Other Resources
    │
    └─→ [Unknown Error]
            │
            ├─→ Log Error
            ├─→ Increment Error Counter
            └─→ [Graceful Degradation Enabled?]
                    │
                    ├─→ Yes: Continue with Other Providers
                    └─→ No: Fail Fast
```

This visual summary provides a comprehensive overview of the cloudtop architecture, making it easy to understand how all components interact at enterprise scale.
