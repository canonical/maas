# Tech Stack Steering

## Runtime / Platform

- Python >= 3.14 (region/rack controllers, legacy + v3 API).
- Go 1.26 (`maasagent`, `maasopenfga`, `host-info`).
- Packaging: snap (`snap/`), Debian-style `setup.py`/`package-files`.

## Backend

- Legacy: Django ORM, Twisted (async reactor patterns) — `maasserver`, `provisioningserver`, `metadataserver`.
- v3 API: FastAPI + Pydantic (`maasapiserver`), SQLAlchemy Core + Pydantic builders (`maasservicelayer`).
- Workflow engine: Temporal (`maastemporalworker`).
- Go services: microcluster-based agent (`maasagent`) — DHCP/DNS, Prometheus metrics, OpenTelemetry tracing.

## Frontend

- `maasui` — separate frontend codebase (excluded from AI agent scope per AGENTS.md).

## Testing / Verification

- Lint: `make lint`
- Test (Python): `make test`; region-specific: `bin/test.region`
- Test (Go): `cd src/maasagent && make test`; `cd src/host-info && go test ./...`

## Constraints

- FIPS 140-2/140-3 and STIG/CIS hardening compliance must not break.
- Max line length 79 chars (Python), Ruff for lint/format.
- Dependency changes checked against `go.mod` (Go) / `pyproject.toml` (Python).

## Architectural Decisions

- **Three-tier v3 API (repository → service → API):** new functionality should prefer this layer over legacy Django when feasible.
- **SQLAlchemy Core, not ORM, in service layer:** keeps query control explicit, avoids ORM overhead for the new stack.
