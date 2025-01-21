MAAS Image Builder is an older tool, still required to build Windows images.  This page explains how to use it.

> In order to use MAAS Image Builder, you must purchase [Ubuntu Pro](https://ubuntu.com/pricing/pro)**^**.

You can customise most images as much or as little as you wish, then use them to commission machines with MAAS. 

To get MAAS Image Builder, you must be subscribed to a private PPA provided by Canonical Support to those customers who have purchased [Ubuntu Pro](https://ubuntu.com/pricing/pro)**^**. Note that the steps below will fail if you have not purchased Ubuntu Advantage and been subscribed to the private PPA by your Canonical support rep.

Once subscribed, you need to obtain your credentials at this external link:

https://launchpad.net/~/+archivesubscriptions

Also, you must add the repository with the <code>add-apt-repository</code> command. Note: Be sure to substitute your unique URL in the command below:

   ```nohighlight
$ sudo add-apt-repository \
    “https://LaunchpadID:Password@private-ppa.launchpad.net/maas-image-builder-partners/stable/ubuntu"
   ```
	
Once you have added the private PPA, you can install the Image Builder like this:

   ```nohighlight
    $ sudo apt-get install maas-image-builder
   ```
	
All done? Great!  Now you can build and customise images for MAAS machines, as shown in the sections below.

## Create Windows images

Since Windows is a proprietary operating system, MAAS can't download these images. You need to manually generate images to use with MAAS by using Windows ISO images. On the upside, the end result will be much simpler, since there are CLI and WebUI tools to upload a Windows image -- which _helps_ automate the process.

You can obtain Windows ISO images at the Microsoft Evaluation Center:

https://www.microsoft.com/en-us/evalcenter **^*

<b>Windows editions</b>

There are several Windows editions/install options supported by `maas-image-builder` (`--windows-edition` options):

- `win2008r2`
- `win2008hvr2`
- `win2012`
- `win2012hv`
- `win2012r2`
- `win2012hvr2`
- `win2016`
- `win2016-core`
- `win2016hv`
- `win2016dc`
- `win2016dc-core`
- `win2019`
- `win2019-core`
- `win2019dc`
- `win2019dc-core`
- `win10ent`
- `win10ent-eval`
- `win2022`
- `win2022-core`

The examples in this section use Windows Hyper-V 2012 R2.

## MIB for Windows

MAAS Image Builder (also known as "MIB") can automate the process of generating images for MAAS and <code>curtin</code>.

Note, though, you may need Windows drivers to deploy the image on your specific hardware (see the `--windows-drivers` option).

In order to obtain Windows updates, provide the <code>--windows-updates</code> option (and sufficient disk space, depending on the Windows edition/updates size, with the <code>--disk-size</code> option). This requires access to a bridged connection with a DHCP server (provide a network interface with the <code>maas-image-builder -i</code> option).

Important: <b>UEFI and BIOS</b> systems require different Windows images, built with or without the `--uefi` option, respectively.
(Windows ISO images in UEFI mode usually require connecting using a VNC client early to press any key to start Windows setup; see below.)

Important: <b>LXD Virtual Machines</b> require an UEFI image (`--uefi`) and VirtIO drivers (`--windows-drivers`).
(In order to use/test the VirtIO drivers during image build, not just during image deploy, use `--virtio` and `--driver-store`.)

    ```nohighlight
    sudo maas-image-builder -o windows-win2012hvr2-amd64-root-dd windows \
    --windows-iso win2012hvr2.iso  --windows-edition win2012hvr2 \
    --windows-language en-US \
    [--windows-drivers ~/Win2012hvr2_x64/DRIVERS/] \
    [--windows-updates] [--disk-size 128G] \
    [--uefi] [--virtio] [--driver-store]
	```

## Windows options

MAAS Image Builder options for Windows images can be listed with the following command:

```nohighlight
	sudo maas-image-builder -o windows --help
```

Note that this is different from the MAAS Image Builder generic/image-independent options, which can be listed with the following command:

```nohighlight
	sudo maas-image-builder --help
```

Some of the Windows-specific options include:

- `--windows-iso`: path to the Windows ISO image.
- `--windows-edition`: identifier for the Windows edition/option being installed (see above).
- `--windows-license-key`: Windows license key (required with non-evaluation editions)
- `--windows-language`: Windows installation language (default: `en-US`)
- `--windows-updates`: download and install Windows Updates (requires internet access; might require a larger `--disk-size` option)
- `--windows-drivers`: path to directory with Windows drivers to be installed (requires internet access; uses the Windows Driver Kit, by default)
- `--driver-store`: combined with `--windows-drivers`, uses the Windows Driver Store to install drivers early into Windows Setup and image (does not require internet access; does not use the Windows Driver Kit).

Some Windows-specific platform options:

- `--uefi`: use UEFI partition layout and firmware
- `--virtio`: use paravirtualized VirtIO SCSI and VirtIO NET devices (instead of emulated devices) for installation (requires `--windows-drivers`)
- `--disk-size`: specify the (virtual) disk size for Windows setup (must be larger for `--windows-updates`; increases deployment/copy-to-disk time, and is expanded to physical disk size during deployment)

## Debugging

You can debug the Windows installation process by connecting to <code>localhost:5901</code> using a VNC client (e.g., `vncviewer`).

You can pause the Windows installation process at the last step for inspection/debugging in PowerShell with the `--powershell` option.

## Installing in MAAS

The generated images need to be placed into the correct directories so MAAS can deploy them onto a node:

```nohighlight
    maas admin boot-resources create name=windows/win2012hvr2 \
    architecture=amd64/generic filetype=ddtgz \ 
    content@=./build-output/windows-win2012hvr2-amd64-root-dd 
```

Now, using the MAAS WebUI, a node can be selected to use Windows Hyper-V 2012 R2. This selection gets reset when a node is stopped, so make sure to set it _before_ starting nodes. You can also set the default operating system (and release) in the settings menu, which removes the need to set it per-node.