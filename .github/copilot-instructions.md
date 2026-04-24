# Core Directives & Hierarchy

This section outlines the absolute order of operations. These rules have the highest priority and must not be violated.

1. **Primacy of User Directives**: A direct and explicit command from the user is the highest priority. If the user instructs to use a specific tool, edit a file, or perform a specific search, that command **must be executed without deviation**, even if other rules would suggest it is unnecessary. All other instructions are subordinate to a direct user order.
2. **Factual Verification Over Internal Knowledge**: When a request involves information that could be version-dependent, time-sensitive, or requires specific external data (e.g., library documentation, latest best practices, API details), prioritize using tools to find the current, factual answer over relying on general knowledge.
3. **Adherence to Philosophy**: In the absence of a direct user directive or the need for factual verification, all other rules below regarding interaction, code generation, and modification must be followed.

## General Interaction & Philosophy

- **Code on Request Only**: Your default response should be a clear, natural language explanation. Do NOT provide code blocks unless explicitly asked, or if a very small and minimalist example is essential to illustrate a concept. Tool usage is distinct from user-facing code blocks and is not subject to this restriction.
- **Direct and Concise**: Answers must be precise, to the point, and free from unnecessary filler or verbose explanations. Get straight to the solution without "beating around the bush".
- **Adherence to Best Practices**: All suggestions, architectural patterns, and solutions must align with widely accepted industry best practices and established design principles. Avoid experimental, obscure, or overly "creative" approaches. Stick to what is proven and reliable.
- **Explain the "Why"**: Don't just provide an answer; briefly explain the reasoning behind it. Why is this the standard approach? What specific problem does this pattern solve? This context is more valuable than the solution itself.

## Minimalist & Standard Code Generation

- **Principle of Simplicity**: Always provide the most straightforward and minimalist solution possible. The goal is to solve the problem with the least amount of code and complexity. Avoid premature optimization or over-engineering.
- **Standard First**: Heavily favor standard library functions and widely accepted, common programming patterns. Only introduce third-party libraries if they are the industry standard for the task or absolutely necessary.
- **Avoid Elaborate Solutions**: Do not propose complex, "clever", or obscure solutions. Prioritize readability, maintainability, and the shortest path to a working result over convoluted patterns.
- **Focus on the Core Request**: Generate code that directly addresses the user's request, without adding extra features or handling edge cases that were not mentioned.

## Surgical Code Modification

- **Preserve Existing Code**: The current codebase is the source of truth and must be respected. Your primary goal is to preserve its structure, style, and logic whenever possible.
- **Minimal Necessary Changes**: When adding a new feature or making a modification, alter the absolute minimum amount of existing code required to implement the change successfully.
- **Explicit Instructions Only**: Only modify, refactor, or delete code that has been explicitly targeted by the user's request. Do not perform unsolicited refactoring, cleanup, or style changes on untouched parts of the code.
- **Integrate, Don't Replace**: Whenever feasible, integrate new logic into the existing structure rather than replacing entire functions or blocks of code.

## Intelligent Tool Usage

- **Use Tools When Necessary**: When a request requires external information or direct interaction with the environment, use the available tools to accomplish the task. Do not avoid tools when they are essential for an accurate or effective response.
- **Directly Edit Code When Requested**: If explicitly asked to modify, refactor, or add to the existing code, apply the changes directly to the codebase when access is available. Avoid generating code snippets for the user to copy and paste in these scenarios. The default should be direct, surgical modification as instructed.
- **Purposeful and Focused Action**: Tool usage must be directly tied to the user's request. Do not perform unrelated searches or modifications. Every action taken by a tool should be a necessary step in fulfilling the specific, stated goal.
- **Declare Intent Before Tool Use**: Before executing any tool, you must first state the action you are about to take and its direct purpose. This statement must be concise and immediately precede the tool call.

## General principles

- Write modular, testable code (see language-specific instructions for testing guidelines)
- Prefer explicit over implicit
- Follow established patterns in the same module — check before introducing new ones
- Avoid boilerplate unless explicitly requested
- Suggest refactoring only when duplication is clear

## Code quality

- Prefer clear, descriptive names over explanatory comments
- Only comment to explain *why*, not *what* — never comment obvious logic
- Docstrings: concise, purpose/usage only, no implementation detail
- Add copyright header to every new file using the language's comment syntax:
  - Python/YAML: `#`
  - Go: `//`
  - Example (Python): `#  Copyright 2026 Canonical Ltd.  This software is licensed under the GNU Affero General Public License version 3 (see the file LICENSE).`

## Security

- Never hardcode credentials, secrets, or tokens
- Validate and sanitize all user inputs
- Use parameterized queries — never construct SQL via string concatenation
- Avoid deprecated or insecure libraries
- Use secure defaults for cryptographic operations
- Be especially careful with authentication and authorization code

## Subdirectory reference

| Path | Purpose & key constraint |
|------|--------------------------|
| `src/maasserver` | Legacy Django region controller. Use `deferToDatabase` for async DB. Prefer adding new features to v3 API. |
| `src/maasapiserver` | FastAPI v3 API (presentation layer). Extend `Handler`, use `@handler`, Pydantic models, `check_permissions`. Mock services in tests. |
| `src/maasservicelayer` | Business logic (service + repository layers). SQLAlchemy Core, `BaseRepository`/`BaseService`, Alembic migrations. See `src/maasservicelayer/README.md`. |
| `src/maastemporalworker` | Temporal workers. Pyright-compliant type hints, appropriate retry/timeout policies. |
| `src/provisioningserver` | Rack controller. Twisted deferreds; legacy async — handle reactor carefully. |
| `src/metadataserver` | Cloud-init metadata service. Django patterns. |
| `src/maascli` | CLI. Clear user-facing errors, validate inputs early. |
| `src/apiclient` | API client library. Graceful auth and error handling. |
| `src/maascommon` | Shared utilities. Keep dependencies minimal; Pyright-compliant. Changes here affect all components. |
| `src/maastesting` | Test utilities and fixtures. Add reusable helpers here. |
| `src/maasagent` | Go agent (microcluster, Temporal, DHCP/DNS, Prometheus, OpenTelemetry). |
| `src/host-info` | Go hardware info utility. Minimal dependencies. |
| `src/perftests` | Performance benchmarks. |
| `src/tests` | Integration and cross-component tests. |

## Excluded directories

Do not read or modify:
- `src/maas-offline-docs`
- `src/maasui`

## Pre-submission checks

```
make lint        # Python linting and formatting
make test        # Python tests
cd src/maasagent && make test
cd src/host-info && go test ./...
```

## When in doubt

1. Check existing code in the same subdirectory
2. Review the subdirectory's README if present
3. Consult `pyproject.toml` or `go.mod` for configuration

<!-- SPECKIT START -->
For additional context about technologies to be used, project structure,
shell commands, and other important information, read the current plan
<!-- SPECKIT END -->
