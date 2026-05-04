# Phase 2: Python3 Package — Discussion Log

**Date:** 2026-05-04
**Areas discussed:** DB connectivity, SSH invocation, MockSys fidelity, Proto usage

## DB connectivity
- Q: PostgreSQL client? → SQLAlchemy ORM
- Q: Env vars? → Same as Go hostctl (INVENTORY_DB_*)

## SSH invocation
- Q: SSH library? → asyncssh (overrides REQUIREMENTS paramiko)
- Q: Auth model? → SSH agent only
- Q: Async CLI pattern? → asyncio.run() per command
- Q: Multi-host? → Yes, asyncio.gather()

## MockSys
- Q: Fidelity? → Configurable fixture data
- Q: Namespace scope? → All 11 namespaces from sysscript.go

## Proto usage
- Q: Which modules? → All modules (hostctl, infractl, stats)
