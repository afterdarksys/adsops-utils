# Cloudtop Usage Examples and Quick Reference

## Quick Start

### Installation

```bash
# macOS (Homebrew)
brew install cloudtop

# Linux (snap)
snap install cloudtop

# From source
git clone https://github.com/yourusername/cloudtop.git
cd cloudtop
make install

# Docker
docker pull yourregistry/cloudtop:latest
```

### Initial Configuration

```bash
# Create config file
mkdir -p ~/.config/cloudtop
cat > ~/.config/cloudtop/config.json <<EOF
{
  "version": "1.0",
  "providers": {
    "cloudflare": {
      "enabled": true,
      "auth": {
        "method": "api_key",
        "env_api_key": "CLOUDFLARE_API_TOKEN"
      }
    }
  }
}
EOF

# Set environment variables
export CLOUDFLARE_API_TOKEN="your-cloudflare-token"
export ORACLE_CONFIG_FILE="~/.oci/config"
export AZURE_CREDENTIALS="~/.azure/credentials.json"
export GCP_SERVICE_ACCOUNT="~/.gcp/service-account.json"
export NEON_API_KEY="your-neon-api-key"
export VASTAI_API_KEY="your-vastai-api-key"
export RUNPOD_API_KEY="your-runpod-api-key"
```

## Basic Usage Examples

### 1. View All Resources Across All Providers

```bash
# Show all resources from all enabled providers
cloudtop --all

# Output:
# === CLOUDFLARE ===
# ┌──────────────────────┬────────┬──────────┬──────┬─────────┐
# │ NAME                 │ STATUS │ REGION   │ CPU% │ MEMORY% │
# ├──────────────────────┼────────┼──────────┼──────┼─────────┤
# │ api-worker           │ active │ global   │ 12.3 │ 45.2    │
# │ auth-worker          │ active │ global   │ 8.7  │ 32.1    │
# └──────────────────────┴────────┴──────────┴──────┴─────────┘
#
# === ORACLE ===
# ┌──────────────────────┬─────────┬──────────────┬──────┬─────────┐
# │ NAME                 │ STATUS  │ REGION       │ CPU% │ MEMORY% │
# ├──────────────────────┼─────────┼──────────────┼──────┼─────────┤
# │ web-server-01        │ running │ us-ashburn-1 │ 45.6 │ 67.8    │
# │ db-server-01         │ running │ us-phoenix-1 │ 23.4 │ 78.9    │
# └──────────────────────┴─────────┴──────────────┴──────┴─────────┘
```

### 2. View Specific Provider Resources

```bash
# Cloudflare only
cloudtop --cloudflare

# Oracle Cloud only
cloudtop --oracle

# Multiple providers
cloudtop --cloudflare --oracle --gcp

# Using shorthand
cloudtop -c -o -g
```

### 3. Filter by Service Type

```bash
# Show only compute instances
cloudtop --all --service compute

# Show only storage
cloudtop --all --service storage

# Show only databases
cloudtop --all --service database

# Show only serverless functions
cloudtop --all --service functions
```

### 4. GPU-Specific Queries

```bash
# Show all GPU instances across all providers
cloudtop --all --gpu

# Show GPU availability and pricing
cloudtop --all --gpu --list

# Filter by AI provider
cloudtop --ai vast
cloudtop --ai io      # RunPod
cloudtop --ai cf      # Cloudflare AI
cloudtop --ai oracle  # Oracle GPU instances

# Show GPU instances with specific filters
cloudtop --oracle --gpu --running
```

### 5. Filter Running vs All Resources

```bash
# Show only running instances
cloudtop --all --running

# Show all resources (including stopped)
cloudtop --all --all-resources

# Filter by provider
cloudtop --provider oracle --running
```

### 6. Output Formats

```bash
# Default table format
cloudtop --all --table

# Wide format (more columns)
cloudtop --all --wide

# JSON format (for scripting)
cloudtop --all --json

# JSON with pretty printing
cloudtop --all --json | jq .
```

### 7. Auto-Refresh Mode

```bash
# Refresh every 30 seconds
cloudtop --all --refresh 30s

# Refresh every 1 minute
cloudtop --all --refresh 1m

# Refresh every 5 minutes
cloudtop --all --refresh 5m
```

## Advanced Usage Examples

### 8. Multi-Cloud Resource Discovery

```bash
# Find all running compute instances across clouds
cloudtop --all --service compute --running --wide

# Example output:
# ┌────────────┬──────────────────┬─────────┬──────────────┬────────┬──────┬─────────┬────────────┬─────────────┐
# │ PROVIDER   │ NAME             │ STATUS  │ REGION       │ TYPE   │ CPU% │ MEMORY% │ NETWORK IN │ NETWORK OUT │
# ├────────────┼──────────────────┼─────────┼──────────────┼────────┼──────┼─────────┼────────────┼─────────────┤
# │ oracle     │ web-server-01    │ running │ us-ashburn-1 │ VM.GPU3│ 45.6 │ 67.8    │ 1.2 GB/s   │ 890 MB/s    │
# │ azure      │ app-server-01    │ running │ eastus       │ D4s_v3 │ 34.2 │ 56.7    │ 450 MB/s   │ 320 MB/s    │
# │ gcp        │ api-server-01    │ running │ us-central1  │ n1-std │ 23.1 │ 45.6    │ 234 MB/s   │ 189 MB/s    │
# └────────────┴──────────────────┴─────────┴──────────────┴────────┴──────┴─────────┴────────────┴─────────────┘
```

### 9. GPU Price Comparison

```bash
# Compare GPU pricing across providers
cloudtop --ai vast --ai io --ai oracle --gpu --list --json | jq -r '
  .providers[].offerings[] |
  select(.available == true) |
  "\(.provider) \(.gpu_type) x\(.gpu_count) - $\(.price_per_hour)/hr - \(.region)"
' | sort -k6 -n

# Example output:
# vastai RTX_3090 x1 - $0.18/hr - us-west
# runpod RTX_3090 x1 - $0.24/hr - us-ca-1
# oracle A10 x1 - $0.89/hr - us-ashburn-1
# vastai A100_40GB x1 - $1.28/hr - eu-de
# oracle A100_80GB x1 - $2.95/hr - us-phoenix-1
```

### 10. Resource Cost Analysis

```bash
# Get JSON output and calculate costs
cloudtop --all --running --json | jq '
  .providers[] |
  .results[] |
  select(.resources[].type == "compute") |
  {
    provider: .provider,
    instances: [.resources[] | {name: .name, type: .instance_type}],
    count: (.resources | length)
  }
'

# Example output:
# {
#   "provider": "oracle",
#   "instances": [
#     {"name": "web-server-01", "type": "VM.Standard.E4.Flex"},
#     {"name": "db-server-01", "type": "VM.Standard.E4.Flex"}
#   ],
#   "count": 2
# }
```

### 11. Finding Available GPU Resources

```bash
# Find all available A100 GPUs
cloudtop --all --gpu --list --json | jq -r '
  .providers[].offerings[] |
  select(.gpu_type | contains("A100")) |
  select(.available == true) |
  "\(.provider): \(.gpu_type) x\(.gpu_count) @ $\(.price_per_hour)/hr in \(.region)"
'

# Example output:
# vastai: A100_40GB x1 @ $1.28/hr in us-west
# runpod: A100_80GB x1 @ $1.89/hr in us-nj-1
# oracle: A100_80GB x8 @ $19.60/hr in us-phoenix-1
```

### 12. Monitoring Specific Resources

```bash
# Watch specific provider with auto-refresh
cloudtop --oracle --service compute --refresh 10s --wide

# Monitor GPU utilization
cloudtop --oracle --gpu --refresh 5s

# Monitor serverless functions
cloudtop --cloudflare --service workers --refresh 30s
```

### 13. Database Monitoring

```bash
# View all databases
cloudtop --neon --oracle --azure --service database

# Neon-specific monitoring
cloudtop --neon --wide

# Example output:
# === NEON ===
# ┌──────────────────────┬────────┬──────────┬─────────┬─────────────┬───────────┐
# │ NAME                 │ STATUS │ REGION   │ SIZE GB │ CONNECTIONS │ QPS       │
# ├──────────────────────┼────────┼──────────┼─────────┼─────────────┼───────────┤
# │ production-db        │ active │ us-east-1│ 45.6    │ 23/100      │ 1234.5    │
# │ staging-db           │ active │ us-west-2│ 12.3    │ 5/50        │ 89.2      │
# └──────────────────────┴────────┴──────────┴─────────┴─────────────┴───────────┘
```

### 14. Serverless Function Monitoring

```bash
# Monitor Cloudflare Workers
cloudtop --cloudflare --service workers --wide

# Monitor Azure Functions
cloudtop --azure --service functions --wide

# Monitor GCP Cloud Functions
cloudtop --gcp --service functions --wide

# Combined view
cloudtop --cloudflare --azure --gcp --service functions --json
```

### 15. Storage Usage Monitoring

```bash
# View Cloudflare R2 buckets
cloudtop --cloudflare --service r2

# View all storage across providers
cloudtop --all --service storage --wide

# Example output:
# ┌──────────┬──────────────────┬────────┬──────────┬────────────┬──────────────┐
# │ PROVIDER │ NAME             │ STATUS │ SIZE     │ OBJECTS    │ STORAGE CLASS│
# ├──────────┼──────────────────┼────────┼──────────┼────────────┼──────────────┤
# │ cf       │ cdn-assets       │ active │ 123.4 GB │ 45,678     │ standard     │
# │ cf       │ user-uploads     │ active │ 567.8 GB │ 123,456    │ standard     │
# └──────────┴──────────────────┴────────┴──────────┴────────────┴──────────────┘
```

## Scripting and Automation

### 16. CI/CD Integration

```bash
#!/bin/bash
# check-resources.sh - Verify resources are running

set -e

echo "Checking production resources..."

# Get running instances
RUNNING=$(cloudtop --oracle --running --json | jq -r '.providers[].results[].resources | length')

if [ "$RUNNING" -lt 2 ]; then
    echo "ERROR: Expected at least 2 running instances, found $RUNNING"
    exit 1
fi

echo "✓ All production resources running"
```

### 17. Cost Monitoring Script

```bash
#!/bin/bash
# monitor-costs.sh - Track cloud costs

OUTPUT=$(cloudtop --all --running --json)

echo "Cloud Resource Summary:"
echo "======================"

# Count resources by provider
echo "$OUTPUT" | jq -r '
  .providers[] |
  "\(.provider): \(.results[].resources | length) resources"
'

# GPU instances
echo ""
echo "GPU Instances:"
GPU_COUNT=$(echo "$OUTPUT" | jq '[.providers[].results[].resources[] | select(.type | contains("gpu"))] | length')
echo "Total GPU instances: $GPU_COUNT"
```

### 18. Alert on High Resource Usage

```bash
#!/bin/bash
# alert-high-usage.sh - Alert on high CPU/memory

THRESHOLD=80

cloudtop --all --running --json | jq -r "
  .providers[].results[].resources[] |
  select(.metrics.cpu_usage_percent > $THRESHOLD or .metrics.memory_usage_percent > $THRESHOLD) |
  \"ALERT: \(.provider)/\(.name) - CPU: \(.metrics.cpu_usage_percent)% Memory: \(.metrics.memory_usage_percent)%\"
"
```

### 19. Resource Inventory Export

```bash
#!/bin/bash
# export-inventory.sh - Export resource inventory

TIMESTAMP=$(date +%Y%m%d_%H%M%S)
OUTPUT_FILE="inventory_${TIMESTAMP}.json"

cloudtop --all --all-resources --json > "$OUTPUT_FILE"

echo "Inventory exported to $OUTPUT_FILE"

# Generate CSV summary
jq -r '
  ["Provider","Name","Type","Region","Status"] |
  @csv
' "$OUTPUT_FILE" > "inventory_${TIMESTAMP}.csv"

cloudtop --all --all-resources --json | jq -r '
  .providers[].results[].resources[] |
  [.provider, .name, .type, .region, .status] |
  @csv
' >> "inventory_${TIMESTAMP}.csv"

echo "CSV summary: inventory_${TIMESTAMP}.csv"
```

### 20. Find Unused Resources

```bash
#!/bin/bash
# find-unused.sh - Find stopped/idle resources

echo "Stopped Instances:"
cloudtop --all --all-resources --json | jq -r '
  .providers[].results[].resources[] |
  select(.status == "stopped" or .status == "terminated") |
  "\(.provider): \(.name) (\(.type)) - Status: \(.status)"
'

echo ""
echo "Low CPU Usage (< 5%):"
cloudtop --all --running --json | jq -r '
  .providers[].results[].resources[] |
  select(.metrics.cpu_usage_percent < 5) |
  "\(.provider): \(.name) - CPU: \(.metrics.cpu_usage_percent)%"
'
```

## Configuration Examples

### 21. Multi-Environment Configuration

```bash
# Production config
cat > ~/.config/cloudtop/production.json <<EOF
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
    "ttl": "10m"
  },
  "providers": {
    "oracle": {
      "enabled": true,
      "auth": {
        "method": "service_account",
        "key_file": "~/.oci/config"
      },
      "regions": ["us-ashburn-1", "us-phoenix-1"]
    }
  }
}
EOF

# Use specific config
cloudtop --config ~/.config/cloudtop/production.json --all
```

### 22. Development Configuration

```bash
cat > ~/.config/cloudtop/development.json <<EOF
{
  "version": "1.0",
  "defaults": {
    "refresh_interval": "10s",
    "output_format": "table",
    "show_cached": true
  },
  "cache": {
    "enabled": true,
    "backend": "memory",
    "ttl": "2m",
    "max_size": 100
  },
  "providers": {
    "cloudflare": {
      "enabled": true,
      "auth": {
        "method": "api_key",
        "env_api_key": "CLOUDFLARE_API_TOKEN_DEV"
      }
    }
  }
}
EOF
```

## Troubleshooting Commands

### 23. Verify Provider Connectivity

```bash
# Test each provider individually
for provider in cloudflare oracle azure gcp neon; do
    echo "Testing $provider..."
    cloudtop --provider "$provider" --list 2>&1 | head -n 5
    echo ""
done
```

### 24. Debug Mode

```bash
# Enable verbose logging
export CLOUDTOP_LOG_LEVEL=debug
cloudtop --all

# Check configuration
cloudtop --config ~/.config/cloudtop/config.json --dry-run

# Validate credentials
cloudtop --validate-credentials
```

### 25. Performance Benchmarking

```bash
# Measure collection time
time cloudtop --all --json > /dev/null

# Compare cache performance
echo "Without cache:"
time cloudtop --all --no-cache --json > /dev/null

echo "With cache:"
time cloudtop --all --json > /dev/null
time cloudtop --all --json > /dev/null  # Should be much faster
```

## Common Workflows

### 26. Morning Resource Check

```bash
#!/bin/bash
# morning-check.sh - Daily resource health check

echo "Daily Cloud Resource Report - $(date)"
echo "======================================"
echo ""

echo "Running Instances:"
cloudtop --all --running --table

echo ""
echo "GPU Utilization:"
cloudtop --all --gpu --running --table

echo ""
echo "Database Status:"
cloudtop --all --service database --table

echo ""
echo "Potential Issues:"
cloudtop --all --running --json | jq -r '
  .providers[].results[].resources[] |
  select(.metrics.cpu_usage_percent > 80 or .metrics.memory_usage_percent > 80) |
  "⚠️  \(.provider)/\(.name): CPU \(.metrics.cpu_usage_percent)% MEM \(.metrics.memory_usage_percent)%"
'
```

### 27. Pre-Deployment Verification

```bash
#!/bin/bash
# pre-deploy-check.sh - Verify infrastructure before deployment

echo "Pre-deployment infrastructure check..."

# Check database is running
DB_STATUS=$(cloudtop --neon --json | jq -r '.providers[].results[].resources[] | select(.name == "production-db") | .status')

if [ "$DB_STATUS" != "active" ]; then
    echo "❌ Production database is not active"
    exit 1
fi

# Check compute capacity
RUNNING=$(cloudtop --oracle --running --json | jq -r '.providers[].results[].resources | length')

if [ "$RUNNING" -lt 2 ]; then
    echo "❌ Insufficient compute capacity"
    exit 1
fi

echo "✅ Infrastructure ready for deployment"
```

### 28. Cost Optimization Workflow

```bash
#!/bin/bash
# cost-optimization.sh - Find cost optimization opportunities

echo "Cost Optimization Opportunities:"
echo "================================"

# Find stopped instances
echo ""
echo "1. Stopped Instances (can be deleted):"
cloudtop --all --all-resources --json | jq -r '
  .providers[].results[].resources[] |
  select(.status == "stopped") |
  "   \(.provider): \(.name) (\(.type))"
'

# Find underutilized instances
echo ""
echo "2. Underutilized Instances (< 20% CPU):"
cloudtop --all --running --json | jq -r '
  .providers[].results[].resources[] |
  select(.metrics.cpu_usage_percent < 20) |
  "   \(.provider): \(.name) - CPU: \(.metrics.cpu_usage_percent)%"
'

# Find cheaper GPU alternatives
echo ""
echo "3. GPU Cost Optimization:"
cloudtop --ai vast --ai io --gpu --list --json | jq -r '
  .providers[].offerings[] |
  select(.available == true) |
  select(.price_per_hour < 1.0) |
  "   \(.provider): \(.gpu_type) x\(.gpu_count) @ $\(.price_per_hour)/hr"
' | sort -k4 -n
```

## Quick Reference

### Command Syntax
```
cloudtop [flags]

Flags:
  -c, --cloudflare       Show Cloudflare resources
  -o, --oracle          Show Oracle Cloud resources
      --azure           Show Azure resources
  -g, --gcp             Show GCP resources
  -n, --neon            Show Neon databases
  -a, --all             Show all providers
  -s, --service string  Filter by service type
      --ai string       Show AI workloads (vast|io|cf|oracle)
      --gpu             Show GPU information
      --list            List available resources
      --provider string Filter by provider
      --running         Show only running resources
      --all-resources   Show all resources
      --table           Output in table format
      --wide            Output in wide table format
      --json            Output in JSON format
      --refresh duration Auto-refresh interval
      --config string   Config file path
```

### Environment Variables
```bash
CLOUDFLARE_API_TOKEN       # Cloudflare API token
ORACLE_CONFIG_FILE         # Oracle OCI config file
AZURE_CREDENTIALS          # Azure credentials file
GCP_SERVICE_ACCOUNT        # GCP service account file
NEON_API_KEY              # Neon API key
VASTAI_API_KEY            # Vast.ai API key
RUNPOD_API_KEY            # RunPod API key
CLOUDTOP_LOG_LEVEL        # Log level (debug|info|warn|error)
CLOUDTOP_CONFIG           # Default config file
```

### Exit Codes
- 0: Success
- 1: General error
- 2: Authentication error
- 3: Configuration error
- 4: Network error
- 5: Rate limit exceeded

This comprehensive usage guide covers everything from basic operations to advanced automation workflows for cloudtop.
