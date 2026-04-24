---
mode: agent
description: Write a conventional commit message for the current changes
---

Inspect the staged or unstaged changes with `git diff --cached` (falling back to `git diff HEAD` if nothing is staged), then write a conventional commit message following the rules below.

## Format

```
<type>[(scope)][!]: <description>

[body]

[footer(s)]
```

## Types

| Type | When to use |
| :--- | :--- |
| `feat` | New feature |
| `fix` | Bug fix |
| `refactor` | Code change that is neither a fix nor a feature |
| `perf` | Performance improvement |
| `test` | Adding or correcting tests |
| `build` | Build, packaging, or dependency changes |
| `chore` | Changes that don't fit other types |
| `docs` | Documentation-only changes |

## Scopes

Use one of these when the change is clearly scoped to a component:

`bootresources` · `dhcp` · `dns` · `network` · `power` · `security` · `storage` · `tftp` · `ci`

For dependency changes use `build(deps):` — `deps` is a scope, not a standalone type.

## Rules

- **description**: 72 characters or less; high-level summary of the problem solved or feature added — no implementation detail lists
- **body**: explain *why*, not *what*; omit if the description is self-evident
- **`!`**: add before the colon for breaking changes; add `BREAKING CHANGE: <description>` in the footer
- **ticket reference**: mandatory for `fix`; include for all other types when a relevant issue exists
  - Launchpad: `Resolves LP:2066936`
  - GitHub: `Resolves GH:123`
  - Jira: `Resolves JIRA-123`
- **author attribution**: Do NOT include Co-authored-by footers for AI tools or bots. This project maintains author integrity by crediting actual humans only.

## Examples

```
feat(bootresources): check if controller has enough disk space

Controllers were silently failing or retrying indefinitely when disk
space was insufficient. This adds pre-flight checks to fail fast with
a clear user-facing error rather than producing confusing partial state.
```

```
fix(network): correct VLAN configuration parsing

The parser was incorrectly handling tagged VLANs with non-standard
MTU values, causing network interface initialization to fail.

Resolves LP:2066936
```

```
feat(bootresources)!: replace tcpdump with maas-netmon

New binary `maas-netmon` is introduced for ARP network discovery.

BREAKING CHANGE: Binary doesn't read PCAP format, thus it is not
possible to pass in stdin or file as an argument anymore.
```

## Output

Print only the commit message — no explanation, no surrounding text.