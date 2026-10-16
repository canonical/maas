# Deploy a FIPS kernel

This guide shows you how to deploy an Ubuntu machine with the [FIPS-certified kernel](https://ubuntu.com/security/certifications/docs/fips). The kernel is available with an [Ubuntu Pro](https://ubuntu.com/pro) subscription.

This guide covers machines that MAAS deploys. To put a MAAS controller into FIPS mode, see [Enable FIPS mode on a MAAS controller](/how-to-guides/enable-fips-mode-on-a-controller.md).

## How it works

MAAS does not install the FIPS kernel directly. Instead, MAAS deploys Ubuntu with a generic kernel and passes cloud-init user data to the machine. Cloud-init then attaches Ubuntu Pro, installs the FIPS kernel, and reboots the machine.

The sequence is:

1. MAAS deploys Ubuntu 22.04 LTS with a generic kernel.
2. The machine reboots and boots from its disk.
3. The machine requests its configuration from MAAS, and MAAS returns the cloud-init user data.
4. Cloud-init attaches Ubuntu Pro and enables the FIPS-updates service.
5. The machine reboots into the FIPS kernel.

MAAS marks the machine as **Deployed** before cloud-init finishes. Expect a further delay while cloud-init completes and the machine reboots.

## Before you begin

You need:

- An Ubuntu Pro token. Find yours on the [Ubuntu Pro dashboard](https://ubuntu.com/pro/dashboard).
- Ubuntu 22.04 LTS images synchronized in MAAS.
- A machine whose hardware is compatible with the Ubuntu FIPS kernel.
- Internet access from the machine. Offline installation of the FIPS kernel is not supported.

## Deploy the machine

1. Commission the machine as usual.
2. Select the machine and choose **Deploy**.
3. Select **Ubuntu** and **Ubuntu 22.04 LTS "Jammy Jellyfish"**.
4. Select **Cloud-init user-data** and paste the template that matches the cloud-init version in your image. Replace `<ubuntu_pro_token>` with your token.

   For cloud-init 24.1 or later:

   ```yaml
   #cloud-config
   ubuntu_pro:
     token: <ubuntu_pro_token>
     enable:
     - fips-updates
   ```

   For cloud-init earlier than 24.1:

   ```yaml
   #cloud-config
   package_update: true
   package_upgrade: true

   runcmd:
   - pro attach <ubuntu_pro_token>
   - yes | pro enable fips-updates
   ```

5. Select **Start deployment for machine**.

## Verify the deployment

After the final reboot, log in to the machine and run these checks:

1. Confirm that the kernel is in FIPS mode:

   ```bash
   cat /proc/sys/crypto/fips_enabled
   ```

   The output is `1` when FIPS mode is active.

2. Confirm that the FIPS-updates service is enabled:

   ```bash
   sudo pro status
   ```

   The `fips-updates` row shows `enabled`.

## Related topics

- [Using the Ubuntu Pro client to enable FIPS](https://ubuntu.com/tutorials/using-the-ubuntu-pro-client-to-enable-fips)
- [FIPS mode and security hardening](/explanation/fips.md)
