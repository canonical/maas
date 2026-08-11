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
  set <key> <value>   Set a hardening parameter. DB-backed keys (hardening_enabled,
                      fips_enabled) are written to the MAAS database; conf-backed
                      keys (api_bind, database_sslmode, etc.) are written to
                      regiond.conf.
  get <key>           Get a hardening parameter value and its source store.
  list                List all hardening parameters with values and stores.
  validate            Run hardening validation; print violations; exit
                      non-zero if any exist.
  enable              Set hardening_enabled=on and seed loopback defaults for
                      unset region-internal bind addresses (prometheus_bind,
                      temporal_bind).
  disable             Set hardening_enabled=off; refused on FIPS hosts.
```

`get`, `list`, and `validate` are the inspection commands. `validate` reads the
region's current configuration, runs every check, prints violations, and exits
non-zero when any exist — use it as on-demand audit evidence. It does not start
or restart services.

`set` accepts any known hardening key. Keys backed by the MAAS database
(`hardening_enabled`, `fips_enabled`) are written to the DB Config store;
keys backed by `regiond.conf` (`api_bind`, `database_sslmode`, and so on)
are written to `regiond.conf` on the local host. The `set` command handles
YAML quoting automatically.

`enable` is a convenience shortcut: it sets `hardening_enabled=on` and also
seeds `prometheus_bind` and `temporal_bind` to `127.0.0.1` in `regiond.conf`
if those keys are unset, saving a separate step on first activation.

## Parameters and stores

| Key | Store | Default | Purpose |
|-----|-------|---------|---------|
| `hardening_enabled` | DB Config | `auto` | `auto`/`on`/`off` — see the activation model above. Set with `maas config-hardening set hardening_enabled <value>`. |
| `fips_enabled` | DB Config | not set | Declared FIPS intent (`true`/`false`). When set, startup validation checks that the declared value matches the host kernel state. |
| `api_bind` | `regiond.conf` (per-host) | empty | IPv4 address the public API binds to. A specific (non-wildcard) address is required when hardening is active. |
| `api_bind6` | `regiond.conf` (per-host) | empty | IPv6 address the public API binds to. A specific (non-wildcard) address is required when hardening is active. |
| `prometheus_bind` | `regiond.conf` (per-host) | empty | IPv4 address the Prometheus metrics endpoint binds to. Seeded to `127.0.0.1` by `maas config-hardening enable` if unset. |
| `temporal_bind` | `regiond.conf` (per-host) | empty | IPv4 address the Temporal worker binds to. Seeded to `127.0.0.1` by `maas config-hardening enable` if unset. |
| `rpc_bind` | `regiond.conf` (per-host) | empty | IPv4 address the region RPC service binds to. |
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

## Violation codes

When hardening is active, startup validation posts each unmet prerequisite as a
non-dismissable admin notification and `maas config-hardening validate` prints
it. A violation clears automatically once the underlying setting is corrected.

| Code | Trigger | Resolution |
|------|---------|------------|
| `MISSING_TLS_CERT` | No public-API TLS certificate configured | `maas config-tls enable <key> <cert>` |
| `MISSING_TLS_KEY` | No public-API TLS private key configured | `maas config-tls enable <key> <cert>` |
| `TLS_CERT_KEY_MISMATCH` | Certificate and key are not a matching pair | Re-run `maas config-tls enable` with a matching pair |
| `TLS_CERT_PARSE_ERROR` | Certificate or key is not valid PEM | Re-run `maas config-tls enable` with a valid PEM certificate |
| `WEAK_DH_PARAMS` | `api_tls_dhparam` file is under 2048 bits | See commands below. |
| `DH_PARAMS_PARSE_ERROR` | `api_tls_dhparam` file is not valid PEM DH parameters | See commands below. |
| `INVALID_BIND_ADDRESS` | A bind key (`api_bind`, `api_bind6`, `prometheus_bind`, `temporal_bind`, `rpc_bind`) contains a value that is not a valid IP address | `maas config-hardening set <key> <specific-ip-address>` |
| `WILDCARD_BIND_NOT_ALLOWED` | A bind key is unset or set to an all-interfaces address (`0.0.0.0` / `::`) | `maas config-hardening set <key> <specific-ip-address>` |
| `INSECURE_DB_SSLMODE` | `database_sslmode` is `disable`, `allow`, or `prefer` | See commands below. |
| `FIPS_CONFIG_STATUS_MISMATCH` | The declared `fips_enabled` value in the DB does not match the host kernel's FIPS state | `maas config-hardening set fips_enabled <true\|false>` to match the actual host state, or correct the host FIPS configuration |

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
