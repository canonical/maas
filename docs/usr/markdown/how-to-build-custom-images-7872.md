MAAS supports custom images built with [Packer](https://developer.hashicorp.com/packer). These images allow you to deploy operating systems beyond the default Ubuntu set, and to customize Ubuntu images for your own environment.

You can build images for a wide variety of operating systems, including Linux distributions, VMware ESXi, and Windows. The [Packer MAAS repository](https://github.com/canonical/packer-maas) contains templates, build instructions, and upload commands.

## Supported operating systems

The following operating systems already have working or in-progress templates in the [Packer MAAS repository](https://github.com/canonical/packer-maas#existing-templates):

| Family        | Versions                       | Notes                       |
|---------------|--------------------------------|-----------------------------|
| Ubuntu        | All current releases           | Stable templates available  |
| RHEL          | 7, 8, 9, 10                    | Varying stability           |
| Rocky         | 8, 9                           |                             |
| SLES          | 12, 15, 16                     |                             |
| Oracle Linux  | 8, 9                           | Alpha-stage support         |
| CentOS        | 6, 7, 8, Stream 8/9            | Many versions now EOL       |
| Debian        | 10, 11, 12, 13                 |                             |
| Fedora Server | 41, 42                         |                             |
| VMware ESXi   | 6, 7, 8, 9                     |                             |
| Windows       | 2016, 2019, 2022, 2025, 10, 11 | Evaluation ISOs recommended |

All templates are community supported.

> ⚠️ Note: Templates marked as *EOL* are for operating systems that no longer receive upstream support. They are not recommended for new deployments.


## Key considerations

* ISO images: Most non-Ubuntu templates require you to supply an ISO manually. Licensing restrictions prevent Packer from downloading these automatically.
* Windows builds:

  * Ubuntu 22.04+ is required to build Windows 11 images (for `swtpm`).
  * Evaluation ISOs usually work without a product key; Enterprise/Retail images may require a valid key at build time.
  * Windows templates include Cloudbase-init and VirtIO drivers to ensure compatibility with MAAS.
* Networking: You may need to configure a build proxy if your environment requires one.
* Upload: Each template’s README includes the correct `maas boot-resources create` command. Small differences in parameters (e.g., `filetype`) mean you should always copy from the template’s example.

## Next steps

For full build instructions:

* Clone the [Packer MAAS repository](https://github.com/canonical/packer-maas).
* Navigate to the template for your target operating system.
* Follow the README in that template directory to:

  * Check build prerequisites
  * Customize installer configuration (e.g., Kickstart, autoinstall, YAML)
  * Build the image
  * Upload it to MAAS

