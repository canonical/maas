> *Errors or typos? Topics missing? Hard to read? <a href="https://docs.google.com/forms/d/e/1FAIpQLScIt3ffetkaKW3gDv6FDk7CfUTNYP_HGmqQotSTtj2htKkVBw/viewform?usp=pp_url&entry.1739714854=https://maas.io/docs/deploying-a-real-time-kernel" target = "_blank">Let us know.</a>*

This page walks you through the steps to deploy an Ubuntu machine with a [real-time (RT) kernel](https://ubuntu.com/blog/real-time-linux-qa). The RT kernel comes with all [Ubuntu Pro](https://ubuntu.com/pro) subscriptions for Ubuntu 22.04 LTS.

> The RT kernel is currently in Beta. General availability is coming soon.

## RT kernel install

The RT kernel isn't directly integrated into MAAS. Instead, cloud-init is used to first deploy a generic kernel. Then cloud-init installs the RT kernel and reboots the machine to enable it. Be aware that after MAAS marks the machine as DEPLOYED, there will be a delay while cloud-init completes and the machine reboots.

## Sequence of events

1. Machine deploys with Ubuntu 22.04 LTS and a generic kernel.
2. Machine reboots.
3. Bootloader instructed to boot from disk.
4. Host requests MAAS for configuration.
5. MAAS sends cloud-init config to host.
6. Cloud-init activates Ubuntu Pro.
7. Ubuntu Pro agent installs the RT kernel.
8. Another reboot to enable the new kernel.
9. System is ready for use.

## What you'll need

1. Valid Ubuntu Pro token (find yours at [Ubuntu Pro Dashboard](https://ubuntu.com/pro/dashboard)^^*^^).
2. MAAS 3.2 or later with Ubuntu 22.04 LTS images.
3. A host compatible with Ubuntu RT kernel.
4. Internet connection.


Offline installation of the RT kernel is not supported currently.


## RT kernel deployment

Perform these steps in the MAAS UI:

1. **Enlist and commission the host**: Do this as you normally would.
  
2. **Initiate deployment**: Select the host and click `Deploy`.
  
3. **Choose OS and release**: Opt for `Ubuntu` and `Ubuntu 22.04 LTS "Jammy Jellyfish"`.
  
4. **Configure cloud-init**: Select `Cloud-init user-data` and use the following templates. Replace `<ubuntu_pro_token>` with your valid token.

    1. `cloud-init` >= 23.4 

```yaml
    #cloud-config
    ubuntu_advantage:
      token: <ubuntu_pro_token>
      enable:
      - realtime-kernel
```

    2. `cloud-init` < 23.4

```yaml
    #cloud-config
    package_update: true
    package_upgrade: true
    
    runcmd:
    - pro attach <ubuntu_pro_token>
    - yes | pro enable realtime-kernel
```

5. **Start deployment**: Click `Start deployment for machine`.

## Verifying deployment

After deployment, execute these commands on the host to confirm RT kernel activation:

1. Check Pro status
```text
    sudo pro status
```
    You should see `realtime-kernel` as enabled.
  
2. Confirm kernel version
```nohighlight
    uname -a
```

Your machine should now be up and running with an RT kernel.