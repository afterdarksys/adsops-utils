# Host Management Tools - Quick Start Guide

## Installation

```bash
cd /Users/ryan/development/adsops-utils
./deploy-hostmgmt.sh
```

Or for production:

```bash
rsync -avz -e "ssh -i ~/.ssh/darkapi_key" \
  /Users/ryan/development/adsops-utils/ \
  opc@132.145.179.230:/tmp/adsops-utils/

ssh -i ~/.ssh/darkapi_key opc@132.145.179.230
cd /tmp/adsops-utils && sudo ./deploy-hostmgmt.sh
```

## Configuration

Set environment variables:

```bash
export POSTGRES_HOST=darkapi-postgres
export POSTGRES_PORT=5432
export POSTGRES_DB=inventory
export POSTGRES_USER=inventory_user
export POSTGRES_PASSWORD=your_secure_password
```

## Common Commands

### SSH Key Tracker

```bash
# Add SSH key mapping
ssh-key-tracker add darkapi-api-1 132.145.179.230 opc ~/.ssh/darkapi_key "API Proxy"

# List all mappings
ssh-key-tracker list

# Get key for a host
ssh-key-tracker get darkapi-api-1

# Test connection
ssh-key-tracker test darkapi-api-1

# Auto-discover working key
ssh-key-tracker scan new-server 10.0.1.100
```

### Host Control (hostctl)

```bash
# Add a host
hostctl add darkapi-api-1 \
  --ip 132.145.179.230 \
  --private-ip 10.0.1.71 \
  --type application_server \
  --env production \
  --tags "apiproxy,krakend"

# List all hosts
hostctl list

# Filter by status/environment
hostctl list --status active
hostctl list --env production

# Change status
hostctl status darkapi-api-1 blackout
hostctl status darkapi-api-1 active

# Show details
hostctl show darkapi-api-1

# Update host
hostctl update darkapi-api-1 --ip 10.0.1.100

# Remove host
hostctl remove old-server
```

### Blackout Management

```bash
# Start maintenance blackout
blackout start CHG-2026-001 darkapi-api-1 2:00 "Database upgrade"

# List active blackouts
blackout list --active

# Show blackout for host
blackout show darkapi-api-1

# Extend blackout
blackout extend darkapi-api-1 30m

# End blackout
blackout end darkapi-api-1

# Export for monitoring
blackout export

# Cleanup expired
blackout cleanup
```

## Typical Workflows

### New Host Setup

```bash
# 1. Add to inventory
hostctl add new-server --ip 10.0.1.100 --type app_server --env production

# 2. Discover SSH key
ssh-key-tracker scan new-server 10.0.1.100

# 3. Mark as build during setup
hostctl status new-server build

# 4. Complete setup...

# 5. Mark as active
hostctl status new-server active
```

### Scheduled Maintenance

```bash
# 1. Start blackout (suppresses alerts)
blackout start CHG-2026-001 darkapi-api-1 2:00 "Patching"

# 2. Verify status
hostctl show darkapi-api-1  # Should show status: blackout

# 3. Export for monitoring
blackout export

# 4. Perform maintenance...

# 5. End blackout
blackout end darkapi-api-1

# 6. Verify back to active
hostctl show darkapi-api-1  # Should show status: active
```

### SSH Access

```bash
# Get correct key for host
KEY=$(ssh-key-tracker get darkapi-api-1)

# SSH using the key
ssh -i $KEY opc@132.145.179.230
```

## Verification

```bash
# Check installations
which ssh-key-tracker hostctl blackout

# Test database
hostctl list

# Check services (if deployed with systemd)
systemctl status blackout-cleanup.timer
systemctl status blackout-exporter.service

# Test monitoring integration
curl http://localhost:9999/metrics
```

## Troubleshooting

### Can't connect to database

```bash
# Check environment variables
env | grep POSTGRES

# Test connection
psql -h $POSTGRES_HOST -U $POSTGRES_USER -d $POSTGRES_DB -c "SELECT 1"
```

### SSH key not working

```bash
# List all keys
ls -la ~/.ssh/*.key ~/.ssh/*.pem

# Scan for working key
ssh-key-tracker scan hostname ip-address
```

### Blackout not showing in monitoring

```bash
# Export blackouts
blackout export

# Check file exists
cat /var/lib/adsops/active-blackouts.json

# Check exporter
systemctl status blackout-exporter
curl http://localhost:9999/metrics | grep blackout
```

## Documentation

- Complete Guide: `HOST_MANAGEMENT_COMPLETE.md`
- SSH Tracker: `ssh-key-tracker --help`
- Hostctl: `tools/hostctl/README.md`
- Blackout: `tools/blackout/README.md`
- Monitoring: `../oci-observability/ansible/roles/blackout-integration/README.md`
