MAAS is much more useful when you can upload images that aren't gathered from [the MAAS image repository](http://images.maas.io/)**^**, deploy them to MAAS-managed machines, and count on them to work properly. But there's a problem: the typical, off-the-shelf ISO image can't just be uploaded to MAAS and deployed to a machine. For one thing, the machines couldn't write the image to their disks or boot the images once they're there. For another, any non-standard configuration items (networking, storage, users, added software) wouldn't be loaded.

We can help guide you in preparing ISO images to run on MAAS machines. Usable MAAS images need both a `curtin` hook script (to write and boot the image), and some `cloud-init` meta-data (to configure the image beyond the out-of-the-box experience). As long as a prepared image meets these requirements, you can successfully upload it to MAAS, deploy it to a machine, and expect it to run properly on that machine.

This explains how MAAS images differ from a standard ISO, and what has to happen to make those off-the-shelf ISOs deployable and usable by MAAS.

## Transforming an ISO

When it comes to creating images for MAAS machines, you can hand-build images, as long as they meet the `curtin` and `cloud-init` requirements; or you can use a third-party tool called  [packer](https://www.packer.io)**^** to prepare special versions of these images that will work with MAAS. There are also static Ubuntu images targeted at older MAAS versions (<3.1). Beyond providing a bit of technical detail here, we won't shepherd you through hand-building images: you're pretty much on your own there. We will try to help you understand how to create and customise MAAS-friendly images, mostly focusing on packer templates.

We maintain a [git repo](https://github.com/canonical/packer-maas)**^** of packer templates for a few popular operating systems. You can check out this graphic of a real, running lab MAAS instance to get an idea:

![image](https://discourse-maas-io-uploads.s3.us-east-1.amazonaws.com/original/2X/a/a80ed5eb191a798d049cb82fade4ee117f5128fd.png)

Packer uses templates (built in HCL2) to run different build, provisioning, and post-processing tools that produce an image MAAS can deploy -- one that you can successfully access and use. These tools might be as simple as a shell command, or as specialised as the RedHat `anaconda` installer. It really just depends on what's needed to prepare an image so that MAAS can deploy it.

We encourage and document custom images -- and help informally as much as we can -- but we're really not able to offer much support. After all, other OS images are built from code we don't own, and licensed in ways that may or may not be compatible with a MAAS deployment. For those reasons, among others, we recommend you customise machines using `cloud-init` user_data and/or `curtin` preseed data, whenever you can, instead of creating a custom image.


That warning bears repeating: While it may be possible to deploy a certain image with MAAS, the particular use case may not be supported by that image’s vendor due to licensing or technical reasons. Canonical recommends that, whenever possible, you should customise machines using `cloud-init` user_data or `curtin` preseed data, instead of creating a custom image.


There are two types of custom images we'll explain here: static Ubuntu images (just below) and [packer images](#heading--about-packer).

## Static Ubuntu images

MAAS provides the capability for you to build a static Ubuntu OS image to deploy with MAAS, using any image-building method you choose. You can create the image once, with a fixed configuration, and deploy it to many machines. This fixed configuration can consist of anything that a normal image would contain: users, packages, etc. This capability is really targeted at older versions of MAAS, but it should work with MAAS of any vintage.

If you're using newer versions of MAAS (>3.0), we recommend choosing packer, since the packer-maas repository already has a built-in Ubuntu image you can customise -- but the choice is yours.

## Uploading hand-built Ubuntu images

You can upload hand-built Ubuntu images, containing a kernel, bootloader, and a fixed configuration, for deployment to multiple machines. The image can be built via a tool, such as [packer](https://www.packer.io)**^**, or build with scripts. You can upload these images to the boot-resources endpoint, where it will then be available for deployment to machines.

At a minimum, this image must contain a kernel, a bootloader, and a `/curtin/curtin-hooks` script that configures the network. A sample can be found in the [packer-maas repos](https://github.com/canonical/packer-maas/tree/master/ubuntu/scripts)**^**. The image must be in raw img file format, since that is the format MAAS accepts for upload. This is the most portable format, and the format most builders support. Upon completing the image build, you will upload this img file to the boot-resources endpoint, specifying the architecture for the image.

## How MAAS handles static Ubuntu images

MAAS will save the image -- in the same way it would save a `tar.gz` file -- in the database. MAAS can differentiate between custom Ubuntu images and custom non-Ubuntu images, generating appropriate pre-seed configurations for each image type.

MAAS will also recognise the base Ubuntu version, so it can apply the correct ephemeral OS version for installation. Custom images are always deployed with the ephemeral operating system. The base_image field is used to select the appropriate version of the ephemeral OS to avoid errors. This ensures a smooth deployment later.

## How MAAS boots static Ubuntu images

When you decide to deploy a machine with your uploaded, custom image, MAAS ensures that the machine receives the kernel, bootloader and root file system provided in the image. The initial boot loader takes over, and boots an ephemeral OS of the same Ubuntu version as the custom image, to reduce the chances of incompatibilities. Curtin then writes your entire custom image to disk. Once the custom image is written to disk, it is not modified by MAAS.

Note that custom non-Ubuntu images still use a standard Ubuntu ephemeral OS to boot, prior to installing the non-Ubuntu OS.

## Configuring deployed machine networking

If you deploy a machine with a custom Ubuntu image, MAAS allows you to configure the deployed machine's networks just like you would for any other MAAS machine. If you create an interface and assign it to a subnet or static address, this will be reflected in the deployed machine.

For this reason, MAAS also does some initial diagnostics while installing the custom image. MAAS will detect when a network configuration is not present and abort the installation with a warning. Essentially, MAAS checks to be sure that `cloud-init` and `netplan` are present in the images written by `curtin`. If not, MAAS won't deploy the machine with the image.

## Configuring deployed machine storage

If you deploy a machine with a custom Ubuntu image, you will also want to be able to configure storage, just like you would do with any other machine. MAAS facilitates changes to the storage configuration. You can resize the root partition, as well as attaching and formatting any additional block devices you may desire.

## Static image metrics

As a user, you want to keep track of how many static images are being used, and how many deployed machines are using static images. The standard MAAS dashboard reflects both of these metrics.

## Packer

The [packer documentation](https://www.packer.io/docs)**^** has an excellent, in-depth discussion of what packer does, how it works, and where it is limited. Simply put, packer creates OS images that can be uploaded and deployed using MAAS. We can summarise packer with the following flowchart:

![image](https://discourse-maas-io-uploads.s3.us-east-1.amazonaws.com/original/2X/4/47cb177f4ee2f52ac00c877449770a23cfa0c9b4.jpeg)

We can walk through packer operation like this:

 - A template is created or obtained which drives the packer build. The [packer-maas](https://github.com/canonical/packer-maas)**^** repository uses HCL2 templates.

 - The template specifies packer commands and data sources.

 - The template specifies a builder, which creates the MAAS-consumable images.

 - Multiple builds can run in parallel. Within the MAAS domain, we typically don't set templates up that way, but it is possible to do so.

 - Provisioners spin up a running version of the image and add things that make it usable, like `curtin` hooks, `cloud-init` meta-data to install custom packages, and so on.

 - Post-processors do things to the built image to make it usable, e.g., compressing the file into a `tar.gz` image.

 - Because packer creates a wide-range of load packages, the results are called "artefacts" in packer terminology. MAAS simply refers to these as "images".

Note that we said this flow is linear. You can see that provisioners might need to run before a post-processor creates an uploadable `tar.gz` image. The actual flow depends on the template, which depends on the OS being customised into an image. In the parlance of packer, all of these components -- builders, post-processors, provisioners -- are sometimes referred to collectively as "plugins".
    
## Packer dependencies

Depending upon which image you are building, packer-maas may require various dependencies. For example, when customising an Ubuntu image, you'd need to install the following dependencies:

 - qemu-utils
 - qemu-system
 - ovmf
 - cloud-image-utils

These dependencies -- and the functionality they provide -- will be explained in the specific image sections which follow.

## Packer templates

A [packer template](https://www.packer.io/docs/templates)**^** could just as easily be called a "packer script". It contains declarations and commands that sequence and configure plugins. Templates also have built-in functions to help you customise your artefacts. Our packer-maas templates are implemented in HCL2.

Templates are run by the packer `build` command. Within packer-maas, packer commands (like `build`) are collected into makefiles that prevent you from having to know a lot about how packer works. Even so, it's beneficial to take a quick tour of how a typical packer template works. Let's use the [ubuntu-cloudimg](https://github.com/canonical/packer-maas/blob/master/ubuntu/ubuntu-cloudimg.pkr.hcl)**^** template as a simple example.


Building workable templates can be extremely difficult. This section is intended to familiarise you with templates and their components so that you can possibly pinpoint bugs in community-provided templates. If you want to build your own template, you should rely on the [packer documentation](https://www.packer.io/docs)**^** as your guide.


This template builds a customised Ubuntu image with packer:

```nohighlight
packer {
  required_version = ">= 1.7.0"
  required_plugins {
    qemu = {
      version = "~> 1.0"
      source  = "github.com/hashicorp/qemu"
    }
  }
}

variable "ubuntu_series" {
  type        = string
  default     = "focal"
  description = "The codename of the Ubuntu series to build."
}

variable "filename" {
  type        = string
  default     = "custom-cloudimg.tar.gz"
  description = "The filename of the tarball to produce"
}

variable "kernel" {
  type        = string
  default     = ""
  description = "The package name of the kernel to install. May include version string, e.g linux-image-generic-hwe-22.04=5.15.0.41.43"
}

variable "customize_script" {
  type        = string
  description = "The filename of the script that will run in the VM to customize the image."
}

variable "architecture" {
  type        = string
  default     = "amd64"
  description = "The architecture to build the image for (amd64 or arm64)"
}

variable "headless" {
  type        = bool
  default     = true
  description = "Whether VNC viewer should not be launched."
}

variable "http_directory" {
  type        = string
  default     = "http"
  description = "Directory for files to be accessed over http in the VM."
}

variable "http_proxy" {
  type        = string
  default     = "${env("http_proxy")}"
  description = "HTTP proxy to use when customising the image inside the VM. The http_proxy environment is set, and apt is configured to use the http proxy"
}

variable "https_proxy" {
  type        = string
  default     = "${env("https_proxy")}"
  description = "HTTPS proxy to use when customising the image inside the VM. The https_proxy environment is set, and apt is configured to use the https proxy"
}

variable "no_proxy" {
  type        = string
  default     = "${env("no_proxy")}"
  description = "NO_PROXY environment to use when customising the image inside the VM."
}

variable "ssh_password" {
  type        = string
  default     = "ubuntu"
  description = "SSH password to use to connect to the VM to customize the image. Needs to match the hashed password in user-data-cloudimg."
}

variable "ssh_username" {
  type        = string
  default     = "root"
  description = "SSH user to use to connect to the VM to customize the image. Needs to match the user in user-data-cloudimg."
}

locals {
  qemu_arch = {
    "amd64" = "x86_64"
    "arm64" = "aarch64"
  }
  uefi_imp = {
    "amd64" = "OVMF"
    "arm64" = "AAVMF"
  }
  qemu_machine = {
    "amd64" = "ubuntu,accel=kvm"
    "arm64" = "virt"
  }
  qemu_cpu = {
    "amd64" = "host"
    "arm64" = "cortex-a57"
  }

  proxy_env = [
    "http_proxy=${var.http_proxy}",
    "https_proxy=${var.https_proxy}",
    "no_proxy=${var.https_proxy}",
  ]
}


source "qemu" "cloudimg" {
  boot_wait      = "2s"
  cpus           = 2
  disk_image     = true
  disk_size      = "4G"
  format         = "qcow2"
  headless       = var.headless
  http_directory = var.http_directory
  iso_checksum   = "file:https://cloud-images.ubuntu.com/${var.ubuntu_series}/current/SHA256SUMS"
  iso_url        = "https://cloud-images.ubuntu.com/${var.ubuntu_series}/current/${var.ubuntu_series}-server-cloudimg-${var.architecture}.img"
  memory         = 2048
  qemu_binary    = "qemu-system-${lookup(local.qemu_arch, var.architecture, "")}"
  qemu_img_args {
    create = ["-F", "qcow2"]
  }
  qemuargs = [
    ["-machine", "${lookup(local.qemu_machine, var.architecture, "")}"],
    ["-cpu", "${lookup(local.qemu_cpu, var.architecture, "")}"],
    ["-device", "virtio-gpu-pci"],
    ["-drive", "if=pflash,format=raw,id=ovmf_code,readonly=on,file=/usr/share/${lookup(local.uefi_imp, var.architecture, "")}/${lookup(local.uefi_imp, var.architecture, "")}_CODE.fd"],
    ["-drive", "if=pflash,format=raw,id=ovmf_vars,readonly=on,file=/usr/share/${lookup(local.uefi_imp, var.architecture, "")}/${lookup(local.uefi_imp, var.architecture, "")}_VARS.fd"],
    ["-drive", "file=output-qemu/packer-qemu,format=qcow2"],
    ["-drive", "file=seeds-cloudimg.iso,format=raw"]
  ]
  shutdown_command       = "sudo -S shutdown -P now"
  ssh_handshake_attempts = 500
  ssh_password           = var.ssh_password
  ssh_timeout            = "45m"
  ssh_username           = var.ssh_username
  ssh_wait_timeout       = "45m"
  use_backing_file       = true
}

build {
  sources = ["source.qemu.cloudimg"]

  provisioner "shell" {
    environment_vars = concat(local.proxy_env, ["DEBIAN_FRONTEND=noninteractive"])
    scripts          = ["${path.root}/scripts/cloudimg/setup-boot.sh"]
  }


  provisioner "shell" {
    environment_vars  = concat(local.proxy_env, ["DEBIAN_FRONTEND=noninteractive"])
    expect_disconnect = true
    scripts           = [var.customize_script]
  }

  provisioner "shell" {
    environment_vars = [
      "CLOUDIMG_CUSTOM_KERNEL=${var.kernel}",
      "DEBIAN_FRONTEND=noninteractive"
    ]
    scripts = ["${path.root}/scripts/cloudimg/install-custom-kernel.sh"]
  }

  provisioner "file" {
    destination = "/tmp/"
    sources     = ["${path.root}/scripts/cloudimg/curtin-hooks"]
  }

  provisioner "shell" {
    environment_vars = ["CLOUDIMG_CUSTOM_KERNEL=${var.kernel}"]
    scripts          = ["${path.root}/scripts/cloudimg/setup-curtin.sh"]
  }

  provisioner "shell" {
    environment_vars = ["DEBIAN_FRONTEND=noninteractive"]
    scripts          = ["${path.root}/scripts/cloudimg/cleanup.sh"]
  }

  post-processor "shell-local" {
    inline = [
      "IMG_FMT=qcow2",
      "source ../scripts/setup-nbd",
      "OUTPUT=$${OUTPUT:-${var.filename}}",
      "source ./scripts/cloudimg/tar-rootfs"
    ]
    inline_shebang = "/bin/bash -e"
  }
}
```

You can see that the sections match the typical structure of a `packer` HCL2 template: declarations (variables); a source declaration; and build tools. We can deconstruct these briefly to understand what the template is doing. This will help explain the image creation process.

### Variables (declaration section)

The variables section of this template looks like this:

```nohighlight
variable "ubuntu_series" {
  type        = string
  default     = "focal"
  description = "The codename of the Ubuntu series to build."
}

variable "filename" {
  type        = string
  default     = "custom-cloudimg.tar.gz"
  description = "The filename of the tarball to produce"
}

variable "kernel" {
  type        = string
  default     = ""
  description = "The package name of the kernel to install. May include version string, e.g linux-image-generic-hwe-22.04=5.15.0.41.43"
}

variable "customize_script" {
  type        = string
  description = "The filename of the script that will run in the VM to customize the image."
}

variable "architecture" {
  type        = string
  default     = "amd64"
  description = "The architecture to build the image for (amd64 or arm64)"
}

variable "headless" {
  type        = bool
  default     = true
  description = "Whether VNC viewer should not be launched."
}

variable "http_directory" {
  type        = string
  default     = "http"
  description = "Directory for files to be accessed over http in the VM."
}

variable "http_proxy" {
  type        = string
  default     = "${env("http_proxy")}"
  description = "HTTP proxy to use when customizing the image inside the VM. The http_proxy enviroment is set, and apt is configured to use the http proxy"
}

variable "https_proxy" {
  type        = string
  default     = "${env("https_proxy")}"
  description = "HTTPS proxy to use when customizing the image inside the VM. The https_proxy enviroment is set, and apt is configured to use the https proxy"
}

variable "no_proxy" {
  type        = string
  default     = "${env("no_proxy")}"
  description = "NO_PROXY environment to use when customizing the image inside the VM."
}

variable "ssh_password" {
  type        = string
  default     = "ubuntu"
  description = "SSH password to use to connect to the VM to customize the image. Needs to match the hashed password in user-data-cloudimg."
}

variable "ssh_username" {
  type        = string
  default     = "root"
  description = "SSH user to use to connect to the VM to customize the image. Needs to match the user in user-data-cloudimg."
}

locals {
  qemu_arch = {
    "amd64" = "x86_64"
    "arm64" = "aarch64"
  }
  uefi_imp = {
    "amd64" = "OVMF"
    "arm64" = "AAVMF"
  }
  qemu_machine = {
    "amd64" = "ubuntu,accel=kvm"
    "arm64" = "virt"
  }
  qemu_cpu = {
    "amd64" = "host"
    "arm64" = "cortex-a57"
  }

  proxy_env = [
    "http_proxy=${var.http_proxy}",
    "https_proxy=${var.https_proxy}",
    "no_proxy=${var.https_proxy}",
  ]
}
```

Most of this is straightforward. We're going to use a base image of Ubuntu 20.04, keeping the HTTP files in directory `http` and making three possible proxy options available: HTTP, HTTPS, or no proxy. The produced image will have an SSH username and password of "ubuntu". It's that simple.

The really complicated "builders" section of the old JSON version is replaced by a "source" section that is much cleaner. Here's the source section of this HCL2 template, with a few comments added for clarity:

```nohighlight
source "qemu" "cloudimg" {
  boot_wait      = "2s"
 SETS UP THE IMAGE FOR A TWO-CPU VIRTUAL/MACHINE:
  cpus           = 2
  disk_image     = true
 SETS UP THE IMAGE TO EXPECT A 4GB DISK:
  disk_size      = "4G"
  format         = "qcow2"
 WHETHER OR NOT THE IMAGE EXPECTS TO RUN HEADLESS, THAT IS, WITHOUT A CONSOLE:
  headless       = var.headless
 THE HTTP DIRECTORY WILL (HOPEFULLY) BE THE USER'S HTTP DIRECTORY:
  http_directory = var.http_directory
 THE CHECKSUM FOR THE ISO IMAGE WILL BE FOUND HERE:
  iso_checksum   = "file:https://cloud-images.ubuntu.com/${var.ubuntu_series}/current/SHA256SUMS"
 THE ISO IMAGE ITSELF WILL BE FOUND AT THIS URL:
  iso_url        = "https://cloud-images.ubuntu.com/${var.ubuntu_series}/current/${var.ubuntu_series}-server-cloudimg-${var.architecture}.img"
 THE IMAGE SHOULD EXPECT THIS MUCH MEMORY:
  memory         = 2048
  qemu_binary    = "qemu-system-${lookup(local.qemu_arch, var.architecture, "")}"
  qemu_img_args {
    create = ["-F", "qcow2"]
  }
 IF YOU STUDY THE QEMU DOCUMENTATION, IT'S FAIRLY EASY TO SEE WHAT THESE ARGS DO:
  qemuargs = [
    ["-machine", "${lookup(local.qemu_machine, var.architecture, "")}"],
    ["-cpu", "${lookup(local.qemu_cpu, var.architecture, "")}"],
    ["-device", "virtio-gpu-pci"],
    ["-drive", "if=pflash,format=raw,id=ovmf_code,readonly=on,file=/usr/share/${lookup(local.uefi_imp, var.architecture, "")}/${lookup(local.uefi_imp, var.architecture, "")}_CODE.fd"],
    ["-drive", "if=pflash,format=raw,id=ovmf_vars,readonly=on,file=/usr/share/${lookup(local.uefi_imp, var.architecture, "")}/${lookup(local.uefi_imp, var.architecture, "")}_VARS.fd"],
    ["-drive", "file=output-qemu/packer-qemu,format=qcow2"],
    ["-drive", "file=seeds-cloudimg.iso,format=raw"]
  ]
 HERE'S THE SHUTDOWN COMMAND TO USE:
  shutdown_command       = "sudo -S shutdown -P now"
 HERE'S HOW MANY TIMES YOU TRY SSH:
  ssh_handshake_attempts = 500
 HERE'S HOW YOU GATHER THE SSH PASSWORD:
  ssh_password           = var.ssh_password
 USE A REALLY LONG SSH WAIT TIMEOUT:
  ssh_timeout            = "45m"
 HERE'S HOW YOU GATHER THE SSH USERNAME:
  ssh_username           = var.ssh_username
 USE A REALLY LONG SSH TIMEOUT, TOO:
  ssh_wait_timeout       = "45m"
  use_backing_file       = true
}
```

The high number of SSH handshake attempts -- and the really long timeouts -- have to do with trying to catch the system after it has successfully booted. Because of the way packer works, it has no direct way to be informed that the system has booted. As a consequence, to finish the build and run provisioners and post-processors, packer has to keep trying for a while until an SSH connection is successful. In practice, this should only take 2-3 minutes, but this template uses very long values, just to be sure.

### Build section

The build section of this template lays out the tools that will build the packed image:

```nohighlight
build {
  sources = ["source.qemu.cloudimg"]

  provisioner "shell" {
    environment_vars = concat(local.proxy_env, ["DEBIAN_FRONTEND=noninteractive"])
    scripts          = ["${path.root}/scripts/cloudimg/setup-boot.sh"]
  }


  provisioner "shell" {
    environment_vars  = concat(local.proxy_env, ["DEBIAN_FRONTEND=noninteractive"])
    expect_disconnect = true
    scripts           = [var.customize_script]
  }

  provisioner "shell" {
    environment_vars = [
      "CLOUDIMG_CUSTOM_KERNEL=${var.kernel}",
      "DEBIAN_FRONTEND=noninteractive"
    ]
    scripts = ["${path.root}/scripts/cloudimg/install-custom-kernel.sh"]
  }

  provisioner "file" {
    destination = "/tmp/"
    sources     = ["${path.root}/scripts/cloudimg/curtin-hooks"]
  }

  provisioner "shell" {
    environment_vars = ["CLOUDIMG_CUSTOM_KERNEL=${var.kernel}"]
    scripts          = ["${path.root}/scripts/cloudimg/setup-curtin.sh"]
  }

  provisioner "shell" {
    environment_vars = ["DEBIAN_FRONTEND=noninteractive"]
    scripts          = ["${path.root}/scripts/cloudimg/cleanup.sh"]
  }

  post-processor "shell-local" {
    inline = [
      "IMG_FMT=qcow2",
      "source ../scripts/setup-nbd",
      "OUTPUT=$${OUTPUT:-${var.filename}}",
      "source ./scripts/cloudimg/tar-rootfs"
    ]
    inline_shebang = "/bin/bash -e"
  }
}
```

Rather than walking through each of these lines individually, we can just note that this HCL2 causes packer to:

 - retrieve scripts that set up the bootloader, configure curtin hooks, and install custom packages from a named gzip source.
 - set the homedir and proxy options for the image.
 - set up curtin, networking, and maybe storage for the image.
 - clean up the image prior to post-processing.

The post-processing section of this template prepares the image for use:

```nohighlight
  post-processor "shell-local" {
    inline = [
      "IMG_FMT=qcow2",
      "source ../scripts/setup-nbd",
      "OUTPUT=$${OUTPUT:-${var.filename}}",
      "source ./scripts/cloudimg/tar-rootfs"
    ]
    inline_shebang = "/bin/bash -e"
  }
```

You can see right away that this template has one post-processor (only one `post-processor` entry). This post-processor is a local shell, invoked with the `-e` option, which causes the shell to terminate if there's an error (rather than continuing with the next command). In this case, we can see that the shell runs four commands:

 - sets `$IMG_FMT` to "qcow2"
 - runs the script `setup-nbd`
 - sets $OUTPUT to "<name of image>-custom-cloudimg.tar.gz"
 - runs the script `tar-rootfs`

In this case, it's worth a quick look at the two scripts to see what this post-processor does. First, let's glance at `setup-nbd`:

```nohighlight
!/bin/bash -e

 setup-nbd - Bind Packer qemu output to a free /dev/nbd device.

 Author: Lee Trager <lee.trager@canonical.com>

 Copyright (C) 2020 Canonical

 This program is free software: you can redistribute it and/or modify
 it under the terms of the GNU Affero General Public License as
 published by the Free Software Foundation, either version 3 of the
 License, or (at your option) any later version.

 This program is distributed in the hope that it will be useful,
 but WITHOUT ANY WARRANTY; without even the implied warranty of
 MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
 GNU Affero General Public License for more details.

 You should have received a copy of the GNU Affero General Public License
 along with this program. If not, see <http://www.gnu.org/licenses/>.

if [ $UID -ne 0 ]; then
    echo "ERROR: Must be run as root!" >&2
    exit 1
fi

if [ ! -f output-qemu/packer-qemu ]; then
    echo "ERROR: Not in the same path as template!" >&2
    exit
fi

echo 'Loading nbd...'
shopt -s extglob
modprobe nbd
for nbd in /sys/class/block/nbd+([0-9]); do
    if [ "$(cat ${nbd}/size)" -eq 0 ]; then
	nbd="/dev/$(basename $nbd)"
	echo "Using $nbd"
	break
    fi
done

if [ -z "${nbd}" ] || ! echo $nbd | grep -q "/dev"; then
    echo "ERROR: Unable to find nbd device to mount image!" >&2
    exit 1
fi

echo "Binding image to $nbd..."
qemu-nbd -d $nbd
if [ -n "$IMG_FMT" ]; then
    qemu-nbd -c $nbd -f "$IMG_FMT" -n output-qemu/packer-qemu
else
    qemu-nbd -c $nbd -n output-qemu/packer-qemu
fi
echo 'Waiting for partitions to be created...'
tries=0
while [ ! -e "${nbd}p1" -a $tries -lt 60 ]; do
    sleep 1
    tries=$((tries+1))
done
```

As you can see, this is just a well-structured script to export a QEMU image as a Network Block Device, binding it to a `/dev/nbd` directory. This is first step in creating MAAS-loadable Ubuntu image. The second step comes in `tar-rootfs`:

```nohighlight
!/bin/bash -e

 tar-rootfs - Create a tar.gz from a binded /dev/nbd device

 Author: Alexsander de Souza <alexsander.souza@canonical.com>

 Copyright (C) 2021 Canonical

 This program is free software: you can redistribute it and/or modify
 it under the terms of the GNU Affero General Public License as
 published by the Free Software Foundation, either version 3 of the
 License, or (at your option) any later version.

 This program is distributed in the hope that it will be useful,
 but WITHOUT ANY WARRANTY; without even the implied warranty of
 MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
 GNU Affero General Public License for more details.

 You should have received a copy of the GNU Affero General Public License
 along with this program. If not, see <http://www.gnu.org/licenses/>.

cleanup() {
    qemu-nbd -d "$nbd"
    [ -d "${TMP_DIR}" ] && rm -rf "${TMP_DIR}"
}
trap cleanup EXIT

if [ ${UID} -ne 0 ]; then
    echo "ERROR: Must be run as root!" >&2
    exit 1
fi

TMP_DIR=$(mktemp -d /tmp/packer-maas-XXXX)

echo 'Mounting root partition...'
mount "${nbd}p2" "${TMP_DIR}"
mount "${nbd}p1" "${TMP_DIR}/boot/efi"

echo "Creating MAAS image $OUTPUT..."
tar -Sczpf "$OUTPUT" --acls --selinux --xattrs -C "${TMP_DIR}" .

echo 'Unmounting image...'
umount "${TMP_DIR}/boot/efi"
umount "${TMP_DIR}"
```

This script just creates a `.tar.gz` from a bound `/dev/nbd` device (where the QEMU image was initially stored by the last script.

As you can see, the process of creating a customised packer image is not overly complex. Nevertheless, it's a difficult process to get right, hence our community-contributed templates.

## The image installation process

Installing a packer-created image is highly dependent on the application. In the case of MAAS, we use the CLI `boot-resources` command to upload the image to MAAS, something like this:

```nohighlight
$ maas admin boot-resources create \
    name='custom/ubuntu-tgz' \
    title='Ubuntu Custom TGZ' \
    architecture='amd64/generic' \
    filetype='tgz' \
    content@=custom-ubuntu.tar.gz
```

At this point, the image shows up in MAAS, synced to the controller, the same as any other image.

## Packer-created images

If you're more interested in the anatomy of a packer-created image, for example, an ISO image, you can use `isoinfo` to explore the image file. The image should be found in the packer git repository, under `<imagename>/packer-cache`. Ideally, it shouldn't differ too much from any other customised ISO image. You can explore with a few of the `isoinfo` commands. For example, you can read the primary volume descriptor like this:

```nohighlight
stormrider@neuromancer:~/mnt/Dropbox/src/git/packer-maas/ubuntu/packer_cache$ isoinfo -d -i ubuntu.iso | more                                                         
CD-ROM is in ISO 9660 format
System id: 
Volume id: Ubuntu-Server 20.04.4 LTS amd64
Volume set id: 
Publisher id: 
Data preparer id: XORRISO-1.2.4 2012.07.20.130001, LIBISOBURN-1.2.4, LIBISOFS-1.2.4, LIBBURN-1.2.4
Application id: 
Copyright File id: 
Abstract File id: 
Bibliographic File id: 
Volume set size is: 1
Volume set sequence number is: 1
Logical block size is: 2048
Volume size is: 650240
El Torito VD version 1 found, boot catalog is in sector 250
Joliet with UCS level 3 found
Rock Ridge signatures version 1 found
Eltorito validation header:
    Hid 1
    Arch 0 (x86)
    ID ''
    Key 55 AA
    Eltorito defaultboot header:
        Bootid 88 (bootable)
        Boot media 0 (No Emulation Boot)
        Load segment 0
        Sys type 0
        Nsect 4
        Bootoff 8EC04 584708
```

You could also generate an exhaustive directory listing with `isoinfo -f -i <isoname>`, and possibly pipe that through `grep` to ensure that your desired packages have been added to the image. Or, if you prefer to sweep the image directories manually, you can use `isoinfo -l -i <isoname>`. The larger point, of course, is that a packer-generated image is essentially identical to any prepared ISO image, including, of course, any customisations (e.g., extra software) that the template loads before finalising the image.