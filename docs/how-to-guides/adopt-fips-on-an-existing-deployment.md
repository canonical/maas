# Adopt FIPS mode on an existing deployment

This guide shows you how to prepare a running MAAS deployment before you put its controllers into FIPS mode. Work through it in full, and complete every step before you enable FIPS mode.

::::{important}
Converting a populated deployment is not a supported path to FIPS compliance. MAAS validates cryptographic material only when you create or update it, so material that is already stored is neither checked nor repaired. The supported approach is a new deployment on a host that is already in FIPS mode. See [Adopting FIPS on an existing deployment](/explanation/fips.md#adopting-fips-on-an-existing-deployment).
::::

The conversion is also one-way. As soon as one region controller starts in FIPS mode, every controller that is not in FIPS mode reports a `FIPS_CONFIG_STATUS_MISMATCH` violation, and you cannot clear that state.

## Before you begin

You need:

- Administrator access to MAAS, and a logged-in CLI profile. The examples use `$PROFILE`.
- `sudo` access to every region and rack controller.
- The same MAAS version on every controller. Controllers on different versions cannot communicate.
- A maintenance window. Every controller host must reboot into a FIPS kernel.
- Console or out-of-band access to each power device, in case a power path stops working.

## Step 1: Inventory power drivers

List every machine with its power driver:

```bash
maas $PROFILE machines read | jq -r '.[] | [.hostname, .power_type] | @tsv' | sort -k2
```

Compare the result with the [driver status table](/reference/configuration-guides/fips-mode.md#driver-status). Machines on a rejected driver, such as `apc`, `raritan`, or `sm15k`, are usually powered through a network power distribution unit or a chassis manager, and no software change makes those protocols compliant. Plan to add a compliant BMC, or to replace the power path.

After the cutover, MAAS refuses to create or update a machine that uses a rejected driver, and reports:

```text
Power driver 'apc' is not supported in FIPS mode: SNMPv1 — no FIPS-approved authentication.
```

MAAS does not block power actions for a machine that already uses a rejected driver, but that does not make the machine safe. The host rejects unapproved algorithms once it is in FIPS mode, so the driver may fail anyway, at any point after the cutover. Treat every machine on a rejected driver as both a compliance finding and an availability risk.

## Step 2: Correct stored IPMI cipher suites

In FIPS mode, MAAS accepts only cipher suite 17. A machine that holds the previous default, `3`, fails every power action:

```text
IPMI cipher suite '3' is not FIPS-compliant. Allowed: 17.
```

1. List the stored value for every machine. Entries that show `unset` either use another driver or leave the value unset:

   ```bash
   maas $PROFILE machines power-parameters \
     | jq -r 'to_entries[] | [.key, (.value.cipher_suite_id // "unset")] | @tsv'
   ```

2. For each IPMI machine whose BMC supports suite 17, set the value explicitly:

   ```bash
   maas $PROFILE machine update $SYSTEM_ID power_parameters_cipher_suite_id=17
   ```

3. Change the default that commissioning applies, so that a later commissioning run does not write `3` back:

   ```bash
   maas $PROFILE maas set-config name=maas_auto_ipmi_cipher_suite_id value=17
   ```

4. For a BMC whose firmware does not support suite 17, schedule a firmware update or hardware replacement. Suite 17 is the only approved option, so there is no configuration that makes such a BMC compliant.

::::{warning}
Do this before the cutover. Recommissioning cannot repair a stale cipher suite afterwards: recommissioning needs a power cycle, the power cycle uses the stored cipher suite, and FIPS mode rejects it. The machine then has no in-product route back to a working configuration.
::::

## Step 3: Register trusted SSH host keys

In FIPS mode, MAAS rejects any SSH host key that is not in its trusted list, and the list starts empty. The first power action against every machine that uses the `hmc`, `mscm`, or `wedge` driver fails until you register its key.

Collect and register a key for each of those machines, as described in [Manage trusted SSH host keys](/how-to-guides/manage-trusted-ssh-host-keys.md). Register RSA keys of at least 2048 bits, or ECDSA P-256 keys, because MAAS negotiates only those host key algorithms in FIPS mode.

A missing key produces a `fips_crypto_error` log event with `operation=ssh_host_key_verify`, and the power action reports that MAAS could not make an SSH connection to the device.

## Step 4: Review stored keys and certificates

MAAS does not re-check keys and certificates that are already stored. You'll need to review them yourself.

- **Public API TLS certificate.** This one is checked at startup. A certificate with an unapproved key or signature produces a `WEAK_TLS_CERT_KEY` violation after the cutover. Replace it first. See [Replace a weak TLS certificate](/how-to-guides/resolve-hardening-violations.md#replace-a-weak-tls-certificate).
- **User SSH keys.** Keys are stored per user, and there is no fleet-wide listing. Ask each user to review their own keys and to delete any key that is not an RSA key of at least 2048 bits or an ECDSA key:

  ```bash
  maas $PROFILE sshkeys read | jq -r '.[] | [.id, (.key | split(" ")[0])] | @tsv'
  maas $PROFILE sshkey delete $KEY_ID
  ```

- **User SSL keys.** Review these the same way with `maas $PROFILE sslkeys read`. MAAS uses them for Windows WinRM access.
- **User passwords.** Stored passwords need no action. The [password policy](/reference/configuration-guides/security-hardening.md#password-policy) applies only when a password is set or changed.

## Step 5: Check the platform

- **PostgreSQL.** The database server must run in FIPS mode for the deployment to be compliant end to end. MAAS neither checks nor controls this. If you use `verify-ca` or `verify-full`, confirm that the server certificate carries Subject Alternative Names. See [PostgreSQL server certificate requirements](/reference/configuration-guides/security-hardening.md#postgresql-server-certificate-requirements).
- **Vault.** If you store MAAS secrets in Vault, that server must also run in FIPS mode.
- **API clients.** Clients that cannot negotiate TLS 1.2 or later stop working once TLS is enabled. Upgrade them first.

## Step 6: Enable FIPS mode

1. Enable FIPS mode on every controller host, one at a time, as described in [Enable FIPS mode on a MAAS controller](/how-to-guides/enable-fips-mode-on-a-controller.md). Leaving one controller out leaves the fleet in a permanent mismatch state.

2. After the last controller restarts, validate each one:

   ```bash
   sudo maas config-hardening validate
   ```

3. Resolve any violation. See [Resolve hardening violations](/how-to-guides/resolve-hardening-violations.md).

4. Exercise one machine of each power driver type: query its power state, then power it off and on.

## What MAAS does not fix for you

| Artifact | Behavior after the cutover | Remediation |
|---|---|---|
| Machine on a rejected power driver | MAAS allows power actions, but the host may refuse the algorithms the driver uses. Creating or updating the machine is refused. | Add a compliant BMC, or replace the power path. |
| Stored IPMI cipher suite of `3`, `8`, or `12` | Every power action fails with a fatal error. An unset value is treated as `17`. | Step 2, before the cutover. |
| BMC that cannot do cipher suite 17 | Power actions fail at the BMC. | Firmware update or hardware replacement. |
| Unregistered SSH host key | The first power action against the device fails. | Step 3. |
| User SSH key or SSL key with an unapproved type or size | The key is still used. | Step 4. Delete and re-add compliant keys. |
| Public API TLS certificate with a weak key or signature | Reported as `WEAK_TLS_CERT_KEY`. MAAS keeps running. | Step 4. Reissue the certificate. |
| PostgreSQL or Vault not in FIPS mode | Not detected by MAAS. | Step 5. Operator-managed. |

This list covers the cases we know about. FIPS mode changes the behavior of every cryptographic operation on the host, including operations inside libraries that MAAS calls indirectly, so expect failures that are not listed here. Convert a test deployment first, keep out-of-band access to your hardware, and plan the cutover as a change you may need to reverse.

## Related topics

- [FIPS mode and security hardening](/explanation/fips.md)
- [FIPS mode reference](/reference/configuration-guides/fips-mode.md)
- [Enable FIPS mode on a MAAS controller](/how-to-guides/enable-fips-mode-on-a-controller.md)
