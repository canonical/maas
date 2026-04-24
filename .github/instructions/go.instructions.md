---
applyTo: "**/*.go"
---

## Subdirectory Context

See the subdirectory reference table in `copilot-instructions.md` for detailed constraints on: `src/maasagent` (microcluster-based agent with Temporal, DHCP/DNS, observability) and `src/host-info` (standalone hardware utility with minimal dependencies).

## Linting, Formatting & Testing

- Use `make lint-go` to check Go code before committing
- Use `make lint-go-fix` to auto-fix lint issues where possible
- Run the targeted Go lint instead of `make lint` when only Go files changed
- Use `make format-go` to format Go files instead of `make format` when only Go files changed
- Use `make test-go` to run Go tests instead of `make test` when only Go files changed

## Style

- Always run `gofmt` / `go fmt` before committing
- Follow standard Go idioms; avoid clever or non-idiomatic patterns
- Full style reference: `go-style-guide.md`

## Versions & modules

- `src/maasagent`: Go 1.24.4
- `src/host-info`: Go 1.18
- Check `go.mod` before adding any new dependency

## Testing

- Prefer table-driven tests
- Use `testify` in `src/maasagent`
- Standard `testing` package in `src/host-info`

## Subdirectory specifics

**`src/maasagent`** — microcluster-based agent
- Follow microcluster patterns
- Integrates Temporal workflows, DHCP/DNS services, Prometheus metrics, OpenTelemetry tracing
- Keep observability instrumentation consistent with existing patterns

**`src/host-info`** — hardware info utility
- Minimal dependencies; do not introduce new ones without good reason
- Standalone binary; keep it simple