This page explains how to build a deployable Ubuntu image with packer.

## Install packer

Packer is easily installed from its Debian package:

```nohighlight
sudo apt install packer
```

This should install with no additional prompts.

## Install dependencies

```nohighlight
sudo apt install qemu-utils
sudo apt install qemu-system
sudo apt install ovmf
sudo apt install cloud-image-utils
```

All of these should install with no additional prompts.

## Get templates

You can obtain the packer templates by cloning the [packer-maas github repository](https://github.com/canonical/packer-maas.git)**^**, like this:

```nohighlight
git clone https://github.com/canonical/packer-maas.git
```

Make sure to pay attention to where the repository is cloned. The Packer template in this cloned repository creates a Ubuntu AMD64 image for use with MAAS.

## Build a raw image

To build a packer image, you must change to the template repository directory, then to the subdirectory for the image you want to build. From that subdirectory, you can easily build a raw image with LVM, using the Makefile:

```nohighlight
$ make custom-ubuntu-lvm.dd.gz
```

This makefile will run for a couple of minutes before attempting to boot the image. While waiting for the image to boot, packer will attempt to SSH into the machine repeatedly until it succeeds. You will see terminal messages similar to this one for upwards of three to five minutes:

```nohighlight
2022/05/09 15:50:46 packer-builder-qemu plugin: [DEBUG] handshaking with SSH
2022/05/09 15:50:50 packer-builder-qemu plugin: [DEBUG] SSH handshake err: ssh: handshake failed: ssh: unable to authenticate, attempted methods [none password], no supported methods remain
2022/05/09 15:50:50 packer-builder-qemu plugin: [DEBUG] Detected authentication error. Increasing handshake attempts.
```

Eventually, you should see a successful SSH connection:

```nohighlight
2022/05/09 15:50:57 packer-builder-qemu plugin: [INFO] Attempting SSH connection to 127.0.0.1:2351...
2022/05/09 15:50:57 packer-builder-qemu plugin: [DEBUG] reconnecting to TCP connection for SSH
2022/05/09 15:50:57 packer-builder-qemu plugin: [DEBUG] handshaking with SSH
2022/05/09 15:51:17 packer-builder-qemu plugin: [DEBUG] handshake complete!
```

If the process seems to run for a long time, you can predict whether it's going to work by doing a series of `netstat -a` on the `IP:port` given in the connection attempt. Attempts may fail repeatedly, but if you repeat the `netstat -a` command frequently, you will see some tentative connections, like this one:

```nohighlight
stormrider@neuromancer:~$ netstat -a | grep 2281
tcp        0      0 0.0.0.0:2281            0.0.0.0:*               LISTEN     
tcp        0      0 localhost:46142         localhost:2281          TIME_WAIT  
tcp        0      0 localhost:46120         localhost:2281          TIME_WAIT  
tcp        0      0 localhost:46138         localhost:2281          TIME_WAIT  
tcp        0      0 localhost:46134         localhost:2281          TIME_WAIT  
tcp        0      0 localhost:46130         localhost:2281          TIME_WAIT  
tcp        0      0 localhost:46124         localhost:2281          TIME_WAIT  
stormrider@neuromancer:~$ netstat -a | grep 2281
tcp        0      0 0.0.0.0:2281            0.0.0.0:*               LISTEN     
tcp        0      0 localhost:46142         localhost:2281          TIME_WAIT  
tcp        0      0 localhost:46146         localhost:2281          ESTABLISHED
tcp        0      0 localhost:2281          localhost:46146         ESTABLISHED
tcp        0      0 localhost:46138         localhost:2281          TIME_WAIT  
tcp        0      0 localhost:46134         localhost:2281          TIME_WAIT  
tcp        0      0 localhost:46130         localhost:2281          TIME_WAIT  
tcp        0      0 localhost:46124         localhost:2281          TIME_WAIT
```

This `ESTABLISHED` connection may not hold the first few times, but eventually, the SSH connection will be made, and the provisioning process will finish. If you want to walk away and come back, be advised that the Makefile clears the terminal buffer at the end, but echoes one final instruction:

```nohighlight
rm OVMF_VARS.fd
```

## Validate the build

You can check the validity of the operation with `ls`, like this:

```nohighlight
stormrider@neuromancer:~/mnt/Dropbox/src/git/packer-maas/ubuntu$ ls
custom-ubuntu-lvm.dd.gz  packages      seeds-lvm.iso     user-data-lvm
http                     packer_cache  ubuntu-flat.json
Makefile                 README.md     ubuntu-lvm.json
meta-data                scripts       user-data-flat
```

## OR run manually

You can also manually run packer. Your current working directory must be in the subdirectory where the packer template is located. In the case of this example, that's `packer-maas/ubuntu`. Once in `packer-maas/ubuntu`, you can generate an image with the following command sequence:

```nohighlight
$ sudo PACKER_LOG=1 packer build ubuntu-lvm.json
```


ubuntu-lvm.json is configured to run Packer in headless mode. Only Packer output will be seen. If you wish to see the installation output connect to the VNC port given in the Packer output, or change the value of headless to false in the JSON file.


This process is non-interactive.

## Upload to MAAS

You can upload an Ubuntu raw packer image with the following command:

```nohighlight
$ maas admin boot-resources create \
    name='custom/ubuntu-raw' \
    title='Ubuntu Custom RAW' \
    architecture='amd64/generic' \
    filetype='ddgz' \
    content@=custom-ubuntu-lvm.dd.gz
```

## Verify the image

Before relying on it in production, you should test your custom image by deploying it to a test (virtual) machine. It's the machine named `open-gannet` in this listing:

```nohighlight
maas admin machines read | jq -r '(["HOSTNAME","SYSID","POWER","STATUS",
"OWNER", "OS", "DISTRO"] | (., map(length*"-"))),
(.[] | [.hostname, .system_id, .power_state, .status_name, .owner // "-",
.osystem, .distro_series]) | @tsv' | column -t

HOSTNAME     SYSID   POWER  STATUS    OWNER  OS      DISTRO
--------     -----   -----  ------    -----  --      ------
valued-moth  e86c7h  on     Deployed  admin  ubuntu  focal
open-gannet  nk7x8y  on     Deployed  admin  custom  ubuntu-raw
```

## Log in to verify

You should log into your newly-deployed image and verify that it has all the customizations you added to the build process. The default username for packer-created images is `ubuntu`, the same as the default username for other MAAS images.

