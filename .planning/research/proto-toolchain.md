# Research: Protocol Buffer Toolchain for Go + Python Monorepo

**Project:** adsops-utils / systemapi-agent
**Researched:** 2026-05-03
**Overall confidence:** HIGH (buf docs verified, Python recommendation MEDIUM due to betterproto2 churn)

---

## 1. buf vs protoc — Verdict: Use buf

**Use buf.** Protoc requires manual plugin management, shell flags, and bespoke Makefiles. Buf replaces all of that with declarative YAML and remote plugin execution via the BSR.

Key advantages for this project:
- `buf lint` enforces proto style (catches field naming, reserved range, etc.)
- `buf breaking` detects wire-incompatible changes — important once systemapi-agent imports these types
- `buf generate` is deterministic and reproducible across machines without pinning plugin binaries
- Remote plugins via BSR mean no local `protoc-gen-go`, `protoc-gen-python` installs required
- Managed mode removes `go_package` options from `.proto` files, keeping schemas language-neutral

**Install:** `brew install bufbuild/buf/buf` or download binary; no other protoc tools needed.

---

## 2. Proto Directory Structure

Recommended layout for adsops-utils:

```
proto/
  buf.yaml                          # module definition
  adsops/telemetry/v1/
    telemetry.proto                 # TelemetryPayload, StatsSnapshot
  adsops/host/v1/
    host.proto                      # HostRecord
  adsops/container/v1/
    container.proto                 # ContainerStats, K3sStats
buf.gen.yaml                        # root-level generation config
gen/
  go/                               # generated Go bindings
  python/                           # generated Python bindings
```

**Why this layout:**
- Versioned sub-paths (`v1/`) enable buf breaking change detection and future `v2/` migration
- Domain separation (telemetry, host, container) maps cleanly to the stats types needed
- `gen/` at root is conventional and makes `.gitignore` targeting clean

**proto/buf.yaml:**
```yaml
version: v2
name: buf.build/afterdarksys/adsops  # optional: only needed if pushing to BSR
```

---

## 3. buf.gen.yaml Configuration

Place at repo root. Uses remote plugins — no local plugin binaries needed.

```yaml
version: v2
managed:
  enabled: true
  override:
    - file_option: go_package_prefix
      value: github.com/afterdarksys/adsops-utils/gen/go
plugins:
  # Go bindings
  - remote: buf.build/protocolbuffers/go
    out: gen/go
    opt:
      - paths=source_relative

  # Python bindings (_pb2.py files)
  - remote: buf.build/protocolbuffers/python
    out: gen/python
    opt:
      - paths=source_relative

  # Python type stubs (_pb2.pyi files) — required for IDE completion and mypy
  - remote: buf.build/protocolbuffers/pyi
    out: gen/python
    opt:
      - paths=source_relative
inputs:
  - directory: proto
```

Run generation:
```bash
buf generate
```

**Managed mode note:** The `go_package_prefix` override means you do NOT put `option go_package = "..."` inside each `.proto` file. buf injects it at generation time. This is the current best practice — keeps protos language-neutral.

---

## 4. Go Module Import by systemapi-agent

Two options; recommendation depends on release cadence.

### Option A: replace directive (development / pre-release)

In systemapi-agent's `go.mod`:
```
require github.com/afterdarksys/adsops-utils v0.0.0

replace github.com/afterdarksys/adsops-utils => /path/to/local/adsops-utils
```

This works for local development but cannot be used in CI/CD without a local checkout or git submodule. Replace directives are not allowed in published modules — any downstream that imports systemapi-agent as a library will break.

### Option B: Extract gen/go/ as a separate Go module (recommended for v1+)

Create `gen/go/go.mod`:
```
module github.com/afterdarksys/adsops-utils/gen/go

go 1.21

require google.golang.org/protobuf v1.34.0
```

systemapi-agent then imports:
```
require github.com/afterdarksys/adsops-utils/gen/go v0.1.0
```

This is a separate versioned module in the same repo (multi-module monorepo pattern). Tag releases as `gen/go/v0.1.0` in git. This is the cleanest long-term approach.

**Recommended path:** Start with Option A during active development. Promote to Option B (separate go.mod in gen/go/) before systemapi-agent goes to CI/CD or needs pinned versions.

Generated Go import paths will look like:
```go
import telemetryv1 "github.com/afterdarksys/adsops-utils/gen/go/adsops/telemetry/v1"
```

---

## 5. Python: betterproto vs google-protobuf — Verdict: Use google-protobuf

**Use `google-protobuf` (official) + `mypy-protobuf` for type stubs.**

**Do NOT use betterproto for v1.** Reasons:

- `python-betterproto` (original) is effectively unmaintained; the maintainer moved to `betterproto2` with breaking API changes and incomplete documentation as of 2025
- Historical decode performance was reported at 250-300x slower than official protobuf in one benchmark (though this may have improved)
- No stable BSR remote plugin — you'd need `judahrand/python-betterproto` (community, not official)
- The project has undergone a "major redesign" mid-flight — not stable enough for infrastructure telemetry tooling

**Official google-protobuf stack:**
```
protobuf          # runtime: pip install protobuf
mypy-protobuf     # type stubs: pip install mypy-protobuf (dev)
```

The `buf.build/protocolbuffers/pyi` remote plugin (already in buf.gen.yaml above) generates `_pb2.pyi` stub files. These give IDE completion and mypy checking for generated classes.

Import pattern in tools/adsops/:
```python
from adsops.telemetry.v1.telemetry_pb2 import TelemetryPayload, StatsSnapshot
from adsops.host.v1.host_pb2 import HostRecord
```

Add to tools/adsops/ or a shared requirements:
```
protobuf>=5.26.0
```

For dev/type checking:
```
mypy-protobuf>=3.6.0
```

**sys.path / package setup:** Add `gen/python/` to PYTHONPATH, or install as a local package. A minimal `gen/python/pyproject.toml` makes this clean:
```toml
[build-system]
requires = ["setuptools"]
build-backend = "setuptools.backends.legacy:build"

[project]
name = "adsops-proto"
version = "0.1.0"
dependencies = ["protobuf>=5.26"]
```
Then `pip install -e gen/python/` in dev.

---

## 6. Gotchas

### buf + Python: grpc_tools incompatibility
If gRPC is added later, the standard Python gRPC generation path uses `grpc_tools` (a compiled Python extension), which buf cannot invoke as a plugin — buf expects a `protoc-gen-*` binary on PATH. The buf GitHub issue #1344 confirms this is a known limitation. Workaround: generate gRPC stubs separately via `python -m grpc_tools.protoc` or use the BSR remote plugin `buf.build/grpc/python` which wraps around this correctly.

For v1 (no service definitions), this is not a concern.

### paths=source_relative is required for Go
Without `paths=source_relative`, protoc-gen-go uses the full proto import path and can generate files in unexpected nested directories. Always set this option.

### gen/ directory: commit or gitignore?
Both patterns are used in the wild. **Recommendation: commit gen/ for this project.**
- systemapi-agent can `go get` without needing buf installed
- tools/adsops/ can import without running buf at install time
- CI does not need buf in the standard build pipeline
- Add a `make proto` target and a note in the README to regenerate after proto changes

### buf managed mode and existing go_package options
If any `.proto` file already has `option go_package = "..."`, managed mode will override it. Either remove existing `go_package` options from protos (preferred) or add a `disable` rule in buf.gen.yaml.

### Python _pb2 naming
Generated files are always `<filename>_pb2.py` — this is a protobuf convention, not buf-specific. Import paths include `_pb2` suffix. This is normal and expected.

### protobuf runtime version pinning
The generated `_pb2.py` files embed a minimum runtime version check. Pin `protobuf>=5.26` in requirements to avoid runtime errors from version mismatch with generated code.

---

## Makefile Targets

```makefile
.PHONY: proto proto-lint proto-breaking

proto:
	buf generate

proto-lint:
	buf lint proto/

proto-breaking:
	buf breaking proto/ --against '.git#branch=main'
```

---

## Sources

- [buf CLI GitHub](https://github.com/bufbuild/buf) — HIGH confidence
- [Buf Generate Docs](https://buf.build/docs/generate/) — HIGH confidence
- [buf.gen.yaml v2 Reference](https://buf.build/docs/configuration/v2/buf-gen-yaml/) — HIGH confidence
- [Buf BSR Python SDKs](https://buf.build/docs/bsr/generated-sdks/python/) — HIGH confidence
- [python-betterproto GitHub](https://github.com/danielgtaylor/python-betterproto) — MEDIUM confidence (project status)
- [betterproto2 GitHub](https://github.com/betterproto/python-betterproto2) — MEDIUM confidence
- [mypy-protobuf GitHub](https://github.com/nipunn1313/mypy-protobuf) — HIGH confidence
- [buf issue #1344: grpc_tools incompatibility](https://github.com/bufbuild/buf/issues/1344) — HIGH confidence
- [Go Modules Reference](https://go.dev/ref/mod) — HIGH confidence
