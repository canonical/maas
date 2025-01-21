This page explains how to create a CentOS 7 image with packer.

## Verify requirements

To create a CentOS 7 image to upload to MAAS, you must have a machine running Ubuntu 18.04+ or higher with the ability to run KVM virtual machines. You must also acquire the following items, as described in later instructions:

- qemu-utils
- packer

Note that a suitable CentOS 7 image is downloaded as part of the template.

To deploy the image to MAAS, you must also have:

- MAAS 2.3+
- Curtin 18.1-59+

## Install packer

Packer is easily installed from its Debian package:

```nohighlight
sudo apt install packer
```

This should install with no additional prompts.

## Install dependencies

```nohighlight
sudo apt install qemu-utils
```

## Get the templates

You can obtain the packer templates by cloning the [packer-maas github repository](https://github.com/canonical/packer-maas.git)**^**, like this:

```nohighlight
git clone https://github.com/canonical/packer-maas.git
```

Make sure to pay attention to where the repository is cloned. The Packer template in this cloned repository creates a CentOS 7 AMD64 image for use with MAAS.

This package should install with no additional prompts.

## CentOS 7 template

The packer template in the directory `centos7` subdirectory creates a CentOS 7 AMD64 image for use with MAAS.

## Customise the image

The deployment image may be customized by modifying http/centos7.ks. See the CentOS kickstart documentation for more information.

## Optional proxy

The Packer template downloads the CentOS net installer from the Internet. To tell Packer to use a proxy set the HTTP_PROXY environment variable to your proxy server. Alternatively you may redefine iso_url to a local file, set iso_checksum_type to none to disable checksumming, and remove iso_checksum_url.

To use a proxy during the installation add the --proxy=$HTTP_PROXY flag to every line starting with url or repo in http/centos7.ks. Alternatively you may set the --mirrorlist values to a local mirror.

## Build CentOS 7

You can easily build the image using the Makefile:

```nohighlight
$ make
```

For a few minutes, you will encounter a stream `qemu` text similar to this:

```nohighlight
2022/06/07 13:28:00 packer-builder-qemu plugin: Qemu path: /usr/bin/qemu-system-x86_64, Qemu Image page: /usr/bin/qemu-img
==> qemu: Retrieving ISO
2022/06/07 13:28:00 packer-builder-qemu plugin: Leaving retrieve loop for ISO
2022/06/07 13:28:00 packer-builder-qemu plugin: No floppy files specified. Floppy disk will not be made.
2022/06/07 13:28:00 packer-builder-qemu plugin: No CD files specified. CD disk will not be made.
2022/06/07 13:28:00 packer-builder-qemu plugin: [INFO] Creating disk with Path: output-qemu/packer-qemu and Size: 4G
2022/06/07 13:28:00 packer-builder-qemu plugin: Executing qemu-img: []string{"create", "-f", "qcow2", "output-qemu/packer-qemu", "4G"}
2022/06/07 13:28:00 packer-builder-qemu plugin: stdout: Formatting 'output-qemu/packer-qemu', fmt=qcow2 cluster_size=65536 extended_l2=off compression_type=zlib size=4294967296 lazy_refcounts=off refcount_bits=16
2022/06/07 13:28:00 packer-builder-qemu plugin: stderr:
2022/06/07 13:28:00 packer-builder-qemu plugin: Found available port: 8144 on IP: 0.0.0.0
==> qemu: Starting HTTP server on port 8144
    qemu: No communicator is set; skipping port forwarding setup.
==> qemu: Looking for available port between 5900 and 6000 on 127.0.0.1
2022/06/07 13:28:00 packer-builder-qemu plugin: Looking for available port between 5900 and 6000 on 127.0.0.1
2022/06/07 13:28:00 packer-builder-qemu plugin: Found available port: 5970 on IP: 127.0.0.1
2022/06/07 13:28:00 packer-builder-qemu plugin: Found available VNC port: 5970 on IP: 127.0.0.1
2022/06/07 13:28:00 packer-builder-qemu plugin: Qemu --version output: QEMU emulator version 6.2.0 (Debian 1:6.2+dfsg-2ubuntu6)
2022/06/07 13:28:00 packer-builder-qemu plugin: Copyright (c) 2003-2021 Fabrice Bellard and the QEMU Project developers
2022/06/07 13:28:00 packer-builder-qemu plugin: Qemu version: 6.2.0
==> qemu: Starting VM, booting from CD-ROM
    qemu: view the screen of the VM, connect via VNC without a password to
    qemu: vnc://127.0.0.1:70
2022/06/07 13:28:00 packer-builder-qemu plugin: Qemu Builder has no floppy files, not attaching a floppy.
    qemu: The VM will be run headless, without a GUI. If you want to
    qemu: view the screen of the VM, connect via VNC without a password to
    qemu: vnc://127.0.0.1:70
2022/06/07 13:28:00 packer-builder-qemu plugin: Executing /usr/bin/qemu-system-x86_64: []string{"-netdev", "user,id=user.0", "-vnc", "127.0.0.1:70", "-serial", "stdio", "-device", "virtio-net,netdev=user.0", "-drive", "file=output-qemu/packer-qemu,if=virtio,cache=writeback,discard=ignore,format=qcow2", "-drive", "file=/home/stormrider/mnt/Dropbox/src/git/packer-maas/...
==> qemu: Overriding default Qemu arguments with qemuargs template option...
2022/06/07 13:28:00 packer-builder-qemu plugin: Started Qemu. Pid: 7970
2022/06/07 13:28:00 packer-builder-qemu plugin: Qemu stderr: qemu-system-x86_64: warning: host doesn't support requested feature: CPUID.80000001H:ECX.svm [bit 2]
==> qemu: Waiting 3s for boot...
==> qemu: Connecting to VM via VNC (127.0.0.1:5970)
2022/06/07 13:28:05 packer-builder-qemu plugin: Connected to VNC desktop: QEMU (packer-qemu)
==> qemu: Typing the boot command over VNC...
2022/06/07 13:28:05 packer-builder-qemu plugin: Special code '<up>' found, replacing with: 0xFF52
2022/06/07 13:28:06 packer-builder-qemu plugin: Special code '<tab>' found, replacing with: 0xFF09
2022/06/07 13:28:06 packer-builder-qemu plugin: Sending char ' ', code 0x20, shift false
2022/06/07 13:28:06 packer-builder-qemu plugin: Sending char 'i', code 0x69, shift false
2022/06/07 13:28:06 packer-builder-qemu plugin: Sending char 'n', code 0x6E, shift false
2022/06/07 13:28:06 packer-builder-qemu plugin: Sending char 's', code 0x73, shift false
2022/06/07 13:28:07 packer-builder-qemu plugin: Sending char 't', code 0x74, shift false
2022/06/07 13:28:07 packer-builder-qemu plugin: Sending char '.', code 0x2E, shift false
```

Eventually, the screen will clear and you will see an `anaconda` window. Anaconda is the RedHat installer tool, which is preparing your custom image:

```nohighlight
7) [x] Network configuration             8) [ ] User creation
       (Wired (ens3) connected)                 (No user will be created)
2022/06/07 13:29:19 packer-builder-qemu plugin: Qemu stdout: 
================================================================================
================================================================================
Progress07 13:29:19 packer-builder-qemu plugin: Qemu stdout: 
2022/06/07 13:29:19 packer-builder-qemu plugin: Qemu stdout: 
.022/06/07 13:29:20 packer-builder-qemu plugin: Qemu stdout: 
2022/06/07 13:29:20 packer-builder-qemu plugin: Qemu stdout: Setting up the installation environment
2022/06/07 13:29:20 packer-builder-qemu plugin: Qemu stdout: Setting up com_redhat_kdump addon
2022/06/07 13:29:20 packer-builder-qemu plugin: Qemu stdout: Setting up org_fedora_oscap addon
2022/06/07 13:29:20 packer-builder-qemu plugin: Qemu stdout: ..
2022/06/07 13:29:23 packer-builder-qemu plugin: Qemu stdout: Configuring storage
...2/06/07 13:29:20 packer-builder-qemu plugin: Qemu stdout: 
Running pre-installation scriptser-qemu plugin: Qemu stdout:
.022/06/07 13:29:23 packer-builder-qemu plugin: Qemu stdout: 
Running pre-installation taskslder-qemu plugin: Qemu stdout:
...2/06/07 13:29:24 packer-builder-qemu plugin: Qemu stdout: 
2022/06/07 13:29:24 packer-builder-qemu plugin: Qemu stdout: Installing.
2022/06/07 13:29:25 packer-builder-qemu plugin: Qemu stdout: Starting package installation process
Downloading packagespacker-builder-qemu plugin: Qemu stdout: 
2022/06/07 13:29:29 packer-builder-qemu plugin: Qemu stdout: 

[anaconda]1:main* 2:shell  3:log  4:storage-log >Switch tab: Alt+Tab | Help: F1 :shell  3:log  4:sto><'echo -n "Switch tab: Alt+Tab | Help: F
```

Anaconda will run for three to five minutes. When it finishes, it will clear the screen and return you to the shell prompt.

## OR run manually

Alternatively you can manually run packer. Your current working directory must be in packer-maas/centos7, where this file is located. Once in packer-maas/centos7 you can generate an image with:

```nohighlight
$ sudo PACKER_LOG=1 packer build centos7.json
```


centos7.json is configured to run Packer in headless mode. Only Packer output will be seen. If you wish to see the installation output connect to the VNC port given in the Packer output or change the value of headless to false in centos7.json.


Installation is non-interactive.

## Upload to MAAS

You can upload the CentOS 7 raw packer image with the following command:

```nohighlight
$ maas $PROFILE boot-resources create
name='centos/7-custom' title='CentOS 7 Custom' architecture='amd64/generic' filetype='tgz' content@=centos7.tar.gz
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
open-gannet  nk7x8y  on     Deployed  admin  custom  centos7-raw
```

## Log in to verify

You should log into your newly-deployed image and verify that it has all the customisations you added to the build process. The default username for packer-created CentOS 7 images is `centos`.