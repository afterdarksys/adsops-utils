---
phase: 01-proto-data-contracts
plan: "03"
subsystem: proto-codegen
tags: [buf, protobuf, go, python, codegen, bindings, pyproject]
dependency_graph:
  requires: [buf-config, gen-go-module, proto-makefile-targets, container-proto, k3s-proto, stats-proto, telemetry-proto, host-proto]
  provides: [go-proto-bindings, python-proto-bindings, adsops-proto-package]
  affects: [gen/go, gen/python, go.mod, systemapi-agent, tools/adsops]
tech_stack:
  added: [adsops-proto python package, protobuf v7.34.1 (python), google.golang.org/protobuf v1.34.1 (direct dep)]
  patterns: [setuptools-editable-install, buf-remote-plugins, source-relative-go-paths]
key_files:
  created:
    - gen/go/adsops/v1/container.pb.go
    - gen/go/adsops/v1/host.pb.go
    - gen/go/adsops/v1/k3s.pb.go
    - gen/go/adsops/v1/stats.pb.go
    - gen/go/adsops/v1/telemetry.pb.go
    - gen/python/adsops/__init__.py
    - gen/python/adsops/v1/__init__.py
    - gen/python/adsops/v1/container_pb2.py
    - gen/python/adsops/v1/container_pb2.pyi
    - gen/python/adsops/v1/host_pb2.py
    - gen/python/adsops/v1/host_pb2.pyi
    - gen/python/adsops/v1/k3s_pb2.py
    - gen/python/adsops/v1/k3s_pb2.pyi
    - gen/python/adsops/v1/stats_pb2.py
    - gen/python/adsops/v1/stats_pb2.pyi
    - gen/python/adsops/v1/telemetry_pb2.py
    - gen/python/adsops/v1/telemetry_pb2.pyi
    - gen/python/pyproject.toml
    - gen/python/__init__.py
  modified:
    - buf.gen.yaml
    - proto/buf.yaml
    - go.mod
    - go.sum
    - gen/go/go.sum
    - .gitignore
decisions:
  - "Python/pyi BSR plugins do not support paths=source_relative — removed from buf.gen.yaml (Go plugin keeps it)"
  - "pyproject.toml uses setuptools.build_meta backend (not _legacy which requires setuptools>=72 not available on system)"
  - "requires-python = >=3.10 because protobuf v7.34.1 (matching gencode v34.1) requires Python 3.10+"
  - "proto/buf.yaml uses STANDARD lint category (DEFAULT deprecated in buf v2)"
  - "K3sStats in proto generates as K3SStats in Go (protobuf CamelCase treats k3s as K3S acronym)"
  - "google.golang.org/protobuf promoted from indirect to direct dep in root go.mod by manual removal of // indirect"
  - ".gitignore updated to exclude __pycache__/, *.egg-info/, *.pyc"
metrics:
  duration: "~5 minutes"
  completed: "2026-05-04"
  tasks_completed: 2
  files_created: 19
  files_modified: 6
---

# Phase 1 Plan 03: buf Code Generation Summary

buf generate run against five proto files produces Go and Python bindings committed to gen/; pip install -e gen/python/ makes all five proto modules importable as from adsops.v1 import host_pb2; go build ./gen/go/... compiles all five .pb.go files; google.golang.org/protobuf promoted to direct dep in root go.mod.

## What Was Done

### Task 1: Run buf generate and create Python package structure (commit: 2983506)

- Fixed `buf.gen.yaml`: removed `paths=source_relative` option from Python and pyi plugins — BSR plugin version v34.1 does not support this option (Go plugin supports it fine)
- Ran `make proto-gen` which calls `buf generate` then creates `__init__.py` files in all Python package directories
- Generated 5 Go .pb.go files in `gen/go/adsops/v1/`: container, host, k3s, stats, telemetry
- Generated 5 Python `_pb2.py` + 5 `_pb2.pyi` files in `gen/python/adsops/v1/`
- __init__.py created at: `gen/python/__init__.py`, `gen/python/adsops/__init__.py`, `gen/python/adsops/v1/__init__.py`
- Created `gen/python/pyproject.toml` with `name = "adsops-proto"`, `version = "0.1.0"`, `requires-python = ">=3.10"`, `dependencies = ["protobuf>=5.26"]`
- Ran `go mod tidy` in `gen/go/` to resolve transitive deps (downloaded `golang.org/x/xerrors`)

### Task 2: Verify Go build, Python import, promote protobuf dep, and commit gen/ (commit: 39e3af8)

- Verified `go build ./...` in `gen/go/` compiles successfully — all 5 .pb.go files
- Verified all five Go struct types: HostRecord, ContainerStats, K3SStats, StatsSnapshot, TelemetryPayload
- Fixed pyproject.toml build backend from `setuptools.backends._legacy:_Backend` to `setuptools.build_meta` — the `_legacy` backend requires setuptools>=72 not available in this environment
- Installed `protobuf>=7.34.1` for Python 3.10 (BSR plugin gencode version requires runtime 7.34.1+)
- Ran `pip3.10 install -e gen/python/` — adsops-proto editable package installed and importable
- Verified all five Python module imports work: host_pb2, stats_pb2, container_pb2, k3s_pb2, telemetry_pb2
- Promoted `google.golang.org/protobuf v1.34.1` from indirect to direct dep in root `go.mod`
- Updated `proto/buf.yaml` to use `STANDARD` lint category (buf v2 deprecates `DEFAULT`)
- `make proto-lint` passes with zero errors and zero warnings
- Added Python build artifacts to `.gitignore` (`__pycache__/`, `*.egg-info/`, `*.pyc`)

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] BSR Python plugin v34.1 rejects paths=source_relative option**
- **Found during:** Task 1 — `make proto-gen` failed with: `plugin "buf.build/protocolbuffers/python:v34.1" failed: adsops/v1/container.proto: Unknown generator option: paths`
- **Issue:** The Python and pyi BSR remote plugins do not accept `paths` as a valid option. The Go plugin does support it.
- **Fix:** Removed `opt: - paths=source_relative` from Python and pyi plugin entries in `buf.gen.yaml`. Go plugin keeps `paths=source_relative` for the correct source-relative output layout.
- **Files modified:** `buf.gen.yaml`
- **Commit:** 2983506

**2. [Rule 1 - Bug] pyproject.toml used setuptools._legacy backend not available on system**
- **Found during:** Task 2 — `pip install -e gen/python/` failed with `BackendUnavailable: Cannot import 'setuptools.backends._legacy'`
- **Issue:** The `setuptools.backends._legacy:_Backend` backend requires setuptools>=72 which is not installed in the system Python 3.10 environment.
- **Fix:** Changed build backend to standard `setuptools.build_meta` which is universally available.
- **Files modified:** `gen/python/pyproject.toml`
- **Commit:** 39e3af8

**3. [Rule 2 - Missing] Python pycache and egg-info not in .gitignore**
- **Found during:** Task 2 post-commit check — pip install created `__pycache__/`, `adsops_proto.egg-info/` untracked
- **Fix:** Added `__pycache__/`, `*.egg-info/`, `*.pyc` to `.gitignore`
- **Files modified:** `.gitignore`
- **Commit:** 39e3af8

**4. [Observation] buf.yaml DEFAULT category deprecated in buf v2**
- **Found during:** Task 2 `make proto-lint` showing WARN about DEFAULT category
- **Fix:** Updated `proto/buf.yaml` to use `STANDARD` category (backwards compatible, eliminates warning)
- **Files modified:** `proto/buf.yaml`
- **Commit:** 39e3af8

### Environment Notes

**Python version:** The system `python3` is Python 3.9.6 (macOS built-in). The BSR protobuf plugin generates code requiring protobuf v7.34.1 runtime which only works on Python 3.10+. All verification commands use `python3.10` explicitly. The pyproject.toml correctly declares `requires-python = ">=3.10"`. Downstream consumers should use Python 3.10+ with `pip3.10 install -e gen/python/`.

**K3sStats naming:** The proto message `K3sStats` generates as `K3SStats` in Go. This is correct protobuf CamelCase behavior (treats `k3s` as the acronym `K3S`). The plan's must_haves artifact check specified `type K3sStats struct` but the actual generated name is `K3SStats struct`. The Go binding is correct and compiles successfully.

## Known Stubs

None. This plan produces generated code from proto definitions. No stub values.

## Threat Flags

None. Generated code committed to git. BSR plugins are official (buf.build/protocolbuffers/*). Generated output is deterministic. No secrets in generated proto bindings. pyproject.toml declares protobuf dependency — no network-fetched code at import time.

## Self-Check: PASSED

| Item | Status |
|------|--------|
| gen/go/adsops/v1/container.pb.go | FOUND |
| gen/go/adsops/v1/host.pb.go | FOUND |
| gen/go/adsops/v1/k3s.pb.go | FOUND |
| gen/go/adsops/v1/stats.pb.go | FOUND |
| gen/go/adsops/v1/telemetry.pb.go | FOUND |
| gen/python/adsops/v1/host_pb2.py | FOUND |
| gen/python/pyproject.toml | FOUND |
| type HostRecord struct in host.pb.go | VERIFIED |
| type ContainerStats struct in container.pb.go | VERIFIED |
| type K3SStats struct in k3s.pb.go | VERIFIED |
| type StatsSnapshot struct in stats.pb.go | VERIFIED |
| type TelemetryPayload struct in telemetry.pb.go | VERIFIED |
| Python imports (all 5 modules) | VERIFIED |
| google.golang.org/protobuf direct dep | VERIFIED |
| make proto-lint exit 0 | VERIFIED |
| Commit 2983506 (Task 1) | FOUND |
| Commit 39e3af8 (Task 2) | FOUND |
