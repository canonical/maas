# FIPS mode

FIPS (Federal Information Processing Standard) mode is a host kernel feature,
not a MAAS feature. It is enabled on the host operating system via Ubuntu Pro
and signals to all software on that host that only FIPS-approved cryptographic
algorithms and key lengths may be used.

MAAS reads the host FIPS state at startup from `/proc/sys/crypto/fips_enabled`.
A value of `1` means FIPS mode is active. MAAS never enables or disables FIPS
mode itself.

> **Snap install required.** FIPS-certified cryptography is only available
> through the MAAS snap; its `core24` base must run the FIPS-updates
> channel for FIPS-approved cryptographic modules to apply. Debian package
> installs do not currently support FIPS mode.

## FIPS-conditional controls

The following controls activate only when the host kernel is in FIPS mode.

### Security hardening

Security hardening activates automatically when FIPS mode is active, regardless
of the `hardening_enabled` setting. Setting `hardening_enabled=off` does not
override this — the host FIPS state takes precedence.

Hardening covers transport security for the public API, service bind addresses,
and the PostgreSQL connection. See
[Security hardening](/explanation/security.md#security-hardening) for detail.

### Password policy

MAAS enforces password complexity requirements when the host is in FIPS mode.
This applies to passwords set through the CLI (`maas createadmin`,
`maas changepassword`) and the web UI. The same policy also applies when
hardening is explicitly enabled on a non-FIPS host.

See [Password policy](/reference/configuration-guides/security-hardening.md#password-policy)
for the specific rules.

### SSH algorithm restrictions

MAAS-initiated SSH sessions (used by SSH-based power drivers such as HMC, MSCM,
and Wedge) negotiate only FIPS-approved algorithms:

- **Ciphers**: FIPS-approved symmetric ciphers only (per NIST SP 800-131A).
- **Key exchange**: FIPS-approved key exchange methods only (per NIST SP 800-56A).
- **MACs**: FIPS-approved MAC algorithms only (per NIST SP 800-131A).

If the remote host advertises only non-approved algorithms, MAAS rejects the
connection and logs a `fips_crypto_error` event.

### SSH host key verification

On a FIPS host, MAAS enforces strict SSH host key verification. It checks every
SSH connection against a database of trusted host keys and rejects connections
from unrecognised hosts. This replaces the default trust-on-first-use behaviour.

Trusted host keys are managed through the API and web UI. Before connecting to
a machine with an SSH-based power driver, add its host key to the trusted list.
A rejected key is logged with its fingerprint for review.

### Public key type restrictions

MAAS validates public keys against a FIPS-approved allowlist on FIPS hosts:

- **SSH public keys** (added for machine access, or matched against trusted
  host keys): must be RSA (at least 2048 bits) or ECDSA (P-256, P-384, or
  P-521). Ed25519 keys are not accepted.
- **SSL public keys** (used for Windows WinRM access): must be RSA (at
  least 2048 bits) or ECDSA (P-256, P-384, or P-521), signed with SHA-256
  or stronger. DSA keys, weaker signature algorithms, and Ed25519 keys are
  rejected.

### Power driver restrictions

On a FIPS host, the API enforces FIPS compliance on power driver configuration:

- **IPMI**: Only cipher suite 17 is accepted. Cipher suite 17 pairs
  HMAC-SHA256 with AES-CBC-128; all lower suites rely on HMAC-MD5, RC4, or
  SHA-1.
- **Unsupported drivers**: The following drivers are rejected because they
  cannot be made FIPS-compliant: APC, Eaton, Raritan, DLI, MSFTOCS,
  RECS (`recs_box`), SeaMicro (`sm15k`), UCSM, and Moonshot. The API
  returns the rejection reason and a list of supported alternatives.
- **SSL verification**: Drivers that support an SSL verification option
  (Webhook, Proxmox, HMCz) require it enabled (`power_verify_ssl: y`).

Attempting to configure a non-compliant setting returns HTTP 422 with a
structured error identifying the violation.

## Mixed deployments

All controllers in a MAAS deployment must be in the same FIPS state. A
deployment where some controllers have FIPS mode active and others do not is
not supported. Hardening behaviour, password policy, SSH algorithm enforcement,
and power driver validation all differ between FIPS and non-FIPS hosts, so a
mixed deployment produces inconsistent enforcement across the region.

## FIPS on managed machines

Enabling FIPS mode on the controller host is separate from deploying a FIPS
kernel to machines that MAAS manages. For the latter, see
[Deploy a FIPS kernel](/how-to-guides/deploy-a-fips-kernel.md).
