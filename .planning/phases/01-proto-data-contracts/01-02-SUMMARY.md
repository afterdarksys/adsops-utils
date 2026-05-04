---
phase: 01-proto-data-contracts
plan: "02"
subsystem: proto-message-definitions
tags: [protobuf, proto3, buf, data-contracts, statsagent, hostctl, telemetry]
dependency_graph:
  requires: [buf-config, gen-go-module, proto-makefile-targets]
  provides: [container-proto, k3s-proto, stats-proto, telemetry-proto, host-proto]
  affects: [gen/go, gen/python, systemapi-agent, tools/hostctl, tools/statsagent]
tech_stack:
  added: []
  patterns: [proto3-optional-scalars, google-protobuf-struct-for-jsonb, proto3-message-nullable-defaults, int64-unix-timestamp-for-wire-compat]
key_files:
  created:
    - proto/adsops/v1/container.proto
    - proto/adsops/v1/k3s.proto
    - proto/adsops/v1/stats.proto
    - proto/adsops/v1/telemetry.proto
    - proto/adsops/v1/host.proto
  modified: []
decisions:
  - "TelemetryPayload.timestamp uses int64 (not google.protobuf.Timestamp) for wire compatibility with systemapi-agent which sends time.Now().Unix()"
  - "NSInfo renamed to NamespaceInfo in k3s.proto for cleaner public API naming"
  - "HostRecord.metadata uses google.protobuf.Struct (not string) for native JSON support in Go and Python"
  - "HostRecord.children is repeated HostRecord (self-referential) for Phase 5 host->container->pod hierarchy"
  - "sql.NullString and sql.NullFloat64 fields use proto3 optional keyword for presence detection"
  - "No option go_package in any proto file — buf managed mode injects this at generation time"
  - "TelemetryPayload includes host_id field (new, from agent config) not in original Go struct"
  - "DockerStats and K3sStats imported into TelemetryPayload as AGENT-05 extension fields"
metrics:
  duration: "~6 minutes"
  completed: "2026-05-04"
  tasks_completed: 3
  files_created: 5
  files_modified: 0
---

# Phase 1 Plan 02: Proto Message Definitions Summary

Five proto files defining the complete data contract catalog for statsagent collectors, systemapi-agent telemetry, and hostctl inventory — all fields verified against Go source structs with correct types.

## What Was Done

### Task 1: container.proto and k3s.proto (commit: 9eb356a)

- Created `proto/adsops/v1/container.proto` with ContainerStats (11 fields) and DockerStats (5 fields) matching docker.go JSON tags exactly
- Created `proto/adsops/v1/k3s.proto` with NodeInfo (4 fields), NamespaceInfo (3 fields, renamed from NSInfo), and K3sStats (10 fields) matching k3s.go
- All timestamp fields use google.protobuf.Timestamp to represent Go time.Time
- buf lint passes with zero errors

### Task 2: stats.proto (commit: 48f2980)

- Created `proto/adsops/v1/stats.proto` with 9 messages covering all statsagent collectors
- SystemStats (18 fields): full catalog including uptime, load averages (1m/5m/15m), cpu (used/idle/iowait/cores), all memory fields (total/available/used/cached/buffers), and swap
- MountStats (7 fields) and IOStats (7 fields) from disk.go
- InterfaceStat (11 fields) from network.go including rx_errors, tx_errors, rx_dropped, tx_dropped, rx_total_bytes, tx_total_bytes
- ProcInfo (6 fields) including state field, ProcessStats (5 fields) including zombie_procs
- StatsSnapshot (8 fields) imports DockerStats from container.proto and K3sStats from k3s.proto
- buf lint passes with zero errors

### Task 3: telemetry.proto and host.proto (commit: d99faa8)

- Created `proto/adsops/v1/telemetry.proto` with 7 messages matching systemapi-agent telemetry.go
- TelemetryPayload uses int64 timestamp (not Timestamp WKT) for wire compatibility — systemapi-agent sends time.Now().Unix()
- Added host_id string field on TelemetryPayload (from agent config, not in original Go struct)
- DockerStats and K3sStats imported and added to TelemetryPayload as AGENT-05 extension fields
- SoftwareInfo placeholder (name + version) for gatherSoftware() output
- Created `proto/adsops/v1/host.proto` with HostRecord (18 fields) mirroring hostctl Resource type
- sql.NullString fields (region, external_id, external_url) use proto3 optional keyword
- sql.NullFloat64 fields (average_daily_cost, average_monthly_cost) use optional double
- metadata uses google.protobuf.Struct for native arbitrary JSON support in Go and Python
- repeated HostRecord children enables Phase 5 host->container->pod hierarchy
- buf lint passes with zero errors on all five proto files

## Deviations from Plan

None - plan executed exactly as written.

## Known Stubs

**SoftwareInfo in telemetry.proto** — The SoftwareInfo message has only `name` and `version` fields as a placeholder for the gatherSoftware() output. The gatherSoftware() source was not fully analyzed in RESEARCH.md. These fields are sufficient for Phase 1; if gatherSoftware() produces additional fields they can be added in a later phase.

## Threat Flags

None. This plan creates static proto schema definitions only. No network endpoints, auth paths, file access patterns, or runtime behavior introduced.

## Self-Check: PASSED

| Item | Status |
|------|--------|
| proto/adsops/v1/container.proto | FOUND |
| proto/adsops/v1/k3s.proto | FOUND |
| proto/adsops/v1/stats.proto | FOUND |
| proto/adsops/v1/telemetry.proto | FOUND |
| proto/adsops/v1/host.proto | FOUND |
| buf lint exit code 0 | VERIFIED |
| ContainerStats (11 fields) | VERIFIED |
| DockerStats (5 fields) | VERIFIED |
| NamespaceInfo (not NSInfo) | VERIFIED |
| K3sStats (10 fields) | VERIFIED |
| SystemStats (18 fields) | VERIFIED |
| StatsSnapshot (8 fields) | VERIFIED |
| TelemetryPayload int64 timestamp | VERIFIED |
| HostRecord google.protobuf.Struct metadata | VERIFIED |
| No option go_package in any file | VERIFIED (count: 0) |
| Commit 9eb356a (Task 1) | FOUND |
| Commit 48f2980 (Task 2) | FOUND |
| Commit d99faa8 (Task 3) | FOUND |
