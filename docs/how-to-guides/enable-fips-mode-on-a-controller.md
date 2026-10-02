# Enable FIPS mode on a MAAS controller

This guide shows you how to put a MAAS controller host into FIPS mode and confirm that MAAS has detected it. When MAAS detects FIPS mode, it activates security hardening and the FIPS-only controls on that controller.

To deploy a FIPS kernel to a machine that MAAS manages, see [Deploy a FIPS kernel](/how-to-guides/deploy-a-fips-kernel.md) instead.

:::{note}
MAAS is distributed as a snap on the `core26` base. `core26` is not yet FIPS-certified, so the cryptographic libraries inside the snap are not FIPS-validated. The host kernel can still run in FIPS mode, and MAAS applies every FIPS-conditional control. See [FIPS-validated cryptography in the snap](/explanation/fips.md#fips-validated-cryptography-in-the-snap).
:::

## Before you begin

You need:

- An Ubuntu Pro token. Find yours on the [Ubuntu Pro dashboard](https://ubuntu.com/pro/dashboard).
- Administrator (`sudo`) access to the controller host.
- A maintenance window. The host must reboot.

Plan to enable FIPS mode on every controller in the deployment. Once one region controller starts in FIPS mode, every region controller that is not in FIPS mode reports a `FIPS_CONFIG_STATUS_MISMATCH` violation.

## Enable FIPS mode

1. Attach the host to Ubuntu Pro:

   ```bash
   sudo pro attach <ubuntu_pro_token>
   ```

2. Enable the FIPS-updates service:

   ```bash
   sudo pro enable fips-updates
   ```

3. Reboot the host:

   ```bash
   sudo reboot
   ```

## Confirm FIPS mode on the host

After the reboot, check the kernel state:

```bash
cat /proc/sys/crypto/fips_enabled
```

The output is `1` when FIPS mode is active.

## Confirm that MAAS detected FIPS mode

On a region controller, try to turn hardening off:

```bash
sudo maas config-hardening disable
```

On a FIPS host, MAAS refuses with the following message:

```text
Cannot disable hardening on a FIPS-enabled host. Hardening is mandatory when FIPS mode is active.
```

You can also check the startup log:

```bash
journalctl -t maas-regiond | grep -E 'fips_mode_detected|hardening_mode_determined'
```

Look for `fips_mode=True` and `hardening_active=True`.

## Complete the hardening configuration

Hardening is now active on the controller. Any missing prerequisite appears as an error notification for administrators. Run validation to list them:

```bash
sudo maas config-hardening validate
```

To resolve each item, see [Activate MAAS hardening](/how-to-guides/activate-maas-hardening.md#configure-the-hardening-prerequisites).

FIPS mode adds controls that may require further action:

- Replace any public API TLS certificate that uses a weak key or signature. See [Replace a weak TLS certificate](/how-to-guides/resolve-hardening-violations.md#replace-a-weak-tls-certificate).
- Add trusted host keys for machines that use SSH-based power drivers. See [Manage trusted SSH host keys](/how-to-guides/manage-trusted-ssh-host-keys.md).
- Move machines off power drivers that are rejected in FIPS mode. See [Power drivers](/reference/configuration-guides/fips-mode.md#power-drivers).

## Related topics

- [FIPS mode and security hardening](/explanation/fips.md)
- [FIPS mode reference](/reference/configuration-guides/fips-mode.md)
