This guide covers building custom images for the following operating systems using **Packer** for deployment in MAAS:

- **RHEL 7**
- **RHEL 8**
- **CentOS 7**
- **Oracle Linux 8**
- **Oracle Linux 9**
- **VMware ESXi**

## 1. Verify Requirements

You need a machine running **Ubuntu 18.04+** or **22.04+** with the ability to run KVM virtual machines. Ensure the following components are available:

| **OS**              | **Additional Requirements**                                                                 |
|---------------------|---------------------------------------------------------------------------------------------|
| **RHEL 7**          | MAAS 2.3+, Curtin 18.1-59+, RHEL 7 DVD ISO                                                 |
| **RHEL 8**          | MAAS 2.3+, Curtin 18.1-59+, RHEL 8 DVD ISO                                                 |
| **CentOS 7**        | MAAS 2.3+, Curtin 18.1-59+                                                                 |
| **Oracle Linux 8**  | MAAS 3.5+, Curtin 23.1+, libnbd-bin, nbdkit, fuse2fs, Oracle Linux 8 DVD ISO               |
| **Oracle Linux 9**  | MAAS 3.5+, Curtin 23.1+, libnbd-bin, nbdkit, fuse2fs, Oracle Linux 9 DVD ISO               |
| **VMware ESXi**     | MAAS 2.5+, qemu-kvm, qemu-utils, VMware ESXi ISO                                           |

## 2. Install Packer

### For Ubuntu 18.04+

```bash
sudo apt install packer
```

### For Ubuntu 22.04+ (Required for Oracle Linux 8/9)

```bash
curl -fsSL https://apt.releases.hashicorp.com/gpg | sudo apt-key add -
sudo apt-add-repository "deb [arch=amd64] https://apt.releases.hashicorp.com $(lsb_release -cs) main"
sudo apt-get update && sudo apt-get install packer
```

## 3. Install Dependencies

Install dependencies required for image building:

```bash
sudo apt install qemu-utils
```

For **Oracle Linux 8/9** and **VMware ESXi**, install additional dependencies:

```bash
sudo apt install libnbd-bin nbdkit fuse2fs qemu-utils
```

For **VMware ESXi**, install Python pip:

```bash
sudo apt install pip
```

## 4. Get Packer Templates

Clone the **Packer templates** repository:

```bash
git clone https://github.com/canonical/packer-maas.git
```

## 5. Download ISO Files

Download the appropriate ISO for your desired OS version and place it in the corresponding subdirectory:

| **OS**              | **ISO Location**                    | **Subdirectory**  |
|---------------------|--------------------------------------|-------------------|
| **RHEL 7**          | RHEL 7 DVD ISO                      | `rhel7`           |
| **RHEL 8**          | RHEL 8 DVD ISO                      | `rhel8`           |
| **CentOS 7**        | Downloaded via template             | `centos7`         |
| **Oracle Linux 8**  | Oracle Linux 8 DVD ISO              | `ol8`             |
| **Oracle Linux 9**  | Oracle Linux 9 DVD ISO              | `ol9`             |
| **VMware ESXi**     | VMware ESXi ISO                     | `vmware-esxi`     |

## 6. Customize the Image

Modify the **Kickstart file** to customize the deployment image:

| **OS**              | **Kickstart File**            |
|---------------------|-------------------------------|
| **RHEL 7**          | `http/rhel7.ks`               |
| **RHEL 8**          | `http/rhel8.ks`               |
| **CentOS 7**        | `http/centos7.ks`             |
| **Oracle Linux 8**  | `http/ol8.ks`                 |
| **Oracle Linux 9**  | `http/ol9.ks`                 |
| **VMware ESXi**     | `packer-maas/vmware-esxi/KS.CFG` |

Refer to the respective **Kickstart documentation** for detailed customization options.

## 7. Optional Proxy Configuration

To use a proxy during the build process:

1. **Set the HTTP Proxy**:

   ```bash
   export HTTP_PROXY=http://your-proxy-server:port
   ```

2. **Modify Kickstart Files**:

   Add `--proxy=$HTTP_PROXY` to lines starting with `url` or `repo`.

For **Oracle Linux 8/9**, set the `KS_PROXY` variable:

```bash
export KS_PROXY=$HTTP_PROXY
```

## 8. Build the Image

### Using the Makefile

Run the following command in the appropriate subdirectory (`rhel7`, `rhel8`, `centos7`, `ol8`, `ol9`, `vmware-esxi`):

```bash
make ISO=/PATH/TO/your-iso-file.iso
```

### Manually Using Packer

Alternatively, manually run **Packer**:

For **RHEL 7/8**:

```bash
sudo PACKER_LOG=1 packer build -var 'iso_path=/PATH/TO/your-iso-file.iso' rhel7.json  # or rhel8.json
```

For **CentOS 7**:

```bash
sudo PACKER_LOG=1 packer build centos7.json
```

For **Oracle Linux 8/9**:

```bash
packer init .
PACKER_LOG=1 packer build .
```

For **VMware ESXi**:

```bash
sudo PACKER_LOG=1 packer build -var 'vmware_esxi_iso_path=/PATH/TO/your-esxi-iso-file.iso' vmware-esxi.json
```

**Note:** Packer runs in headless mode by default. To view the installation output, connect via **VNC** or set `headless` to `false`.

## 9. Upload the Image to MAAS

### Commands for Each OS

| **OS**              | **Upload Command**                                                                                       |
|---------------------|---------------------------------------------------------------------------------------------------------|
| **RHEL 7**          | `maas $PROFILE boot-resources create name='rhel/7-custom' title='RHEL 7 Custom' ...`                   |
| **RHEL 8**          | `maas $PROFILE boot-resources create name='rhel/8-custom' title='RHEL 8 Custom' ...`                   |
| **CentOS 7**        | `maas $PROFILE boot-resources create name='centos/7-custom' title='CentOS 7 Custom' ...`               |
| **Oracle Linux 8**  | `maas $PROFILE boot-resources create name='ol/8.8' title='Oracle Linux 8.8' ...`                       |
| **Oracle Linux 9**  | `maas $PROFILE boot-resources create name='ol/9.2' title='Oracle Linux 9.2' ...`                       |
| **VMware ESXi**     | `maas $PROFILE boot-resources create name='esxi/6.7' title='VMware ESXi 6.7' ...`                      |


## 10. Verify and Log In

Deploy the image and log in to verify customizations:

| **OS**              | **Default Username** |
|---------------------|----------------------|
| **RHEL 7/8**        | `cloud-user`         |
| **CentOS 7**        | `centos`             |
| **Oracle Linux 8/9**| `cloud-user`         |
| **VMware ESXi**     | `root`               |
