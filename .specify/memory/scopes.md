# Conventional Commit Scopes for MAAS

**Reference**: [Conventional Commits 1.0.0](https://www.conventionalcommits.org/en/v1.0.0/)

**Format**: `<type>[(<scope>)][!]: <description>`

**Examples**:
- `feat(api): add machine list filtering by architecture`
- `fix(repo)!: change ip_addresses table schema` (breaking change, needs migration)
- `test(service): add coverage for machine allocation logic`
- `docs(agent): update microcluster setup instructions`

---

## Primary Scopes (Core MAAS Modules)

### `api`
**Module**: `src/maasapiserver/`  
**Responsibility**: FastAPI handlers, request/response models, HTTP layer  
**Examples**:
- `feat(api): add endpoint to list machines by status`
- `fix(api): validate machine name format in request body`
- `test(api): add permission tests for DELETE handler`

---

### `service`
**Module**: `src/maasservicelayer/services/`  
**Responsibility**: Business logic, service layer orchestration  
**Examples**:
- `feat(service): implement machine allocation algorithm`
- `fix(service): handle race condition in power transition`
- `test(service): add test for insufficient resources error`

---

### `repo`
**Module**: `src/maasservicelayer/db/repositories/`  
**Responsibility**: Repository layer, SQLAlchemy Core queries, filters  
**Examples**:
- `feat(repo): add filter for machines in ready state`
- `fix(repo): correct JOIN logic in power history query`
- `test(repo): add test for ClauseFactory with multiple conditions`

---

### `db`
**Module**: `src/maasservicelayer/db/`  
**Responsibility**: Database schema, Alembic migrations, table definitions  
**Examples**:
- `feat(db): add role-based access control columns to users table`
- `fix(db)!: normalize ip_addresses table schema` (breaking, needs migration)
- `docs(db): document table relationship diagrams`
- **Always include**: Migration script in `db/alembic/versions/`

---

### `builder`
**Module**: `src/maasservicelayer/builders/`  
**Responsibility**: Pydantic builder models for create/update operations  
**Examples**:
- `feat(builder): add builder for machine status update`
- `test(builder): verify builder field validation`

---

### `legacy`
**Module**: `src/maasserver/`  
**Responsibility**: Django region controller, backward compatibility  
**Examples**:
- `fix(legacy): maintain backward compatibility with v2 API`
- `test(legacy): add regression test for Django model persistence`
- **Prefer**: Adding features to v3 API instead. Use this scope only when maintaining/fixing existing Django code.

---

### `provisioning`
**Module**: `src/provisioningserver/`  
**Responsibility**: Rack controller, provisioning services  
**Examples**:
- `feat(provisioning): add support for new power driver`
- `fix(provisioning): correct TFTP boot sequence for arm64`

---

### `metadata`
**Module**: `src/metadataserver/`  
**Responsibility**: Cloud-init metadata service  
**Examples**:
- `feat(metadata): add user-data endpoint for commissioning`
- `test(metadata): verify commissioning script delivery`

---

### `agent`
**Module**: `src/maasagent/` (Go)  
**Responsibility**: Go microservices, microcluster architecture  
**Examples**:
- `feat(agent): implement DHCP service discovery`
- `fix(agent): handle connection timeout to Temporal server`
- `test(agent): add test for agent configuration loading`
- **Language**: Go, separate from Python tests

---

### `host-info`
**Module**: `src/host-info/` (Go)  
**Responsibility**: Hardware information collection  
**Examples**:
- `feat(host-info): detect NVMe storage devices`
- `fix(host-info): correct CPU core count on AMD EPYC`

---

### `worker`
**Module**: `src/maastemporalworker/`  
**Responsibility**: Temporal workflow orchestration  
**Examples**:
- `feat(worker): create workflow for machine deployment`
- `fix(worker): add retry policy for transient API failures`
- `test(worker): mock Temporal client for workflow tests`

---

### `cli`
**Module**: `src/maascli/`  
**Responsibility**: Command-line interface  
**Examples**:
- `feat(cli): add command to list available images`
- `fix(cli): improve error message for invalid arguments`

---

### `apiclient`
**Module**: `src/apiclient/`  
**Responsibility**: HTTP client library for MAAS API  
**Examples**:
- `feat(apiclient): add support for pagination in list methods`
- `fix(apiclient): handle authentication token refresh`

---

### `common`
**Module**: `src/maascommon/`  
**Responsibility**: Shared utilities and helpers  
**Examples**:
- `feat(common): add IP address validation utility`
- `test(common): improve test coverage for parsing functions`
- **Constraint**: Minimal dependencies, widely reused

---

### `testing`
**Module**: `src/maastesting/`  
**Responsibility**: Test utilities, fixtures, pytest plugins  
**Examples**:
- `feat(testing): add fixture for temporary database setup`
- `test(testing): verify fixture cleanup works correctly`

---

## Supporting Scopes (Cross-Cutting Concerns)

### `docs`
**Responsibility**: Documentation, README, architecture guides  
**Examples**:
- `docs(api): update OpenAPI endpoint documentation`
- `docs(service): explain builder pattern in README`
- `docs(architecture): add sequence diagram for v3 API flow`
- **Note**: Can be combined with module scope (e.g., `docs(api):`)

---

### `ci`
**Responsibility**: CI/CD pipelines, GitHub Actions workflows  
**Examples**:
- `ci: add Python type checking step to workflow`
- `ci: increase test timeout for slow integration tests`

---

### `chore`
**Responsibility**: Maintenance, dependency updates, non-functional changes  
**Examples**:
- `chore: update black version to 24.1.0`
- `chore: reorganize imports in maasapiserver`
- **Warning**: Avoid chore for refactoring; use appropriate module scope instead

---

### `perf`
**Responsibility**: Performance improvements  
**Examples**:
- `perf(repo): add index on machines.status column`
- `perf(api): cache permission lookups in request lifecycle`

---

### `style`
**Responsibility**: Code formatting, linting fixes (auto-fixable)  
**Examples**:
- `style(api): fix line length violations`
- `style(agent): apply golangci-lint fixes`
- **Note**: Should rarely appear in history (use `make format-py` / `make format-go` locally)

---

### `refactor`
**Responsibility**: Code restructuring without feature changes  
**Examples**:
- `refactor(service): extract validation logic into helper function`
- `refactor(repo): consolidate similar queries into single method`

---

## Type Specifications

### `feat`
New feature or functionality

**Commit Message Requirements**:
- Clear description of what the feature does
- Reference to user story if available

**Example**:
```
feat(api): add machine list filtering by architecture

Users can now filter the machine list by CPU architecture
via the ?architecture query parameter.
```

---

### `fix`
Bug fix or issue resolution

**Commit Message Requirements**:
- Ticket reference (Launchpad or GitHub):
  - Launchpad: `Resolves LP:2066936`
  - GitHub: `Resolves GH:123`
- Clear description of the fix
- Brief explanation of root cause

**Example**:
```
fix(repo): correct JOIN logic in power history query
Resolves LP:2099205

The previous query was missing the machine_id condition,
returning power history for all machines instead of the
requested machine.
```

---

### `test`
Test addition or modification

**Includes**:
- Unit tests, integration tests, functional tests
- Test fixtures, test utilities
- Test coverage improvements

**Example**:
```
test(service): add coverage for insufficient resources error

Added test case for machine allocation when pool has
insufficient available machines.
```

---

### `docs`
Documentation changes

**Includes**:
- README updates
- Architecture documentation
- Code comments (if explanatory, not obvious)

**Example**:
```
docs(service): explain builder pattern in README

Added section describing how builders work with UNSET
fields for optional create/update operations.
```

---

### `refactor`
Code restructuring (no feature/fix)

**Constraint**: Logic must not change; only structure

**Example**:
```
refactor(repo): consolidate similar queries

Extracted common filter logic into private helper method
to reduce duplication in find_* methods.
```

---

### `perf`
Performance improvement

**Includes**:
- Query optimization
- Index additions
- Caching strategies
- Algorithmic improvements

**Example**:
```
perf(repo): add index on machines.status column

Improves performance of filtered machine list queries by 10x
during high-volume provisioning operations.
```

---

### `chore`
Maintenance, non-functional changes

**Includes**:
- Dependency updates
- Build script changes
- General maintenance

**Example**:
```
chore: update pytest to 9.2.0

Picks up bug fixes and improved performance for large test
suites.
```

---

### `ci`
CI/CD workflow changes

**Includes**:
- GitHub Actions workflow updates
- Build configuration
- Test infrastructure

**Example**:
```
ci: add Python type checking step to workflow

All Python code must now pass Pyright strict mode before
PR merge.
```

---

### `style`
Formatting, linting (auto-fixable)

**Note**: Most commits of this type should not appear in history
(run `make format` locally to auto-fix)

**Example** (rare):
```
style(agent): apply golangci-lint fixes

Auto-fix formatting and linting issues identified by
golangci-lint.
```

---

## Breaking Changes

**Indicator**: Append `!` before colon

**Requirements**:
- Clearly document breaking change in commit body
- Plan migration path for users
- Provide deprecation warning in previous release if applicable

**Examples**:

```
feat(db)!: remove deprecated ip_ranges table

BREAKING CHANGE: ip_ranges table has been consolidated into
ip_spaces. Existing clients must migrate their code.
Migration guide: docs/migration-v3.8-to-v3.9.md
```

```
fix(api)!: change machine status enum values

BREAKING CHANGE: Machine status values have been renamed
for clarity (READY → ALLOCATED_READY). All API clients must
update their status checks.
```

---

## Scope Validation

**CI Check**: Commits without valid scopes are rejected

**Valid Scopes**:
```
api, service, repo, db, builder, legacy, provisioning, metadata,
agent, host-info, worker, cli, apiclient, common, testing,
docs, ci, chore, perf, style, refactor
```

**Invalid Commits** (Will be rejected by CI):
```
❌ feat: add new endpoint               (missing scope)
❌ feat(unknown): something             (unknown scope)
❌ fix: bug fix                          (missing scope, no ticket)
```

**Valid Commits** (Will pass CI):
```
✅ feat(api): add endpoint for listing machines
✅ fix(repo): correct query filter logic
✅ test(service): add test for validation
✅ docs(common): update utility function documentation
✅ feat(db): add users table with migration
✅ fix(legacy): maintain v2 API compatibility
```

---

## Commit Message Template

```
<type>(<scope>): <description>

<body>

<footer>
```

**Description** (max 72 characters):
- Summary of change
- Use imperative mood ("add" not "adds", "fix" not "fixed")

**Body** (optional, wrapped at 79 characters):
- Explain the *why*, not the *what*
- Reference design documents or architectural patterns
- Explain trade-offs considered

**Footer** (required for `fix`, optional for others):
- Ticket reference (Launchpad or GitHub)
- For breaking changes: `BREAKING CHANGE: description`

**Example**:
```
feat(api): add machine list filtering by architecture

The machine list endpoint now supports filtering by CPU
architecture via the ?architecture query parameter. This
reduces unnecessary data transfer for clients filtering
results in-memory.

The filtering is implemented at the repository layer to
ensure database-side filtering for performance. Supported
values are: x86_64, arm64, ppc64el, s390x.

Resolves GH:456
```

---

## Quick Reference

| Scope | Module | Example Commit |
|-------|--------|---|
| `api` | `src/maasapiserver/` | `feat(api): add device list endpoint` |
| `service` | `src/maasservicelayer/services/` | `feat(service): implement allocation logic` |
| `repo` | `src/maasservicelayer/db/repositories/` | `feat(repo): add status filter` |
| `db` | `src/maasservicelayer/db/` | `feat(db): add role column with migration` |
| `builder` | `src/maasservicelayer/builders/` | `feat(builder): add machine builder` |
| `legacy` | `src/maasserver/` | `fix(legacy): v2 API compatibility` |
| `provisioning` | `src/provisioningserver/` | `feat(provisioning): add power driver` |
| `metadata` | `src/metadataserver/` | `feat(metadata): add cloud-init section` |
| `agent` | `src/maasagent/` | `feat(agent): implement DHCP discovery` |
| `host-info` | `src/host-info/` | `feat(host-info): detect GPU devices` |
| `worker` | `src/maastemporalworker/` | `feat(worker): create provisioning workflow` |
| `cli` | `src/maascli/` | `feat(cli): add list-images command` |
| `apiclient` | `src/apiclient/` | `feat(apiclient): add pagination support` |
| `common` | `src/maascommon/` | `feat(common): add UUID utility` |
| `testing` | `src/maastesting/` | `feat(testing): add database fixture` |

---

**Last Updated**: 2025-04-20  
**Maintained By**: MAAS Core Team
