---
phase: 01-proto-data-contracts
plan: "01"
subsystem: proto-build-infra
tags: [buf, protobuf, go, python, makefile, codegen]
dependency_graph:
  requires: []
  provides: [buf-config, gen-go-module, proto-makefile-targets]
  affects: [proto/adsops/v1, gen/go, gen/python]
tech_stack:
  added: [buf v1.69.0, google.golang.org/protobuf v1.34.1]
  patterns: [managed-mode-buf, source-relative-paths, separate-gen-module]
key_files:
  created:
    - proto/buf.yaml
    - buf.gen.yaml
    - gen/go/go.mod
    - gen/go/go.sum
  modified:
    - Makefile
decisions:
  - "proto/buf.yaml placed inside proto/ so module path is '.' (relative to the proto dir)"
  - "No name: field in buf.yaml — BSR push is out of scope for v1"
  - "No gRPC plugins configured — not needed for v1 message-only contracts"
  - "managed mode with go_package_prefix means proto files must NOT contain option go_package"
  - "protobuf dependency pinned in gen/go/go.mod manually (go mod tidy removes it with no .go files)"
metrics:
  duration: "~8 minutes"
  completed: "2026-05-04"
  tasks_completed: 2
  files_created: 4
  files_modified: 1
---

# Phase 1 Plan 01: buf Toolchain Setup Summary

buf v2 config, gen/go module, and Makefile proto targets establishing the proto build infrastructure for Go and Python codegen.

## What Was Done

### Task 1: Install buf and create buf.yaml + buf.gen.yaml (commit: c08d608)

- Installed buf CLI v1.69.0 via `brew install bufbuild/buf/buf`
- Created `proto/buf.yaml` inside the proto/ directory with v2 config, DEFAULT lint rules, and FILE breaking rules
- Created `buf.gen.yaml` at repo root with managed mode (go_package_prefix), three plugins (Go messages, Python _pb2.py, Python .pyi type stubs), and `inputs: directory: proto`
- Created `proto/adsops/v1/` directory structure for future message definitions

### Task 2: Create gen/go/go.mod and add Makefile proto targets (commit: 3fbcd55)

- Created `gen/go/go.mod` as a separate Go module (`github.com/afterdarksys/adsops-utils/gen/go`) with `google.golang.org/protobuf v1.34.1`
- Populated `gen/go/go.sum` via `go mod download`
- Added `proto-gen`, `proto-lint`, `proto-breaking` targets to Makefile
- Updated `.PHONY` line to include new targets
- All targets follow `## target: description` comment convention for the help system

## Deviations from Plan

### Auto-noted Behaviors

**1. [Observation] buf lint fails on empty module in buf v2**

- **Found during:** Task 1 verification
- **Issue:** The plan states "buf lint proto/ # Should succeed (no proto files yet = no errors)" but buf v2 returns exit code 1 with "Module had no .proto files" when no .proto files exist
- **Fix:** Not a bug — expected buf v2 behavior. buf lint will succeed once .proto files are added in Plan 02
- **Impact:** No action required; verification step in plan is aspirational

**2. [Rule 2 - Critical] Protobuf dependency manually pinned in gen/go/go.mod**

- **Found during:** Task 2
- **Issue:** `go mod tidy` removes `google.golang.org/protobuf` from gen/go/go.mod when no .go files exist (nothing imports it yet)
- **Fix:** Used `go mod download` to populate go.sum, then manually kept the require directive in go.mod so the dependency is declared before generated files exist
- **Files modified:** gen/go/go.mod

## Known Stubs

None. This plan creates build tooling configuration only — no application code with stub values.

## Threat Flags

None. This plan creates build configuration only. No network endpoints, auth paths, file access patterns, or schema changes introduced.

## Self-Check: PASSED

| Item | Status |
|------|--------|
| proto/buf.yaml | FOUND |
| buf.gen.yaml | FOUND |
| gen/go/go.mod | FOUND |
| gen/go/go.sum | FOUND |
| SUMMARY.md | FOUND |
| Commit c08d608 (Task 1) | FOUND |
| Commit 3fbcd55 (Task 2) | FOUND |
