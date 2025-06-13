Using Packer, you can build custom, MAAS-deployable images for the following operating systems:

- RHEL 7
- RHEL 8
- CentOS 7
- Oracle Linux 8
- Oracle Linux 9
- VMware ESXi

You can also build deployment [Windows](https://maas.io/docs/how-to-build-maas-images#p-17423-build-windows-images) images.

## Build Linux images

### Verify requirements

You need a machine running Ubuntu 18.04+ or 22.04+ with the ability to run KVM virtual machines. Ensure the following components are available:

| **OS**              | **Additional Requirements**                                                                 |
|---------------------|---------------------------------------------------------------------------------------------|
| RHEL 7          | MAAS 2.3+, Curtin 18.1-59+, RHEL 7 DVD ISO                                                 |
| RHEL 8          | MAAS 2.3+, Curtin 18.1-59+, RHEL 8 DVD ISO                                                 |
| CentOS 7        | MAAS 2.3+, Curtin 18.1-59+                                                                 |
| Oracle Linux 8  | MAAS 3.5+, Curtin 23.1+, libnbd-bin, nbdkit, fuse2fs, Oracle Linux 8 DVD ISO               |
| Oracle Linux 9  | MAAS 3.5+, Curtin 23.1+, libnbd-bin, nbdkit, fuse2fs, Oracle Linux 9 DVD ISO               |
| VMware ESXi     | MAAS 2.5+, qemu-kvm, qemu-utils, VMware ESXi ISO                                           |

### Gather components

Collect Packer, its dependencies and templates, and a suitable ISO file before starting.

#### Install Packer

Packer is the tool of choice for building custom MAAS images.

##### For Ubuntu 18.04+

```bash
sudo apt install packer
```

##### For Ubuntu 22.04+ (Required for Oracle Linux 8/9)

```bash
curl -fsSL https://apt.releases.hashicorp.com/gpg | sudo apt-key add -
sudo apt-add-repository "deb [arch=amd64] https://apt.releases.hashicorp.com $(lsb_release -cs) main"
sudo apt-get update && sudo apt-get install packer
```

#### Install dependencies

Install dependencies required for image building:

```bash
sudo apt install qemu-utils
```

For Oracle Linux 8/9 and VMware ESXi, install additional dependencies:

```bash
sudo apt install libnbd-bin nbdkit fuse2fs qemu-utils
```

For VMware ESXi, install Python pip:

```bash
sudo apt install pip
```

#### Get Packer templates

Clone the Packer templates repository:

```bash
git clone https://GitHub.com/canonical/packer-maas.git
```

#### Download ISO files

Download the appropriate ISO for your desired OS version and place it in the corresponding subdirectory:

| **OS**              | **ISO Location**                    | **Subdirectory**  |
|---------------------|--------------------------------------|-------------------|
| RHEL 7          | RHEL 7 DVD ISO                      | `rhel7`           |
| RHEL 8          | RHEL 8 DVD ISO                      | `rhel8`           |
| CentOS 7        | Downloaded via template             | `centos7`         |
| Oracle Linux 8  | Oracle Linux 8 DVD ISO              | `ol8`             |
| Oracle Linux 9  | Oracle Linux 9 DVD ISO              | `ol9`             |
| VMware ESXi     | VMware ESXi ISO                     | `vmware-esxi`     |

### Customize the image

Modify the Kickstart file to customize the deployment image:

| **OS**              | **Kickstart File**            |
|---------------------|-------------------------------|
| RHEL 7          | `http/rhel7.ks`               |
| RHEL 8          | `http/rhel8.ks`               |
| CentOS 7        | `http/centos7.ks`             |
| Oracle Linux 8  | `http/ol8.ks`                 |
| Oracle Linux 9  | `http/ol9.ks`                 |
| VMware ESXi     | `packer-maas/vmware-esxi/KS.CFG` |

Refer to the respective Kickstart documentation for detailed customization options.

### Configure a build proxy (optional)

To use a proxy during the build process:

1. Set the HTTP proxy:

   ```bash
   export HTTP_PROXY=http://your-proxy-server:port
   ```

2. Modify Kickstart Files:

   Add `--proxy=$HTTP_PROXY` to lines starting with `url` or `repo`.

For Oracle Linux 8/9, set the `KS_PROXY` variable:

```bash
export KS_PROXY=$HTTP_PROXY
```

### Build the image

#### Using the makefile

Run the following command in the appropriate subdirectory (`rhel7`, `rhel8`, `centos7`, `ol8`, `ol9`, `vmware-esxi`):

```bash
make ISO=/PATH/TO/your-iso-file.iso
```

#### Manually, Using Packer

Alternatively, manually run Packer:

For RHEL 7/8:

```bash
sudo PACKER_LOG=1 packer build -var 'iso_path=/PATH/TO/your-iso-file.iso' rhel7.json  # or rhel8.json
```

For CentOS 7:

```bash
sudo PACKER_LOG=1 packer build centos7.json
```

For Oracle Linux 8/9:

```bash
packer init .
PACKER_LOG=1 packer build .
```

For VMware ESXi:

```bash
sudo PACKER_LOG=1 packer build -var 'vmware_esxi_iso_path=/PATH/TO/your-esxi-iso-file.iso' vmware-esxi.json
```

Note: Packer runs in headless mode by default. To view the installation output, connect via VNC or set `headless` to `false`.

### Upload the image to MAAS

#### Commands for each OS

| **OS**              | **Upload Command**                                                                                       |
|---------------------|---------------------------------------------------------------------------------------------------------|
| RHEL 7          | `maas $PROFILE boot-resources create name='rhel/7-custom' title='RHEL 7 Custom' ...`                   |
| RHEL 8          | `maas $PROFILE boot-resources create name='rhel/8-custom' title='RHEL 8 Custom' ...`                   |
| CentOS 7        | `maas $PROFILE boot-resources create name='centos/7-custom' title='CentOS 7 Custom' ...`               |
| Oracle Linux 8  | `maas $PROFILE boot-resources create name='ol/8.8' title='Oracle Linux 8.8' ...`                       |
| Oracle Linux 9  | `maas $PROFILE boot-resources create name='ol/9.2' title='Oracle Linux 9.2' ...`                       |
| VMware ESXi     | `maas $PROFILE boot-resources create name='esxi/6.7' title='VMware ESXi 6.7' ...`                      |


### Verify and log in

Deploy the image and log in to verify customizations:

| **OS**              | **Default Username** |
|---------------------|----------------------|
| RHEL 7/8        | `cloud-user`         |
| CentOS 7        | `centos`             |
| Oracle Linux 8/9| `cloud-user`         |
| VMware ESXi     | `root`               |


## Build Windows images

Since Windows is a proprietary operating system, MAAS can't download these images. You need to manually generate images to use with MAAS by using Windows ISO images. On the upside, the end result will be much simpler, since there are CLI and WebUI tools to upload a Windows image -- which _helps_ automate the process.


### Verify prerequisites

To build the image:

* A machine running Ubuntu 18.04+ with the ability to run KVM virtual machines.
* qemu-utils, libnbd-bin, nbdkit and fuse2fs
* qemu-system
* ovmf
* cloud-image-utils
* [Packer](https://developer.hashicorp.com/packer/tutorials/docker-get-started/get-started-install-cli), v1.7.0 or newer
* A copy of the [packer-maas](https://GitHub.com/canonical/packer-maas) git repository:
```
git clone https://GitHub.com/canonical/packer-maas.git
```
Note that Ubuntu 22.04+ is required to build Windows 11 images due to ```swtpm``` (Software TPM) package requirements.

#### Supported Microsoft Windows versions

This process has been build and deployment tested with the following versions of Microsoft Windows:

* Windows Server 2025
* Windows Server 2022
* Windows Server 2019
* Windows Server 2016
* Windows 10 PRO+
* Windows 11 PRO+

To deploy the image:

* [MAAS](https://maas.io) 3.2+
* [Curtin](https://launchpad.net/curtin) 21.0+

### Gather components

Collect an ISO image and a template before trying to build a Windows image.

#### Get the windows.pkr.hcl Template

This template builds a dd.tgz MAAS image from an official Microsoft Windows ISO/VHDX.
This process also installs the latest VirtIO drivers as well as Cloudbase-init.

#### Obtain Microsoft Windows ISO images

You can obtains Microsoft Windows Evaluation ISO/VHDX images from the following links:

* [Windows Server 2025](https://www.microsoft.com/en-us/evalcenter/download-windows-server-2025)
* [Windows Server 2022](https://www.microsoft.com/en-us/evalcenter/download-windows-server-2022)
* [Windows Server 2019](https://www.microsoft.com/en-us/evalcenter/download-windows-server-2019)
* [Windows Server 2016](https://www.microsoft.com/en-us/evalcenter/download-windows-server-2016)
* [Windows 10 Enterprise](https://www.microsoft.com/en-us/evalcenter/download-windows-10-enterprise)
* [Windows 11 Enterprise](https://www.microsoft.com/en-us/evalcenter/download-windows-11-enterprise)

### Build the image

The build the image you give the template a script which has all the customization:

```shell
sudo make windows ISO=<path-to-iso> VERSION=<windows-version>
```

Example:

```shell
sudo make ISO=/mnt/iso/Windows_Server_2025_SERVER_EVAL_x64FRE_en-us.iso VERSION=2025
```

#### Adjust makefile parameters

##### EDIT

The edition of a targeted ISO image. It defaults to PRO for Microsoft Windows 10/11 and SERVERSTANDARD for Microsoft Windows Servers. Many Microsoft Windows Server ISO images do contain multiple editions and this parameter is useful to build a particular edition such as Standard or Datacenter etc.

##### HEADLESS

Whether VNC viewer should not be launched. Default is set to false. This is useful when building images on machines that do not have graphical libraries such as SDL/GTK installed. Headless mode does include an open VNC port to monitor the build process if needed.

##### ISO

Path to Microsoft Windows ISO image used to build the MAAS image.

##### PACKER_LOG

Enable (1) or Disable (0) verbose Packer logs. The default value is set to 0.

##### PKEY

User supplied Microsoft Windows Product Key. When using KMS, you can obtain the activation keys from the link below:

* [KMS Client Activation and Product Keys](https://learn.microsoft.com/en-us/windows-server/get-started/kms-client-activation-keys)

Please note that PKEY is an optional parameter but it might be required during the build time depending on the type of ISO being used. Evaluation series ISO images usually do not require a product key to proceed, however this is not true with Enterprise and Retail ISO images.

##### TIMEOUT

Defaults to 1h. Supports variables in h (hour) and m (Minutes).

##### VHDX

Path to Microsoft Windows VHDX image used to build the image.

##### VERSION

Specify the Microsoft Windows Version. Example inputs include: 2025, 2022, 2019, 2016, 10 and 11. Currently defaults to 2022.

### Upload Windows images to MAAS

Use MAAS CLI to upload the image:

```shell
maas admin boot-resources create \
    name='windows/windows-server' \
    title='Windows Server' \
    architecture='amd64/generic' \
    filetype='ddtgz' \
    content@=windows-server-amd64-root-dd.gz
```

