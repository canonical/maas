# FIPS mode and security hardening

MAAS supports two related security mechanisms: FIPS mode and security hardening. They are often enabled together, but they are not the same thing. This page explains what each one is, how they interact, and why MAAS behaves the way it does when a requirement is not met.

For step-by-step instructions, see [Activate MAAS hardening](/how-to-guides/activate-maas-hardening.md). For exact settings, codes, and algorithms, see the [Security hardening reference](/reference/configuration-guides/security-hardening.md) and the [FIPS mode reference](/reference/configuration-guides/fips-mode.md).

## Two mechanisms, two owners

**FIPS mode** belongs to the operating system. FIPS (Federal Information Processing Standard) 140 defines which cryptographic algorithms and key lengths a system may use. On Ubuntu, you enable FIPS mode through Ubuntu Pro. The kernel then reports its state in `/proc/sys/crypto/fips_enabled`. MAAS reads that file, but it never enables or disables FIPS mode itself.

**Security hardening** belongs to MAAS. It is a set of transport-security controls, aligned with STIG and CIS benchmarks, that MAAS applies to its own services. Hardening controls *where* MAAS listens and *how* clients reach it, rather than which algorithms are allowed.

| | FIPS mode | Security hardening |
|---|---|---|
| Owned by | The host operating system | MAAS |
| Turned on by | Ubuntu Pro (`pro enable fips-updates`) | The `hardening_enabled` setting, or FIPS mode |
| Main concern | Approved cryptographic algorithms | Transport security and exposed surface |
| Scope | Every process on the host | MAAS services on that controller |

## How the two interact

FIPS mode implies hardening. When a controller's kernel is in FIPS mode, MAAS activates hardening on that controller, whatever the `hardening_enabled` setting says. You cannot turn hardening off on a FIPS host.

Hardening does not imply FIPS mode. You can activate hardening on a host that is not in FIPS mode. This is useful when you need STIG or CIS transport controls but do not have a FIPS requirement.

In summary, a controller ends up in one of three states:

- **FIPS mode**: hardening is active, and the FIPS-only controls also apply.
- **Not in FIPS mode, `hardening_enabled` is `on`**: hardening is active.
- **Not in FIPS mode, `hardening_enabled` is `auto` or `off`**: hardening is inactive.

### What hardening adds

When hardening is active, MAAS:

- Expects the public API to be served over TLS.
- Refuses to treat "all interfaces" as an acceptable listen address for its services.
- Expects the PostgreSQL connection to verify the database server's certificate.
- Adds browser security headers to every web response and rejects `TRACE` and `OPTIONS` requests.
- Hides the DNS server version and applies safe defaults for zone transfers and recursive fetch limits.
- Enforces a password complexity policy for MAAS users and for power driver credentials.

### What FIPS mode adds on top

When the kernel is in FIPS mode, MAAS also restricts cryptography:

- MAAS-initiated SSH sessions negotiate only FIPS-approved algorithms.
- SSH connections to power devices require a trusted host key, rather than accepting any key on first use.
- SSH and SSL keys that users add must use approved key types and sizes.
- The public API TLS certificate must use an approved key and signature algorithm.
- Power drivers that cannot communicate securely are rejected.
- The web server offers only FIPS-approved TLS cipher suites.

## A posture, not a gate

MAAS validates its hardening prerequisites when a region controller starts. If a prerequisite is missing, MAAS still starts.

This is deliberate. A controller that refuses to boot over a single missing setting takes your infrastructure offline, and it hides the cause in a service log. A controller that keeps running and reports the problem gives you a visible, fixable signal instead.

MAAS reports each unmet prerequisite in two ways:

- As an error notification for administrators in the web UI and API.
- As an `ERROR` entry in the controller log.

Hardening notifications cannot be dismissed. A compliance finding should be fixed, not acknowledged. Compare this with the certificate expiry notification, which is a reminder and can be dismissed. When you correct a setting and restart MAAS, the matching notification disappears.

You can also run `maas config-hardening validate` at any time. It runs the same checks and exits with a non-zero status when a violation exists. This makes it useful for automation and as audit evidence.

## When hardening state is decided

Each MAAS process decides whether hardening is active once, when it starts. The decision does not change while the process runs. As a result:

- Changes to `hardening_enabled` take effect after you restart MAAS.
- Changes to bind addresses, TLS, and database settings take effect after a restart, and their notifications update at the same time.

## Region and rack controllers

Region and rack controllers read the hardening setting from different places:

- **Region controllers** read `hardening_enabled` from the MAAS database. One setting applies to every region controller.
- **Rack controllers** read `hardening_enabled` from their local `rackd.conf` file. Each rack controller has its own setting.

The difference follows from the architecture. A rack controller has no direct database access, and it must decide its posture before it connects to a region.

Rack controllers also report differently. A rack controller applies its own controls, such as its own bind addresses, but it has no channel for posting notifications to the region. Rack-side violations therefore do not appear in the web UI. To audit a rack controller, run the validation command on that rack controller. See [Harden a rack controller](/how-to-guides/harden-a-rack-controller.md).

## Keeping a fleet consistent

All controllers in a MAAS deployment should share the same FIPS state. MAAS helps you to detect drift.

The first time a region controller starts in FIPS mode, MAAS records that fact in the database as `fips_enabled`. From then on, every region controller whose kernel is not in FIPS mode reports a `FIPS_CONFIG_STATUS_MISMATCH` violation. You cannot clear the flag with `maas config-hardening`. The only resolution is to enable FIPS mode on the mismatched host.

The flag works in one direction only. It exists to stop a deployment from quietly drifting out of compliance after it has adopted FIPS. MAAS does not block a mismatch, consistent with the posture model, but an uncorrected mismatch leaves enforcement uneven across the fleet.

## FIPS-validated cryptography in the snap

MAAS is distributed as a snap that runs on the `core26` base. The base supplies the cryptographic libraries that MAAS uses at runtime.

For those libraries to be FIPS-validated, the snap base must come from a FIPS-updates channel. At the time of writing, `core26` is not yet FIPS-certified, and no FIPS-updates channel exists for it. Canonical expects certification in late 2027.

Until then, the following is true on a snap install:

- The host kernel can be in FIPS mode.
- MAAS detects FIPS mode and applies every FIPS-conditional control described on this page.
- The cryptographic libraries bundled in the snap are not themselves FIPS-validated.

Track the current status at [Ubuntu security certifications](https://ubuntu.com/security/certifications).

## Controllers versus deployed machines

Enabling FIPS mode on a MAAS controller does not affect the machines that MAAS deploys. Deploying a FIPS kernel to a managed machine is a separate task. See [Deploy a FIPS kernel](/how-to-guides/deploy-a-fips-kernel.md).
