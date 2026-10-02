# Security hardening reference

This page lists the settings, commands, checks, and behavior of MAAS security hardening. For background, see [FIPS mode and security hardening](/explanation/fips.md). For procedures, see [Activate MAAS hardening](/how-to-guides/activate-maas-hardening.md).

Controls that apply only when the host kernel is in FIPS mode are listed separately in the [FIPS mode reference](/reference/configuration-guides/fips-mode.md).

## Activation

Each MAAS process resolves its hardening state once, at startup. A restart is required for a change to take effect.

| `hardening_enabled` | Host in FIPS mode | Hardening |
|---|---|---|
| `auto` (default) | No | Inactive |
| `auto` (default) | Yes | Active |
| `on` | No | Active |
| `on` | Yes | Active |
| `off` | No | Inactive |
| `off` | Yes | Active. FIPS mode overrides `off`. |

Accepted values are `auto`, `on`, and `off`. Values are case-insensitive. An absent setting is treated as `auto`.

FIPS mode is active when `/proc/sys/crypto/fips_enabled` contains `1`. If the file is missing, MAAS treats the host as not in FIPS mode. If the file exists but cannot be read, MAAS treats the host as not in FIPS mode and logs a `fips_mode_unreadable` warning.

### Where each controller reads the setting

| Component | Source of `hardening_enabled` |
|---|---|
| Region controller (`regiond`, API server) | MAAS database. One value for all region controllers. |
| Rack controller (`rackd`) | Local `rackd.conf`. One value per rack controller. |

## Region command: `maas config-hardening`

Run on a region controller, with `sudo`.

```text
maas config-hardening {set,get,list,validate,enable,disable} ...
```

| Subcommand | Behavior |
|---|---|
| `set <key> <value>` | Writes a parameter. `hardening_enabled` is written to the database; every other key is written to the local `regiond.conf`. Prints `Set <key> in regiond.conf` for file-backed keys. |
| `get <key>` | Prints `<key> [<store>] = <value>`. The store is `config` (database) or `conf` (`regiond.conf`). |
| `list` | Prints every parameter with its store and value. The first line shows whether a public API TLS certificate is configured. For an unset bind key that MAAS derives automatically, the line ends with `(effective: <addresses>)`. |
| `validate` | Runs every hardening check against the local configuration and prints the result. Does not restart services or post notifications. |
| `enable` | Sets `hardening_enabled` to `on`. Changes only the database. |
| `disable` | Sets `hardening_enabled` to `off`. Refused on a FIPS host. |

`set` rejects unknown keys and `fips_enabled`. For list-valued keys, separate addresses with commas. `set` handles YAML quoting for you.

### `validate` output and exit status

| Exit status | Meaning | Output |
|---|---|---|
| `0` | No violations | `OK: no hardening violations.` |
| `1` | One or more violations | `VIOLATIONS (<n>):` followed by one block per violation |
| `2` | The configuration could not be read | `Could not read configuration: <error>` |

Each violation block has this form:

```text
  [<CODE>] <message>
    Resolution: <suggested command>
    Config key: <key>  File: <path>
```

`File:` appears only when the violation refers to a file, such as a DH parameters file.

When hardening is inactive, `validate` prints `Hardening is not active; only FIPS-drift is checked.` It then checks only for `FIPS_CONFIG_STATUS_MISMATCH`.

## Rack command

The rack controller has its own command, which manages `rackd.conf`.

| Installation | Command |
|---|---|
| Snap in `rack` mode | `sudo maas config-hardening {list,get,set,validate}` |
| Snap in `region+rack` mode | No command. Edit `/var/snap/maas/current/rackd.conf` directly. |

| Subcommand | Behavior |
|---|---|
| `list` | Prints every rack hardening key and its value. |
| `get <key>` | Prints the value of one key. |
| `set <key> <value>` | Writes one key to `rackd.conf` and prints `<key> set.` |
| `validate` | Checks the rack bind keys. Prints `OK: no hardening violations.` on success, or a `VIOLATIONS (<n>):` list and exits with status `1`. When hardening is inactive, prints `Hardening is not active on this rack controller.` |

Rack validation checks bind addresses only. TLS, DH parameter, and database checks apply to region controllers only. Rack results are not posted as notifications.

## Region parameters

All file-backed keys are per host and stored in `/var/snap/maas/current/regiond.conf`.

### Activation and drift

| Key | Store | Default | Description |
|---|---|---|---|
| `hardening_enabled` | Database | `auto` | Activation setting. See [Activation](#activation). |
| `fips_enabled` | Database | Not set | Read-only. MAAS sets it to `true` when a region controller starts in FIPS mode. It cannot be set or cleared with `maas config-hardening`. |

### TLS and database

| Key | Default | Description |
|---|---|---|
| `api_tls_dhparam` | Empty | Path to a PEM file of Diffie-Hellman parameters for the web server. Optional. When set, the parameters must be at least 2048 bits. |
| `database_sslmode` | `prefer` | PostgreSQL client SSL mode. Under hardening, use `verify-ca` or `verify-full`. |
| `database_sslrootcert` | Empty | Path to the CA certificate that signed the PostgreSQL server certificate. Required for `verify-ca` and `verify-full`. |
| `database_sslcert` | Empty | Path to a client certificate. Needed only if the PostgreSQL server requires client certificate authentication. |
| `database_sslkey` | Empty | Path to the client private key that matches `database_sslcert`. |

The public API TLS certificate and private key are not hardening parameters. They are stored in the MAAS secret store and managed with `maas config-tls`.

### Bind addresses

A bind key sets the address or addresses that a service listens on. List-valued keys accept a comma-separated list that may mix IPv4 and IPv6 addresses.

| Key | Service | Value | Unset, hardening inactive | Unset, hardening active |
|---|---|---|---|---|
| `api_bind` | Public web UI and API | List | All interfaces | Derived from `maas_url`, per address family |
| `api_int_bind` | Internal HTTP listener used by rack controllers when TLS is enabled | List | All interfaces | Violation |
| `agent_api_bind` | Internal API server used by MAAS Agent (port 5242) | List | All interfaces | Derived from `maas_url`, per address family |
| `rpc_bind` | Region RPC service | List | All interfaces | Derived from `maas_url` |
| `temporal_bind` | Temporal services | Single | All interfaces | Derived from `maas_url` |
| `syslog_bind` | Syslog service | List | All interfaces | Derived from `maas_url` |
| `http_proxy_bind` | HTTP proxy (Squid) | List | All interfaces | Derived from `maas_url`, per address family |
| `prometheus_bind` | Prometheus metrics endpoint | Single IPv4 | All interfaces | `127.0.0.1` |
| `dns_bind` | DNS server (BIND 9) | List | All interfaces | Violation |

Derivation rules:

- "Derived from `maas_url`" means the local address that the host uses to reach the `maas_url` host. If MAAS cannot determine that address, it falls back to loopback (`127.0.0.1` or `::1`).
- "Per address family" means MAAS derives an IPv4 and an IPv6 address independently. If you set only one family explicitly, MAAS still derives the other.
- An explicit value always takes precedence.
- `api_int_bind` and `dns_bind` are never derived. DNS must serve every managed subnet, not only the interface that reaches `maas_url`.

When `rpc_bind` is set, rack controllers connect to exactly those addresses.

### DNS server options

These keys are not managed by `maas config-hardening`. Edit `regiond.conf` (region) or `rackd.conf` (rack) directly, then restart MAAS.

| Key | Default | Value when unset and hardening is active | Value when unset and hardening is inactive |
|---|---|---|---|
| `dns_allow_transfer` | Empty | `none` | Directive omitted |
| `dns_fetches_per_zone` | `0` | `100` | Directive omitted |
| `dns_fetches_per_server` | `0` | `100` | Directive omitted |

When hardening is active, MAAS also sets `version "not disclosed"` in the BIND 9 options.

### Editing `regiond.conf` directly

`regiond.conf` is a YAML file. Quote values that YAML would otherwise convert, for example `hardening_enabled: "on"`. An unquoted `on` is read as a Boolean. Prefer `maas config-hardening set`, which quotes values for you.

## Rack parameters

Rack keys are stored in `/var/snap/maas/current/rackd.conf`.

| Key | Value | Unset, hardening active |
|---|---|---|
| `hardening_enabled` | `auto`, `on`, or `off` | Not applicable. Default is `auto`. |
| `api_bind` | List | Derived from `maas_url`, per address family |
| `syslog_bind` | List | Derived from `maas_url` |
| `http_proxy_bind` | List | Derived from `maas_url`, per address family |
| `rpc_bind` | Single | Violation |
| `tftp_bind` | List | Violation |
| `dns_bind` | List | Violation |

When hardening is inactive, an unset rack bind key listens on all interfaces.

`temporal_server` in `rackd.conf` is not a hardening key, and `maas config-hardening` does not manage it. It sets the host name or IP address that MAAS Agent connects to for Temporal, on port 5271. When unset, MAAS Agent uses the host from the first `maas_url`. Set it when the region controllers bind Temporal to an address that differs from that host, for example after you pin `temporal_bind`.

## Violation codes

When hardening is active, region validation can report the following codes. `FIPS_CONFIG_STATUS_MISMATCH` is reported whether or not hardening is active.

| Code | Reported when | Applies to |
|---|---|---|
| `MISSING_TLS_CERT` | No public API TLS certificate is configured. | Region |
| `MISSING_TLS_KEY` | No public API TLS private key is configured. | Region |
| `TLS_CERT_KEY_MISMATCH` | The certificate and private key do not form a pair. | Region |
| `TLS_CERT_PARSE_ERROR` | The certificate or key is not valid PEM. | Region |
| `WEAK_TLS_CERT_KEY` | FIPS mode only. The certificate uses a key type other than RSA or ECDSA, an RSA key under 2048 bits, or a SHA-1 or MD5 signature. | Region |
| `WEAK_DH_PARAMS` | The `api_tls_dhparam` file contains parameters under 2048 bits. | Region |
| `DH_PARAMS_PARSE_ERROR` | The `api_tls_dhparam` file is not valid PEM DH parameters. | Region |
| `INVALID_BIND_ADDRESS` | A bind key contains a value that is not an IP address. | Region and rack |
| `WILDCARD_BIND_NOT_ALLOWED` | A bind key contains `0.0.0.0` or `::`, or a key with no derived default is unset. | Region and rack |
| `INSECURE_DB_SSLMODE` | `database_sslmode` is `disable`, `allow`, `prefer`, or `require`, and the database host is not a Unix socket path. | Region |
| `FIPS_CONFIG_STATUS_MISMATCH` | `fips_enabled` is `true` in the database, but this host is not in FIPS mode. | Region |

Notes:

- TLS checks stop at the first failure. For example, a missing certificate hides any key problem.
- If `api_tls_dhparam` points to a file that does not exist, no violation is reported.
- A bind key reports at most one `INVALID_BIND_ADDRESS` or one `WILDCARD_BIND_NOT_ALLOWED` violation, listing every offending value.
- `database_sslmode` is not checked when `database_host` is a filesystem path, because a Unix socket connection does not use TLS.

For resolution steps, see [Resolve hardening violations](/how-to-guides/resolve-hardening-violations.md).

## Notifications

The primary region controller process posts and clears hardening notifications each time it starts.

| Property | Value |
|---|---|
| Category | `error` |
| Audience | Administrators only |
| Can be dismissed | No |
| Message | The violation message followed by its resolution |
| Context fields | `code`, `config_key`, and `file_path` when present |

Bind address violations are scoped to the controller that found them. Their message starts with `[<system_id>]`, so each region controller in a high availability deployment has its own notification. All other violations are global.

A notification is removed the next time a region controller starts without that violation.

## Password policy

The policy applies when hardening is active or the host is in FIPS mode. A compliant password must meet every rule:

| Rule | Requirement |
|---|---|
| Length | At least 14 characters |
| Uppercase | At least one uppercase letter (`A`–`Z`) |
| Digit | At least one digit (`0`–`9`) |
| Special character | At least one character that is not a letter or digit. Spaces, `-`, and `_` count. |

MAAS checks every rule and reports all failures in one message. The policy cannot be configured.

The policy applies to:

- MAAS user passwords set in the web UI, with `maas createadmin` or `maas changepassword`, or through the user endpoints of the MAAS API.
- The `power_pass` value of a machine or VM host power configuration, when hardening is active. An empty `power_pass` is not checked.

The 14-character minimum also meets the FIPS minimum HMAC key length of 112 bits, which applies when MAAS hashes passwords.

## Reverse proxy

The region and rack controllers each run an NGINX reverse proxy.

### Rate and connection limits

These limits apply whether or not hardening is active.

| Key | Default | Description |
|---|---|---|
| `api_rate_limit_rate` | `20r/s` | Requests per second allowed for each client IP address. |
| `api_rate_limit_burst` | `60` | Requests a client can make above the rate before MAAS rejects them. |
| `api_conn_limit` | `100` | Concurrent connections allowed for each client IP address. |

Set these keys in `regiond.conf` or `rackd.conf`, then restart MAAS. An empty `api_rate_limit_rate` turns off both rate and connection limiting.

### Hardening response headers

When hardening is active, both proxies:

- Set `server_tokens off`, which hides the NGINX version.
- Add `X-Frame-Options: DENY`.
- Add `X-Content-Type-Options: nosniff`.
- Add `Referrer-Policy: strict-origin-when-cross-origin`.
- Add `X-XSS-Protection: 1; mode=block`.
- Add a `Content-Security-Policy` header.
- Close the connection without a response (NGINX status `444`) for `TRACE` and `OPTIONS` requests.

These controls are not configurable. They produce no violations, because there is nothing to validate.

Independently of hardening, the region proxy adds `Strict-Transport-Security: max-age=63072000; includeSubdomains` whenever TLS is enabled.

### Content Security Policy

Region controller:

```text
default-src 'self';
script-src 'self' 'sha256-<hash>';
style-src 'self' 'unsafe-inline';
img-src 'self' data:;
font-src 'self';
connect-src 'self';
frame-ancestors 'none'
```

| Directive | Value | Reason |
|---|---|---|
| `default-src` | `'self'` | Deny by default. Every resource type must be same-origin unless overridden. |
| `script-src` | `'self' 'sha256-<hash>'` | Inline scripts are forbidden. One hash allows a single static inline script required by the documentation theme. |
| `style-src` | `'self' 'unsafe-inline'` | The documentation generator emits inline `style` attributes. Styles cannot execute code. |
| `img-src` | `'self' data:` | Allows inline image data used by theme icons and diagrams. |
| `font-src` | `'self'` | Fonts are bundled with MAAS and served from the region controller. |
| `connect-src` | `'self'` | Restricts `fetch()` and `XMLHttpRequest` to the same origin. |
| `frame-ancestors` | `'none'` | Prevents MAAS pages from being embedded in a frame. |

The rack controller serves no HTML interface, so its policy is `default-src 'none'; frame-ancestors 'none'`.

## Log events

Hardening and FIPS detection events are written to the controller logs. On a snap installation, read them with `journalctl`, for example `journalctl -t maas-regiond`.

| Event | Level | Fields |
|---|---|---|
| `fips_mode_detected` | `INFO` | `fips_mode` |
| `fips_mode_unreadable` | `WARNING` | `fips_mode`, `detection_error` |
| `hardening_mode_determined` | `INFO` | `setting`, `fips_enabled`, `hardening_active` |
| `hardening_violation` | `ERROR` | `ident`, `code`, `config_key`, `file_path`, `message` |
| `hardening_notification_posted` | `INFO` | `ident`, `code`, `controller_id` |

For FIPS cryptography events, see the [FIPS mode reference](/reference/configuration-guides/fips-mode.md#log-events).
