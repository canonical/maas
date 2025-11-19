Real-time (RT) kernels reduce latency for workloads where timing is critical, such as telecom, financial services, and robotics.  MAAS can deploy RT kernels by combining Ubuntu Pro with cloud-init.

Learn more about [the Ubuntu RT kernel](https://documentation.ubuntu.com/real-time/latest/reference/releases/).

## Prerequisites

Before you begin, make sure you have:

* A valid Ubuntu Pro subscription (the RT kernel is enabled through Ubuntu Pro).
   Find your token in the [Ubuntu Pro dashboard](https://ubuntu.com/pro/dashboard).
* MAAS 3.2 or later with [one of these releases](https://documentation.ubuntu.com/real-time/latest/reference/releases/).
* A machine that is already enlisted and commissioned in MAAS.
* Internet access (offline installation is not supported).

> If you are not familiar with Ubuntu Pro in MAAS, review the [Ubuntu Pro overview](https://ubuntu.com/pro) before you start.

## How it works

The RT kernel is not built into MAAS images.  Instead:

1.  MAAS deploys the machine with a generic Ubuntu kernel.
2. cloud-init attaches the machine to Ubuntu Pro and enables the RT kernel.
3.  The machine reboots, and the new RT kernel is activated.

## Steps to deploy

1.  Select the machine in the MAAS UI

   * Enlist and commission as usual if you haven’t already.
   * Choose *Deploy*.

2.  Choose operating system

   * Select [one of the valid kernels](https://documentation.ubuntu.com/real-time/latest/reference/releases/).

3.  Configure cloud-init:
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

4.  Start deployment

   * Click *Start deployment*.
   * Be aware: MAAS may show the machine as *Deployed* before cloud-init finishes the kernel change and the reboot.

## Verify deployment

After the machine finishes rebooting, verify the RT kernel is active:

1.  Check Ubuntu Pro status:

```bash
sudo pro status
```

Look for `realtime-kernel` in the list of enabled services.

2.  Check kernel version:

```bash
uname -a
```

The kernel string should confirm that the RT kernel is running.

Your machine is now deployed with a real-time kernel and ready for latency-sensitive workloads.


