# FIPS mode reference

This page lists the controls that MAAS applies only when the host kernel is in FIPS mode. For background, see [FIPS mode and security hardening](/explanation/fips.md). To enable FIPS mode on a controller, see [Enable FIPS mode on a MAAS controller](/how-to-guides/enable-fips-mode-on-a-controller.md).

FIPS mode always activates security hardening. The controls in the [Security hardening reference](/reference/configuration-guides/security-hardening.md) therefore also apply on a FIPS host.

## Detection

| Item | Value |
|---|---|
| Source | `/proc/sys/crypto/fips_enabled` |
| FIPS mode active | File content is `1` |
| File missing | Not in FIPS mode |
| File unreadable | Not in FIPS mode, and a `fips_mode_unreadable` warning is logged |
| When read | Once per process, at startup |

## Summary of FIPS-conditional controls

| Area | Control |
|---|---|
| Security hardening | Always active. `hardening_enabled=off` is ignored, and `maas config-hardening disable` is refused. |
| Public API TLS | Certificate must meet the [TLS certificate rules](#tls-certificates). Otherwise `WEAK_TLS_CERT_KEY` is reported. |
| Web server TLS | Only FIPS-approved cipher suites and curves are offered. |
| SSH sessions | Only FIPS-approved algorithms are negotiated. |
| SSH host keys | Unknown host keys are rejected. Trust on first use is turned off. |
| User SSH keys | Must use an approved key type and size. |
| User SSL keys | Must meet the TLS certificate rules. |
| Power drivers | Non-compliant drivers and settings are rejected. |
| Password policy | Always enforced. |
| Fleet drift | `fips_enabled` is recorded in the database. |

## Web server TLS

When TLS is enabled on a FIPS host, the region controller web server uses these settings:

| Setting | Value |
|---|---|
| Protocols | TLS 1.2, TLS 1.3 |
| TLS 1.3 cipher suites | `TLS_AES_256_GCM_SHA384`, `TLS_AES_128_GCM_SHA256` |
| TLS 1.2 cipher suites | `ECDHE-ECDSA-AES128-GCM-SHA256`, `ECDHE-RSA-AES128-GCM-SHA256`, `ECDHE-ECDSA-AES256-GCM-SHA384`, `ECDHE-RSA-AES256-GCM-SHA384`, `DHE-RSA-AES128-GCM-SHA256`, `DHE-RSA-AES256-GCM-SHA384` |
| Elliptic curves | `prime256v1` (P-256), `secp384r1` (P-384) |

On a non-FIPS host, MAAS additionally offers ChaCha20-Poly1305 suites and the X25519 curve.

## TLS certificates

These rules apply to the public API certificate and to SSL keys that users add for Windows WinRM access.

| Property | Allowed |
|---|---|
| Key type | RSA or ECDSA |
| RSA key size | 2048 bits or larger |
| Signature algorithm | SHA-256 or stronger |

Rejected: DSA, Ed25519, and Ed448 keys; RSA keys under 2048 bits; SHA-1 and MD5 signatures.

## SSH

### Session algorithms

MAAS-initiated SSH sessions negotiate only the following algorithms. These sessions are used by SSH-based power drivers, such as `hmc`, `mscm`, and `wedge`.

| Type | Allowed algorithms |
|---|---|
| Ciphers | `aes128-ctr`, `aes192-ctr`, `aes256-ctr`, `aes128-gcm@openssh.com`, `aes256-gcm@openssh.com` |
| Key exchange | `ecdh-sha2-nistp256`, `ecdh-sha2-nistp384`, `diffie-hellman-group14-sha256` |
| MACs | `hmac-sha2-256`, `hmac-sha2-512` |
| Host key algorithms | `ecdsa-sha2-nistp256`, `rsa-sha2-256`, `rsa-sha2-512` |

If the remote device offers no allowed cipher or MAC, the connection fails and MAAS logs a `fips_crypto_error` event with `operation=ssh_negotiation`.

### Host key verification

| Host state | Behavior for a host key that is not already known |
|---|---|
| Not in FIPS mode | Accepted |
| FIPS mode | Accepted only if it matches a trusted SSH host key. Otherwise rejected, and a `fips_crypto_error` event is logged with `operation=ssh_host_key_verify`. |

A trusted host key matches when all three of these fields are equal:

- `host`: the power address configured for the machine.
- `key_type`: the key type reported by the device, such as `ssh-rsa` or `ecdsa-sha2-nistp256`.
- `public_key`: the Base64-encoded public key.

If MAAS cannot look up the trusted keys, it rejects the connection.

### Trusted SSH host keys API

Trusted SSH host keys can be managed in the web UI or through the MAAS v3 API.

| Method | Path | Permission | Description |
|---|---|---|---|
| `GET` | `/MAAS/a/v3/ssh-host-keys` | View global entities | List trusted host keys. Supports pagination. |
| `GET` | `/MAAS/a/v3/ssh-host-keys/{id}` | View global entities | Get one trusted host key. |
| `POST` | `/MAAS/a/v3/ssh-host-keys` | Edit global entities | Add a trusted host key. |
| `PUT` | `/MAAS/a/v3/ssh-host-keys/{id}` | Edit global entities | Replace a trusted host key. Accepts an `If-Match` ETag header. |
| `DELETE` | `/MAAS/a/v3/ssh-host-keys/{id}` | Edit global entities | Remove a trusted host key. Accepts an `If-Match` ETag header. |

Request body fields:

| Field | Required | Description |
|---|---|---|
| `host` | Yes | Host name or IP address. 1–255 characters. Must match the machine's power address exactly. |
| `key_type` | Yes | One of `ssh-rsa`, `ecdsa-sha2-nistp256`, `ecdsa-sha2-nistp384`, `ecdsa-sha2-nistp521`, `ssh-ed25519`, `sk-ecdsa-sha2-nistp256@openssh.com`, `sk-ssh-ed25519@openssh.com`. |
| `public_key` | Yes | Base64-encoded public key, without the key type or comment. |
| `label` | No | Free-text label. Up to 255 characters. |

On a FIPS host, `key_type` and `public_key` must also pass the [public key rules](#public-ssh-keys). Because SSH sessions negotiate only the host key algorithms listed above, store RSA or ECDSA P-256 host keys.

### Public SSH keys

These rules apply on a FIPS host to SSH keys that users add, and to trusted SSH host keys.

| Key type | Allowed |
|---|---|
| `ssh-rsa` | Yes, if the key is 2048 bits or larger |
| `ecdsa-sha2-nistp256` | Yes |
| `ecdsa-sha2-nistp384` | Yes |
| `ecdsa-sha2-nistp521` | Yes |
| Any other type, including `ssh-ed25519` and `ssh-dss` | No |

If MAAS cannot determine the size of an RSA key, it rejects the key.

## Power drivers

On a FIPS host, MAAS validates power configuration when you create or update a machine or a VM host. A failure returns a validation error that includes the reason and a list of compliant drivers. MAAS also logs a `fips_driver_rejected` event when it rejects a driver.

### Driver status

| Driver | FIPS status | Reason |
|---|---|---|
| `amt` | Supported | |
| `hmc` | Supported | |
| `hmcz` | Supported | Requires SSL verification |
| `ipmi` | Supported | Requires cipher suite 17 |
| `lxd` | Supported | |
| `manual` | Supported | |
| `mscm` | Supported | |
| `openbmc` | Supported | |
| `proxmox` | Supported | Requires SSL verification |
| `redfish` | Supported | |
| `virsh` | Supported | |
| `vmware` | Supported | |
| `webhook` | Supported | Requires SSL verification |
| `wedge` | Supported | |
| `apc` | Rejected | SNMPv1, no FIPS-approved authentication |
| `dli` | Rejected | Plain HTTP basic authentication |
| `eaton` | Rejected | SNMPv1, no FIPS-approved authentication |
| `moonshot` | Rejected | IPMI without cipher suite 17 support |
| `msftocs` | Rejected | Plain HTTP basic authentication |
| `raritan` | Rejected | SNMPv2c, community string only |
| `recs_box` | Rejected | Plain HTTP, no TLS |
| `sm15k` | Rejected | Plain HTTP, no TLS |
| `ucsm` | Rejected | HTTP XML API, no TLS |
| Any other driver | Rejected | FIPS compliance not verified |

### Driver settings

| Driver | Setting | Required value |
|---|---|---|
| `ipmi` | `cipher_suite_id` | `17`. If unset, `17` is assumed. Cipher suite 17 uses HMAC-SHA256 and AES-CBC-128. |
| `webhook`, `proxmox`, `hmcz` | `power_verify_ssl` | `y` |

The [password policy](/reference/configuration-guides/security-hardening.md#password-policy) also applies to `power_pass`, because hardening is always active on a FIPS host.

## Fleet drift

| Item | Value |
|---|---|
| Database key | `fips_enabled` |
| Set by | A region controller that starts in FIPS mode |
| Cleared by | Nothing. The flag cannot be cleared with `maas config-hardening`. |
| Violation | `FIPS_CONFIG_STATUS_MISMATCH` on any region controller that is not in FIPS mode while the flag is `true` |

## Log events

FIPS events use the `maas.fips` logger.

| Event | Level | Fields | Emitted when |
|---|---|---|---|
| `fips_mode_detected` | `INFO` | `fips_mode` | A process reads the FIPS state. |
| `fips_mode_unreadable` | `WARNING` | `fips_mode`, `detection_error` | `/proc/sys/crypto/fips_enabled` exists but cannot be read. |
| `fips_tls_handshake` | `INFO` | `cipher_suite`, `protocol_version`, `peer`, `cert_issuer`, `cert_valid` | MAAS completes an outgoing TLS handshake on a FIPS host. |
| `fips_ssh_authentication` | `INFO` | `key_type`, `kex`, `cipher`, `mac`, `peer`, `result` | MAAS completes an SSH connection on a FIPS host. |
| `fips_crypto_error` | `ERROR` | `operation`, `error`, `algorithm`, `peer` | SSH negotiation fails or a host key is not trusted. |
| `fips_driver_rejected` | `ERROR` | `driver`, `reason` | MAAS rejects a power driver. |
