# How to deploy a FIPS-compliant kernel

FIPS (Federal Information Processing Standards) compliance is required in many regulated industries, such as finance, government, and healthcare. Deploying a FIPS kernel through MAAS allows you to run workloads that meet these strict security requirements.

This guide walks you through the steps to deploy an Ubuntu machine with a FIPS-compliant kernel.  
The FIPS kernel comes with all [Ubuntu Pro](https://ubuntu.com/pro) subscriptions for Ubuntu 22.04 LTS.  
There is also a [tutorial](https://ubuntu.com/tutorials/ubuntu-fips) on how to get access to the Ubuntu FIPS-compliant kernel.

## How FIPS deployment works

The FIPS kernel isn’t directly integrated into MAAS. Instead:

1. MAAS deploys a machine with Ubuntu 22.04 LTS and a generic kernel.  
2. The machine reboots.  
3. The bootloader is instructed to boot from disk.  
4. The host requests configuration data from MAAS.  
5. MAAS sends a cloud-init configuration to the host.  
6. Cloud-init activates Ubuntu Pro.  
7. The Ubuntu Pro agent installs the FIPS kernel.  
8. Another reboot enables the new kernel.  
9. The system is ready for use.  

Be aware that after MAAS marks the machine as DEPLOYED, there will be a short delay while `cloud-init` completes and the machine reboots again.

## What you’ll need

- A valid Ubuntu Pro token (find yours in the [Ubuntu Pro Dashboard](https://ubuntu.com/pro/dashboard)).  
- MAAS 3.2 or later with Ubuntu 22.04 LTS images.  
- A host compatible with the Ubuntu FIPS-compliant kernel.  
- An internet connection (offline installation is not supported).  

## Deploy a FIPS kernel

Perform these steps in the MAAS UI:

1. Enlist and commission the host (as you normally would).  
2. Initiate deployment: Select the host and click Deploy.  
3. Choose OS and release: Select *Ubuntu* and *Ubuntu 22.04 LTS (Jammy Jellyfish)*.  
4. Configure cloud-init:  
   Select *Cloud-init user-data* and use one of the following templates.  
   Replace `<ubuntu_pro_token>` with your valid token.  

### For `cloud-init` >= 24.1
```yaml
#cloud-config
ubuntu_pro:
token: <ubuntu_pro_token>
enable:
- fips-updates
```

### For `cloud-init` < 24.1

```yaml
#cloud-config
package_update: true
package_upgrade: true

runcmd:
  - pro attach <ubuntu_pro_token>
  - yes | pro enable fips-updates
```

5. Start deployment: Click Start deployment for the machine.

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

You should see both `fips-preview` and `fips-updates` listed as enabled.

Your machine should now be up and running with a FIPS-compliant kernel.
For more details on Ubuntu Pro and FIPS, refer to the [Ubuntu Pro documentation](https://ubuntu.com/pro/docs).

