# Security hardening reference

This page is the reference for MAAS security-hardening configuration:
the activation model, the `maas config-hardening` command, the hardening
parameters and their stores, the password policy enforced in hardening mode,
and the violation codes reported at startup.

For step-by-step setup, see
[Activate MAAS hardening](/how-to-guides/enhance-maas-security.md#activate-maas-hardening).
For the concepts behind hardening, see
[Security hardening](/explanation/security.md#security-hardening).

## Activation model

Hardening state is resolved once per process at startup and never blocks a
controller from starting.

| `hardening_enabled` | Host in FIPS mode | Result |
|---------------------|-------------------|--------|
| `auto` (default)    | yes               | hardening active |
| `auto` (default)    | no                | hardening inactive |
| `on`                | yes or no         | hardening active |
| `off`               | no                | hardening inactive |
| `off`               | yes               | hardening active (FIPS overrides `off`) |

FIPS mode is detected from `/proc/sys/crypto/fips_enabled`. On a FIPS host,
hardening is always active; `off` cannot disable it.

## `maas config-hardening`

```text
usage: maas config-hardening {set,get,list,validate,enable,disable} ...

Manage MAAS hardening configuration parameters.

subcommands:
  set <key> <value>   Set a hardening parameter. hardening_enabled (DB-backed)
                      and conf-backed keys (api_bind, database_sslmode, etc.)
                      can be set; fips_enabled cannot (see below).
  get <key>           Get a hardening parameter value and its source store.
  list                List all hardening parameters with values and stores.
  validate            Run hardening validation; print violations; exit
                      non-zero if any exist.
  enable              Set hardening_enabled=on. A pure database operation;
                      it does not touch regiond.conf. Every bind key is
                      left unset so MAAS can derive or discover an
                      address at startup.
  disable             Set hardening_enabled=off; refused on FIPS hosts.
```

`get`, `list`, and `validate` are the inspection commands. `validate` reads the
region's current configuration, runs every check, prints violations, and exits
non-zero when any exist — use it as on-demand audit evidence. It does not start
or restart services.

`set` accepts any known hardening key except `fips_enabled` (see below).
`hardening_enabled` is written to the DB Config store; keys backed by
`regiond.conf` (`api_bind`, `database_sslmode`, and so on) are written to
`regiond.conf` on the local host. The `set` command handles YAML quoting
automatically.

`enable` is a convenience shortcut for
`maas config-hardening set hardening_enabled on`: it writes only the DB
`Config` store. No bind key is seeded. `api_bind`, `api_bind6`,
`temporal_bind`, `rpc_bind`, `agent_api_bind`, `agent_api_bind6`,
`syslog_bind`, `http_proxy_bind`, and `http_proxy_bind6` derive a specific
address from `maas_url` at startup when left unset; `prometheus_bind`
instead defaults to loopback (`127.0.0.1`) when left unset, since it's
scraped locally rather than reached via `maas_url` (see the parameter
table below).

## Parameters and stores

| Key | Store | Default | Purpose |
|-----|-------|---------|---------|
| `hardening_enabled` | DB Config | `auto` | `auto`/`on`/`off` — see the activation model above. Set with `maas config-hardening set hardening_enabled <value>`. |
| `fips_enabled` | DB Config | not set | Read-only, auto-detected: the first controller in the fleet to observe kernel FIPS mode active writes `true`, so every controller is thereafter held to the same requirement. Not settable via `config-hardening set`; inspect with `get`/`list`. |
| `api_bind` | `regiond.conf` (per-host) | empty | IPv4 address(es) the public API binds to; may be a comma-separated list. Left unset by default: derived from `maas_url` at startup when hardening is active (same address clients already use to reach the region), otherwise binds all interfaces. Set explicitly to pin one or more addresses. |
| `api_bind6` | `regiond.conf` (per-host) | empty | IPv6 address(es) the public API binds to; may be a comma-separated list. Same derivation as `api_bind`, restricted to an IPv6 address of `maas_url`'s host. |
| `api_int_bind` | `regiond.conf` (per-host) | empty | IPv4 address the internal (rack-facing) plain HTTP listener binds to when TLS is enabled. Left unset by default: **not** derived from `maas_url` — binds all interfaces when unset, which is flagged under hardening. Set explicitly to pin it to a specific address. |
| `api_int_bind6` | `regiond.conf` (per-host) | empty | IPv6 equivalent of `api_int_bind`; same derivation (none) and same requirement to set explicitly under hardening. |
| `prometheus_bind` | `regiond.conf` (per-host) | empty | IPv4 address the Prometheus metrics endpoint binds to. Left unset by default: when hardening is active, the runtime binds it to `127.0.0.1` — unlike the other bind keys, it defaults to loopback rather than a `maas_url`-derived address, since it's scraped locally by a co-located agent (e.g. grafana-agent), not remotely. Set explicitly to pin it elsewhere. |
| `temporal_bind` | `regiond.conf` (per-host) | empty | IPv4 address the Temporal services bind to. Left unset by default: derived from `maas_url` at startup, on every install mode (region, rack+region, all-in-one). Set explicitly to pin it elsewhere. |
| `temporal_server` | `rackd.conf` (per-host) | empty | Address MAAS Agent dials to reach Temporal; not a hardening key. Left unset by default: derived from `maas_url` at startup, the same as `temporal_bind`. Set explicitly to pin it elsewhere. |
| `rpc_bind` | `regiond.conf` (per-host) | empty | Address(es) the region RPC service binds to; may be a comma-separated list. Left unset by default: derived from `maas_url` at startup (same address rack controllers already use to reach the region), falling back to binding and advertising every interface only if `maas_url` cannot be resolved. When set, rack controllers dial exactly the configured address(es). |
| `agent_api_bind` | `regiond.conf` (per-host) | empty | IPv4 address(es) the internal API server (dialed by `maas-agent` on rack controllers, port 5242) binds to; may be a comma-separated list. Left unset by default: derived from `maas_url` at startup, the same as `rpc_bind`. |
| `agent_api_bind6` | `regiond.conf` (per-host) | empty | IPv6 equivalent of `agent_api_bind`; may be a comma-separated list. Same derivation. |
| `syslog_bind` | `regiond.conf`/`rackd.conf` (per-host) | empty | Address(es) the syslog service binds to; may be a comma-separated list. Left unset by default: derived from `maas_url` at startup (same address enrolled machines and rack controllers already reach MAAS on), the same as `rpc_bind`/`temporal_bind`. Set it explicitly to pin syslog to a different interface. |
| `dns_bind` | `regiond.conf` (per-host) | empty | IPv4 address(es) the DNS (BIND9) service binds to when hardening is active; may be a comma-separated list. **Not** derived from `maas_url`: DNS must serve every managed subnet, not just the interface that reaches the API, so a specific address is always required explicitly under hardening. **Snap installs only**: MAAS owns the whole `named.conf` there; not available (nor validated) on Debian-packaged installs, where MAAS does not own the base `named.conf.options`. |
| `dns_bind6` | `regiond.conf` (per-host) | empty | IPv6 equivalent of `dns_bind`; may be a comma-separated list. Same derivation, and same snap-only restriction. |
| `http_proxy_bind` | `regiond.conf`/`rackd.conf` (per-host) | empty | IPv4 address(es) the HTTP proxy (squid) service binds to; may be a comma-separated list. Left unset by default: binds all interfaces outside hardening, or derives from `maas_url` at startup when hardening is active, the same as `rpc_bind`/`syslog_bind`. |
| `http_proxy_bind6` | `regiond.conf`/`rackd.conf` (per-host) | empty | IPv6 equivalent of `http_proxy_bind`; may be a comma-separated list. Same derivation. |
| `api_tls_dhparam` | `regiond.conf` (per-host) | empty | Path to a DH parameters PEM file. When present, it must be at least 2048 bits. |
| `database_sslmode` | `regiond.conf` (per-host) | `prefer` | PostgreSQL client SSL mode. Under hardening, use `verify-ca` or `verify-full`. |
| `database_sslcert` | `regiond.conf` (per-host) | empty | Path to the PostgreSQL client certificate. Required when `database_sslmode` is `verify-full`. |
| `database_sslkey` | `regiond.conf` (per-host) | empty | Path to the PostgreSQL client private key. Required when `database_sslmode` is `verify-full`. |
| `database_sslrootcert` | `regiond.conf` (per-host) | empty | Path to the CA certificate used to verify the PostgreSQL server. Required when `database_sslmode` is `verify-ca` or `verify-full`. |
| TLS certificate / key | secret store | not set | Public-API HTTPS certificate and key. Managed by `maas config-tls enable`, **not** `config-hardening`. |

`regiond.conf` is at `/var/snap/maas/current/regiond.conf` for snap installs and `/etc/maas/regiond.conf` for Debian package installs.

`regiond.conf` is YAML. String values that YAML would otherwise coerce must be
quoted when editing the file directly — for example `hardening_enabled: "on"`
(unquoted `on` parses as a boolean). The `maas config-hardening set` command
handles quoting automatically and is the recommended way to set all parameters.

## Rack controller hardening

`maas config-hardening` manages the region's `regiond.conf`. A rack
controller has its own bind keys in `rackd.conf` and its own CLI,
`maas-rack config-hardening`, run locally on the rack:

```text
usage: maas-rack config-hardening {list,get,set,validate} ...

subcommands:
  list       List all rack hardening parameters.
  get <key>  Get a rack hardening parameter value.
  set <key> <value>
             Set a rack hardening parameter value.
  validate   Run hardening validation against rackd.conf; print
             violations; exit non-zero if any exist.
```

Keys: `hardening_enabled`, `api_bind`, `api_bind6`, `rpc_bind`,
`syslog_bind`, `http_proxy_bind`, `http_proxy_bind6`, and (snap installs
only) `dns_bind`/`dns_bind6`. `api_bind`, `api_bind6`, `syslog_bind`,
`http_proxy_bind`, and `http_proxy_bind6` derive a specific address from
`maas_url` when left unset, the same as their region counterparts.
`rpc_bind` has no such derivation on the rack: leaving it unset binds all
interfaces and is flagged under hardening.

`maas-rack config-hardening validate` checks only bind-wildcard rules —
the rack has no TLS certificate, DH parameters, or database to validate;
those checks are region-only. It does not post notifications to the
region database (see [Security hardening](/explanation/security.md#security-hardening)
for the region/rack notification scope).

## Violation codes

When hardening is active, startup validation posts each unmet prerequisite as a
non-dismissable admin notification and `maas config-hardening validate` prints
it. A violation clears automatically once the underlying setting is corrected.

| Code | Trigger | Resolution |
|------|---------|------------|
| `MISSING_TLS_CERT` | No public-API TLS certificate configured | `maas config-tls enable <key> <cert>` |
| `MISSING_TLS_KEY` | No public-API TLS private key configured | `maas config-tls enable <key> <cert>` |
| `TLS_CERT_KEY_MISMATCH` | Certificate and key are not a matching pair | Re-run `maas config-tls enable` with a matching pair |
| `WEAK_TLS_CERT_KEY` | Certificate's key is DSA, an RSA key under 2048 bits, or the certificate is signed with SHA-1/MD5 (only checked when FIPS mode is active on the host) | Re-run `maas config-tls enable` with a FIPS-compliant certificate (RSA 2048 bits or larger, ECDSA, signed with SHA-256 or stronger) |
| `TLS_CERT_PARSE_ERROR` | Certificate or key is not valid PEM | Re-run `maas config-tls enable` with a valid PEM certificate |
| `WEAK_DH_PARAMS` | `api_tls_dhparam` file is under 2048 bits | See commands below. |
| `DH_PARAMS_PARSE_ERROR` | `api_tls_dhparam` file is not valid PEM DH parameters | See commands below. |
| `INVALID_BIND_ADDRESS` | A bind key (`api_bind`, `api_bind6`, `api_int_bind`, `api_int_bind6`, `prometheus_bind`, `temporal_bind`, `rpc_bind`, `agent_api_bind`, `agent_api_bind6`, `syslog_bind`, `http_proxy_bind`, `http_proxy_bind6`, `dns_bind`, `dns_bind6`) contains a value that is not a valid IP address | `maas config-hardening set <key> <specific-ip-address>` |
| `WILDCARD_BIND_NOT_ALLOWED` | A bind key is set to an all-interfaces address (`0.0.0.0` / `::`), or is unset (except `api_bind`, `api_bind6`, `temporal_bind`, `rpc_bind`, `agent_api_bind`, `agent_api_bind6`, `syslog_bind`, `http_proxy_bind`, and `http_proxy_bind6`, which are derived automatically from `maas_url` when unset). `api_int_bind`/`api_int_bind6` have no such derivation and are flagged when unset. `dns_bind`/`dns_bind6` are only checked on snap installs. | `maas config-hardening set <key> <specific-ip-address>` |
| `INSECURE_DB_SSLMODE` | `database_sslmode` is `disable`, `allow`, `prefer`, or `require`, and `database_host` is not a Unix socket path | See commands below. |
| `FIPS_CONFIG_STATUS_MISMATCH` | Another controller in the fleet has FIPS mode active (`fips_enabled` in the DB), but this host's kernel does not | Enable FIPS mode on this host's kernel to match the rest of the fleet. `fips_enabled` cannot be unset via `config-hardening`. |

**Resolving `WEAK_DH_PARAMS` or `DH_PARAMS_PARSE_ERROR`:** generate a new DH
parameters file and set the path:

```text
openssl dhparam -out /var/snap/maas/current/certs/dhparam.pem 2048
sudo maas config-hardening set api_tls_dhparam /var/snap/maas/current/certs/dhparam.pem
```

**Resolving `INSECURE_DB_SSLMODE`:** set the SSL mode and supply the client
certificate, key, and CA certificate:

```text
sudo maas config-hardening set database_sslmode verify-full
sudo maas config-hardening set database_sslcert /var/snap/maas/current/certs/db-client.pem
sudo maas config-hardening set database_sslkey /var/snap/maas/current/certs/db-client.key
sudo maas config-hardening set database_sslrootcert /var/snap/maas/current/certs/db-ca.pem
```

Not flagged when `database_host` is a filesystem path (e.g. the socket
directory used by `maas-test-db`): connections over a Unix domain socket
never negotiate TLS, so `database_sslmode` is not applicable.

## Password policy

When hardening is active, MAAS enforces password complexity on every password
set through the CLI (`maas createadmin`, `maas changepassword`) and the web UI.
The same policy applies independently on any FIPS host, regardless of the
`hardening_enabled` setting.

A compliant password must satisfy all four rules:

| Rule | Requirement |
|------|-------------|
| Length | At least 14 characters |
| Uppercase | At least one uppercase letter (A–Z) |
| Digit | At least one digit (0–9) |
| Special character | At least one character that is not a letter or digit — including `-`, `_`, space, and punctuation |

All four rules are evaluated together. When a password fails, the error message
lists every unmet rule in a single response.

The policy is not configurable. It cannot be relaxed or disabled while hardening
is active or FIPS mode is on.

## Startup log events

Structured JSON events. View them with `journalctl -o json`.

| Event | Level | Meaning |
|-------|-------|---------|
| `fips_mode_detected` | INFO | FIPS state read at startup (`fips_mode`, `source`). |
| `hardening_mode_determined` | INFO | Resolved hardening state (`setting`, `fips_enabled`, `hardening_active`). |
| `hardening_violation` | ERROR | A prerequisite is unmet (`ident`, `code`, `config_key`, `file_path`, `message`). |
| `hardening_notification_posted` | INFO | An admin notification was posted for a violation (`ident`, `code`). |
