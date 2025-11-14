FIPS (Federal Information Processing Standards) compliance is required in many regulated industries, such as finance, government, and healthcare.  Deploying a FIPS-enabled machine with MAAS allows you to run workloads that meet these strict security requirements.

This guide walks you through the steps to deploy a FIPS-compliant Ubuntu machine.
FIPS packages come with all [Ubuntu Pro](https://ubuntu.com/pro) subscriptions for Ubuntu 22.04 LTS.  You can check the [FIPS certification status](https://ubuntu.com/security/certifications/docs) for other versions of Ubuntu, including guidance on how to access the FIPS-compliant packages.

## How FIPS deployment works

This is the sequence of steps required to enable FIPS during deployment:

1.  MAAS deploys a machine with Ubuntu 22.04 LTS and a generic kernel.
2.  The machine reboots.
3.  The bootloader is instructed to boot from disk.
4.  The host requests configuration data from MAAS.
5.  MAAS sends a cloud-init configuration to the host.
6.  Cloud-init activates Ubuntu Pro.
7.  The Ubuntu Pro agent installs the FIPS boot assets, kernel and other packages.
8.  Another reboot enables the new kernel.
9.  The system is ready for use.

Be aware that after MAAS marks the machine as DEPLOYED, there will be a short delay while `cloud-init` completes and the machine reboots again.

## What you’ll need

- A valid Ubuntu Pro token (find yours in the [Ubuntu Pro Dashboard](https://ubuntu.com/pro/dashboard)).
- MAAS 3.2 or later with Ubuntu 22.04 LTS images.
- A host compatible with the Ubuntu FIPS-compliant kernel.
- An internet connection (offline installation is not supported).

## Deploy a FIPS-enabled machine

Perform these steps in the MAAS UI:

1.  Enlist and commission the host (as you normally would).
2.  Initiate deployment: Select the host and click **Deploy**.
3.  Choose OS and release: Select *Ubuntu* and *Ubuntu 22.04 LTS (Jammy Jellyfish)*.
4.  Configure cloud-init:
   Select *Cloud-init user-data* and use one of the following templates.
   Replace `<ubuntu_pro_token>` with your valid token.

### Configure cloud-init

Use this simple rule based on the **Ubuntu series you’re deploying** (per current -updates):

- **20.04 (Focal) and newer (22.04 Jammy, 24.04 Noble, etc.)** → use the **`ubuntu_pro`** block.
- **18.04 (Bionic) and older** → use the **`runcmd`** block.

> If you’ve customized images or aren’t sure, you can confirm your version with:
> ```bash
> cloud-init --version
> ```
> Use **`ubuntu_pro`** when `cloud-init >= 24.1`; otherwise use **`runcmd`**.

#### `ubuntu_pro` style (Focal/20.04 and newer, or `cloud-init >= 24.1`)
```yaml
#cloud-config
ubuntu_pro:
  token: <ubuntu_pro_token>
  enable:
    - fips-updates
```

#### `runcmd` style (Bionic/18.04 and older, or `cloud-init < 24.1`)
```yaml
#cloud-config
package_update: true
package_upgrade: true

runcmd:
  - pro attach <ubuntu_pro_token>
  - yes | pro enable fips-updates
```

5.  Start deployment: Click **Start deployment** for the machine.

## Verify deployment

After deployment, log into the machine and confirm FIPS activation:

### Check if FIPS mode is active
```bash
cat /proc/sys/crypto/fips_enabled
```
A return value of `1` indicates FIPS mode is active.

### Confirm Pro status
```bash
sudo pro status
```
Look for **`fips`** or **`fips-updates`** listed as enabled (labels vary by series/certification stream).

Your machine should now be up and running with a FIPS-compliant kernel.
For more details on Ubuntu Pro and FIPS, refer to the [Ubuntu Pro overview](https://ubuntu.com/pro) and the [Ubuntu security certifications documentation](https://ubuntu.com/security/certifications/docs).
