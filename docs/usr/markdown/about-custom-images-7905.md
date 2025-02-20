## Overview  

MAAS allows you to upload and deploy custom images beyond the [MAAS image repository](http://images.maas.io). However, generic ISO images require modifications before they can be used. A valid MAAS image must include:  

- A **curtin hook script** to write and boot the image.  
- **Cloud-init metadata** for networking, storage, users, and software.  

## Preparing Custom Images  

You can create MAAS-compatible images in two ways:  

1. **Hand-build images** (requires deep understanding of curtin/cloud-init).  
2. **Use [Packer](https://www.packer.io)** to automate the process.  

For supported operating systems, Canonical provides [Packer templates](https://github.com/canonical/packer-maas). Custom images are not officially supported due to licensing and compatibility risks. **Canonical strongly recommends using cloud-init or curtin for customization instead of building custom images.**  

## Static Ubuntu Images  

Static images are pre-configured Ubuntu OS images deployable via MAAS. They include users, packages, and configurations but remain fixed post-deployment. This method is mainly for MAAS versions `<3.1`, but works on all versions.  

For MAAS `3.0+`, **Packer is recommended** due to its built-in Ubuntu image customization capabilities.  

### Uploading Hand-Built Images  

A hand-built image must include:  

- A **kernel**  
- A **bootloader**  
- A **curtin network hook** (`/curtin/curtin-hooks`)  

It must be in **raw `.img` format** (required by MAAS). Once built, upload it via:  

```bash
maas $PROFILE boot-resources create \
    name='custom/ubuntu' \
    title='Ubuntu Custom' \
    architecture='amd64/generic' \
    filetype='tgz' \
    content@=custom-ubuntu.img
```

## How MAAS Handles Custom Images  

- MAAS stores uploaded images in the database as `.tar.gz` files.  
- It distinguishes between Ubuntu and non-Ubuntu images, applying the correct pre-seed configs.  
- **Custom images always boot with an ephemeral Ubuntu OS before deployment.**  
- The `base_image` field ensures compatibility between the ephemeral OS and the custom image.  

## Deployment & Boot Process  

1. **MAAS loads the image’s kernel, bootloader, and root filesystem.**  
2. **An ephemeral OS (matching the custom image version) boots first.**  
3. **Curtin writes the full custom image to disk.**  
4. **After writing, MAAS does not modify the custom image.**  

For non-Ubuntu images, an Ubuntu ephemeral OS still boots first before switching to the custom OS.  

## Network & Storage Configuration  

- **Networking:** MAAS-configured network settings apply automatically.  
- **Storage:** Root partitions can be resized, and additional block devices can be attached/formatted.  
- **Verification:** MAAS aborts installation if `cloud-init` or `netplan` is missing.  

## Static Image Metrics  

The MAAS dashboard tracks the number of deployed static images.  

---

# Packer  

[Packer](https://www.packer.io/docs) automates OS image creation for MAAS deployment. It uses **HCL2 templates** to define build, provisioning, and post-processing steps.  

### Packer Workflow  

1. **Define a template** (HCL2 format).  
2. **Select a builder** (e.g., QEMU, Anaconda).  
3. **Run provisioners** (install software, configure settings).  
4. **Apply post-processors** (e.g., compressing into `.tar.gz`).  

Packer outputs **artifacts** (loadable images). In MAAS, these are simply called **images**.  

## Packer Image Creation Process  

- **Builders** create base OS images.  
- **Provisioners** customize images (`curtin` hooks, `cloud-init`, packages).  
- **Post-processors** finalize the image for deployment (e.g., compression).  

### Dependencies for Ubuntu Images  

To build an Ubuntu image with `packer-maas`, install:  

```bash
sudo apt install qemu-utils qemu-system ovmf cloud-image-utils
```

## Packer Templates  

A [Packer template](https://www.packer.io/docs/templates) (written in HCL2) defines the entire image-building process. It includes:  

- **Variables** (image type, architecture, file paths).  
- **Source declaration** (how the image is built).  
- **Provisioners** (installation/configuration scripts).  
- **Post-processors** (final adjustments before deployment).  

### Example: Ubuntu Packer Template  

```hcl
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
  description = "Ubuntu version to build."
}

source "qemu" "cloudimg" {
  iso_url        = "https://cloud-images.ubuntu.com/${var.ubuntu_series}/current/${var.ubuntu_series}-server-cloudimg-amd64.img"
  disk_size      = "4G"
  memory         = 2048
  cpus           = 2
  headless       = true
}

build {
  sources = ["source.qemu.cloudimg"]

  provisioner "shell" {
    scripts = ["./scripts/setup.sh"]
  }

  post-processor "shell-local" {
    inline = [
      "tar -czf ubuntu-custom.tar.gz /path/to/image"
    ]
  }
}
```

## Uploading Packer Images to MAAS  

Once built, upload a Packer-generated image via:  

```bash
maas admin boot-resources create \
    name='custom/ubuntu-packer' \
    title='Ubuntu Packer' \
    architecture='amd64/generic' \
    filetype='tgz' \
    content@=ubuntu-custom.tar.gz
```

## Inspecting Packer-Generated Images  

To examine a Packer-created ISO:  

```bash
isoinfo -d -i ubuntu.iso
```

For a directory listing:  

```bash
isoinfo -f -i ubuntu.iso | grep <package>
```

For a structured view:  

```bash
isoinfo -l -i ubuntu.iso
```

## Summary  

| Feature              | Static Ubuntu Image | Packer Image |
|----------------------|--------------------|--------------|
| **Customization**   | Fixed, manual       | Automated, templated |
| **Deployment**      | Upload & use        | Build, upload & use |
| **Flexibility**     | Limited             | Highly flexible |
| **Recommended for** | Legacy MAAS (<3.1)  | Modern MAAS (3.0+) |

For flexibility, **Packer is the recommended approach**. For minimal customizations, **use cloud-init or curtin instead of custom images**.  

