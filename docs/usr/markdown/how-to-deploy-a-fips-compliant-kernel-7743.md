This guide walks you through the steps to deploy an Ubuntu machine with a [FIPS-compliant kernel](https://ubuntu.com/security/certifications/docs/fips). The FIPS kernel comes with all [Ubuntu Pro](https://ubuntu.com/pro) subscriptions for Ubuntu 22.04 LTS. There is also a [tutorial](https://ubuntu.com/tutorials/using-the-ubuntu-pro-client-to-enable-fips#1-overview) on how to get access to the Ubuntu FIPS-compliant kernel.

## Install FIPS kernel

The  kernel FIPS kernel isn't directly integrated into MAAS. Instead, cloud-init is used to first deploy a generic kernel. Then cloud-init installs the FIPS kernel and reboots the machine to enable it. Be aware that after MAAS marks the machine as DEPLOYED, there will be a delay while cloud-init completes and the machine reboots.

## Sequence of events

1. Machine deploys with Ubuntu 22.04 LTS and a generic kernel.
2. Machine reboots.
3. Bootloader instructed to boot from disk.
4. Host requests MAAS for configuration.
5. MAAS sends cloud-init config to host.
6. Cloud-init activates Ubuntu Pro.
7. Ubuntu Pro agent installs the FIPS kernel.
8. Another reboot enables the new kernel.
9. System is ready for use.

## What you'll need

1. Valid Ubuntu Pro token (find yours at [Ubuntu Pro Dashboard](https://ubuntu.com/pro/dashboard)^^*^^).
2. MAAS 3.2 or later with Ubuntu 22.04 LTS images.
3. A host compatible with Ubuntu FIPS-compliant kernel.
4. Internet connection.


Offline installation of the  kernel FIPS-compliant kernel is not supported currently.


## Deploy FIPS kernel

Perform these steps in the MAAS UI:

1. **Enlist and commission the host**: Do this as you normally would.
  
2. **Initiate deployment**: Select the host and click `Deploy`.
  
3. **Choose OS and release**: Opt for `Ubuntu` and `Ubuntu 22.04 LTS "Jammy Jellyfish"`.
  
4. **Configure cloud-init**: Select `Cloud-init user-data` and use the following templates. Replace `<ubuntu_pro_token>` with your valid token.

    1. `cloud-init` >= 24.1

```yaml
    #cloud-config
    ubuntu_pro:
      token: <ubuntu_pro_token>
      enable:
      - fips-updates
```

    2. `cloud-init` < 24.1

```yaml
    #cloud-config
    package_update: true
    package_upgrade: true
    
    runcmd:
    - pro attach <ubuntu_pro_token>
    - yes | pro enable fips-updates
```

5. **Start deployment**: Click `Start deployment for machine`.

## Verify deployment

After deployment, execute these commands on the host to confirm RT kernel activation:

1. Run `cat /proc/sys/crypto/fips_enabled` on the machine. A return value of 1 indicates FIPS mode is active.

2. Check the output of `sudo pro status` to confirm that `fips-preview` and `fips-updates` are enabled.

Your machine should now be up and running with a FIPS-compliant kernel.

