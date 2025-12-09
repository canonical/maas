# AI Coding Agent Guidelines

This document provides guidelines for AI coding agents (such as GitHub Copilot, Cursor, Cline, etc.) working on the MAAS project. These rules help ensure consistency, quality, and security across the codebase.

## Table of Contents

- [General Principles](#general-principles)
- [Security Requirements](#security-requirements)
- [Documentation Standards](#documentation-standards)
- [Collaboration Practices](#collaboration-practices)
- [Python Guidelines](#python-guidelines)
- [Go Guidelines](#go-guidelines)
- [Subdirectory-Specific Rules](#subdirectory-specific-rules)

## General Principles

- Prefer clear, descriptive variable and function names
- Avoid abbreviations unless they are widely understood
- Write code that is modular and testable
- Prefer explicit over implicit code
- Follow the project's established patterns and idioms
- Suggest refactoring when code duplication is detected
- Avoid generating large boilerplate unless explicitly requested
- Always check existing code patterns in the same module before introducing new patterns

## Security Requirements

Across all parts of the codebase:

- Never hardcode credentials, secrets, or tokens
- Validate and sanitize all user inputs
- Use parameterized queries for database access
- Avoid deprecated or insecure libraries
- Follow security best practices for the specific technology stack
- Be especially careful with authentication and authorization code
- Always use secure defaults for cryptographic operations

## Documentation Standards

- Maintain up-to-date inline comments for complex logic
- Update README files when functionality changes
- Document API changes immediately
- Keep architecture documentation synchronized with code changes
- Use docstrings for all public functions, classes, and modules
- Include type hints where applicable

## Collaboration Practices

- Follow the project's code review and pull request process
- Tag relevant team members for specialized reviews
- Reference related issues in commits and pull requests
- Link to relevant documentation when making architectural changes
- Ensure code is compatible with the project's current dependency versions

## Python Guidelines

MAAS Python code must adhere to the following standards:

### Code Style

- **Line length**: Maximum 79 characters (as configured in `pyproject.toml`)
- **Indentation**: 4 spaces (no tabs)
- **Quotes**: Use double quotes for strings
- **Formatting**: Use Ruff formatter (configured in `pyproject.toml`)
- **Linting**: Follow Ruff linting rules (pycodestyle, pyflakes, isort, flake8-bugbear)

### Python Version Compatibility

- Target Python 3.9+ (check `pyproject.toml` for exact supported versions)
- Avoid using features from Python versions not yet supported
- Use type hints from `typing` module for compatibility

### Import Organization

Follow the isort configuration in `pyproject.toml`:

1. Standard library imports
2. Third-party library imports
3. MAAS first-party imports (in this order):
    - `apiclient`
    - `maasapiserver`
    - `maascli`
    - `maascommon`
    - `maasserver`
    - `maasservicelayer`
    - `maastesting`
    - `metadataserver`
    - `provisioningserver`

### Type Hints

- Use type hints for function signatures
- For new code in `maascommon`, `maasservicelayer`, `maasapiserver`, and `maastemporalworker`, ensure Pyright compliance
- Use Pydantic models for data validation where appropriate

### Async Code

- Use `async`/`await` patterns in asynchronous contexts
- Be aware of the difference between sync and async database access patterns
- In v3 API code, prefer async patterns
- In legacy Django code, use `deferToDatabase` for database operations in async contexts

### Database Access

- **New code**: Use SQLAlchemy Core (not ORM) in the service layer
- **Legacy code**: Continue using Django ORM where already established
- Always use parameterized queries
- Never construct SQL with string concatenation
- Use transactions appropriately

### Testing

- Write tests using `pytest` for new code
- Follow existing test patterns in the subdirectory
- Use appropriate fixtures (`db_connection`, `services_mock`, etc.)
- Aim for high test coverage
- Mock external dependencies appropriately

### Common Patterns

- Use builders (Pydantic models) for creating/updating entities in the service layer
- Implement `ClauseFactory` for reusable query filters
- Use `QuerySpec` for filtering in repository methods
- Follow the three-tier architecture in v3 API code (repository → service → API)

## Go Guidelines

MAAS Go code (primarily in `maasagent` and `host-info`) follows these standards:

### Code Style

- Follow standard Go formatting (`gofmt` / `go fmt`)
- Use `golangci-lint` if configured in the project
- Organize imports into standard library and external packages groups

### Go Version

- Check `go.mod` for the minimum required Go version
- Currently using Go 1.24.4 for `maasagent` and Go 1.18 for `host-info`

### Error Handling

- Always check and handle errors explicitly
- Use error wrapping with `fmt.Errorf` and `%w` for context
- Don't ignore errors unless there's a documented reason
- Prefer returning errors over panicking

### Naming Conventions

- Use `MixedCaps` or `mixedCaps` (not underscores) for multi-word names
- Exported names start with capital letters
- Keep names concise but descriptive
- Use single-letter variables only for short scopes (e.g., loop indices)

### Concurrency

- Use channels and goroutines idiomatically
- Avoid shared memory where possible; communicate by sharing
- Always provide context with timeouts for potentially long operations
- Use `sync` package primitives (Mutex, WaitGroup) carefully

### Context Usage

- Always pass `context.Context` as the first parameter
- Respect context cancellation and deadlines
- Use `context.Background()` only at the top level

### Dependencies

- Minimize external dependencies
- Check `go.mod` and `go.sum` for existing dependencies before adding new ones
- Use versioned imports from the `go.mod` file

### Testing

- Write tests in `_test.go` files
- Use table-driven tests where appropriate
- Use `testify` for assertions (already in dependencies)
- Mock interfaces, not concrete types
- Strive for good test coverage

### Logging

- Use structured logging (e.g., `zerolog` as used in `maasagent`)
- Include appropriate context in log messages
- Use appropriate log levels (debug, info, warn, error)

### Common Patterns

- Follow the microcluster patterns in `maasagent`
- Use dependency injection for better testability
- Implement interfaces for abstraction
- Keep functions focused and composable

## Subdirectory-Specific Rules

### `src/maasserver`

**Purpose**: Legacy Django-based region controller server

- **Technology**: Python, Django, Twisted
- **Database**: Django ORM (legacy), transitioning to SQLAlchemy where possible
- **Key Patterns**:
    - Use `deferToDatabase` for database calls in async contexts
    - Follow Django model conventions for existing models
    - Maintain backward compatibility with existing APIs
    - Add new functionality to service layer when possible
- **Testing**: Use Django test fixtures and `testtools`
- **Notes**: This is legacy code; prefer adding new features to the v3 API when feasible

### `src/maasapiserver`

**Purpose**: FastAPI-based v3 REST API (Presentation Layer)

- **Technology**: Python, FastAPI, Pydantic
- **Architecture**: Part of the three-tier architecture (API layer)
- **Key Patterns**:
    - Extend `Handler` class for new endpoints
    - Use `@handler` decorator for endpoint methods
    - Define Pydantic models for requests/responses
    - Use `check_permissions` for authorization
    - Mock services in tests, not repositories
- **Testing**: Use `APICommonTests`, `mocked_api_client*` fixtures
- **Authentication**: Support Bearer tokens, Django sessionid, and Macaroons
- **Documentation**: Ensure OpenAPI spec stays accurate

### `src/maasservicelayer`

**Purpose**: Business logic layer for v3 API (Application Layer)

- **Technology**: Python, SQLAlchemy, Pydantic
- **Architecture**: Part of the three-tier architecture (Service + Repository layers)
- **Key Patterns**:
    - Repositories use SQLAlchemy Core (not ORM)
    - Services contain business logic
    - Use builders for create/update operations
    - Implement `ClauseFactory` for reusable filters
    - Use `QuerySpec` for query filtering
    - Extend `BaseRepository` or `ReadOnlyRepository`
    - Extend `BaseService` or `ReadOnlyService`
- **Testing**:
    - Test repositories with real database (`db_connection` fixture)
    - Test services with mocked repositories
    - Use `RepositoryCommonTests` and `ServiceCommonTests` base classes
- **Database**: Keep table definitions in `db/tables.py` synchronized
- **Migrations**: Use Alembic for schema migrations
- **Notes**: Read `src/maasservicelayer/README.md` for detailed architecture

### `src/maastemporalworker`

**Purpose**: Temporal workflow workers

- **Technology**: Python, Temporal
- **Key Patterns**:
    - Follow Temporal workflow and activity patterns
    - Ensure type hints for Pyright compliance
    - Use appropriate retry and timeout policies
- **Testing**: Mock Temporal client in tests

### `src/provisioningserver`

**Purpose**: Rack controller provisioning services

- **Technology**: Python, Twisted
- **Key Patterns**:
    - Async operations using Twisted deferreds
    - Power driver implementations
    - TFTP and HTTP boot services
- **Notes**: Legacy async patterns; be careful with reactor usage

### `src/metadataserver`

**Purpose**: Cloud-init metadata service

- **Technology**: Python, Django
- **Key Patterns**:
    - Serve metadata to deploying machines
    - Handle commissioning and deployment scripts
- **Testing**: Follow Django testing patterns

### `src/maascli`

**Purpose**: Command-line interface

- **Technology**: Python
- **Key Patterns**:
    - CLI command implementations
    - User-facing error messages should be clear
    - Validate inputs early

### `src/apiclient`

**Purpose**: API client library

- **Technology**: Python
- **Key Patterns**:
    - HTTP client for MAAS API
    - Handle authentication and errors gracefully

### `src/maascommon`

**Purpose**: Common utilities shared across components

- **Technology**: Python
- **Key Patterns**:
    - Keep dependencies minimal
    - Well-tested utility functions
    - Ensure Pyright compliance
- **Notes**: Changes here affect multiple components

### `src/maastesting`

**Purpose**: Testing utilities and fixtures

- **Technology**: Python, pytest
- **Key Patterns**:
    - Reusable test fixtures
    - Database setup helpers
    - Pytest plugins
- **Notes**: Add reusable test utilities here

### `src/maasagent`

**Purpose**: Go-based MAAS agent using microcluster

- **Technology**: Go 1.24.4, microcluster, Temporal
- **Key Patterns**:
    - Microcluster-based architecture
    - DHCP and DNS services
    - Temporal workflow integration
    - Prometheus metrics
    - OpenTelemetry tracing
- **Testing**: Use Go testing with testify
- **Dependencies**: Check `go.mod` before adding dependencies
- **Notes**: Modern Go service; follow Go best practices

### `src/host-info`

**Purpose**: Collect host hardware information

- **Technology**: Go 1.18, LXD libraries
- **Key Patterns**:
    - Hardware detection and reporting
    - Minimal dependencies
- **Testing**: Standard Go tests
- **Notes**: Standalone utility for hardware information gathering

### `src/perftests`

**Purpose**: Performance testing

- **Technology**: Python
- **Key Patterns**:
    - Performance benchmarks
    - Load testing scenarios
- **Notes**: Add performance tests for critical paths

### `src/tests`

**Purpose**: Integration and cross-component tests

- **Technology**: Python, pytest
- **Key Patterns**:
    - Integration tests
    - End-to-end scenarios
- **Notes**: Tests that span multiple components

## Excluded Directories

The following directories should be ignored by AI coding agents:

- `src/maas-offline-docs`: Documentation artifacts
- `src/maasui`: UI components (separate frontend codebase)

## Running Checks

Before submitting code, ensure:

```bash
# Python linting and formatting
make lint

# Python tests
make test

# Go tests (in respective directories)
cd src/maasagent && make test
cd src/host-info && go test ./...
```

## Additional Resources

- Python configuration: `pyproject.toml`
- Go configuration: `src/maasagent/go.mod`, `src/host-info/go.mod`
- Service layer architecture: `src/maasservicelayer/README.md`
- Database migrations: `src/maasservicelayer/db/alembic/`

## Questions and Clarifications

When in doubt:

1. Check existing code in the same subdirectory for patterns
2. Review the subdirectory's README if available
3. Consult `pyproject.toml` or `go.mod` for configuration
4. Ask the human reviewer for clarification on architectural decisions
