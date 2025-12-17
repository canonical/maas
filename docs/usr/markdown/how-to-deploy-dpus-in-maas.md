A Data Processing Unit (DPU) is a specialized network interface card that offloads networking, storage, and security tasks from the CPU. MAAS 3.7 introduced BMC-based control for NVIDIA BlueField 3 DPUs, enabling them to be managed like standard machines in the MAAS infrastructure.

This guide explains how to configure, add, commission, deploy, and release NVIDIA BlueField 3 DPUs in MAAS 3.7 and later.

**Note**: BlueField 2 DPUs can still be added and controlled using the manual approach described in previous [documentation](https://discourse.maas.io/t/maas-and-dpus/6390). This guide focuses on the BMC-enabled workflow for BlueField 3 devices.

## Prerequisites

Before deploying a DPU in MAAS, ensure you have the following:

### Infrastructure Requirements

- **MAAS 3.7 or later** installed and configured  
- **NVIDIA BlueField 3 DPU** with BMC support  
- **Host machine** powered on (the DPU resides within this host)  
- **Network infrastructure** configured for PXE boot on the OOB management interface  
- **Noble (24.04) ARM64 images** synced in MAAS (used for commissioning)

### Host Machine Setup

The host machine must have:

- **Power management accessible** (host must remain powered on during DPU operations)

### DPU Configuration

- **DPU MAC address** noted down for registration  
- **BMC IP address and credentials** (administrator account required)  
- **DPU operating mode** set to 'DpuMode' (not NIC or Restricted mode)  
- **PXE boot configured** for initial commissioning via OOB interface

### Additional Requirements

- SSH keys configured in MAAS for remote access  
- Understanding of DPU-host relationship constraints (see "Important Considerations" section)

## Preparing the DPU

### Finding the BMC IP Address

Connect to the DPU via SSH and use the following command to find the BMC IP address:

```shell
sudo ipmitool lan print
```

For IPv6:

```shell
sudo ipmitool lan6 print
```

### Configuring BMC Credentials

MAAS requires administrator-level BMC credentials to control the DPU's power state. Add a user account to the BMC with administrator privileges using `ipmitool`. See the [ipmitool documentation](https://linux.die.net/man/1/ipmitool) for detailed steps.

For the commands in this guide, the following environment variables are used:

- `$BMC_USER`: Username of the BMC administrator account  
- `$BMC_PASS`: Password for the BMC account  
- `$BMC_IP`: IP address of the DPU's BMC

### Setting the DPU Operating Mode

BlueField 3 DPUs have three operating modes: DPU, Restricted, and NIC. For full MAAS control, the DPU must be in **DPU mode**.

**Check the current mode:**

```shell
curl -k -u $BMC_USER:$BMC_PASS -H 'Content-Type: application/json' \
  -X GET https://$BMC_IP/redfish/v1/Systems/Bluefield/Bios/ | jq '.Attributes'
```

**Change to DPU mode if needed:**

1. Issue this Redfish call to set DPU mode:

```shell
curl -k -u $BMC_USER:$BMC_PASS -H 'content-type: application/json' \
  -d '{ "Attributes": { "NicMode": "DpuMode" } }' \
  -X PATCH https://$BMC_IP/redfish/v1/Systems/Bluefield/Bios/Settings
```

2. Hard reset the DPU. This requires resetting the **host** machine.

More information about BlueField modes: [NVIDIA BlueField Modes of Operation](https://docs.nvidia.com/doca/sdk/bluefield+modes+of+operation/index.html)

### Setting PXE Boot for Initial Commissioning

For initial commissioning and deployment, configure the DPU to PXE boot:

```shell
curl -k -u $BMC_USER:$BMC_PASS -H 'Content-Type: application/json' \
  -X PATCH https://$BMC_IP/redfish/v1/Systems/Bluefield \
  -d '{"Boot": {"BootSourceOverrideEnabled": "Once", "BootSourceOverrideTarget": "Pxe"}}'
```

**Important**: Configure PXE boot to use the **OOB (out-of-band) management interface**, not the high-speed P0/P1 interfaces, to avoid firmware compatibility issues during deployment.

Subsequent commissioning and deployments will automatically configure PXE boot.

### Configuring Boot Order (Optional)

To set a persistent PXE boot order, update the boot device configuration from the BMC console. See [NVIDIA's boot order configuration guide](https://docs.nvidia.com/networking/display/bluefieldbmcv2309/boot+order+configuration).

If the boot device name for the desired NIC is unknown, enter the UEFI menu from the BMC console by running:

```shell
obmc-console-client
```

**Note**: The boot order resets to default when a BFB image from NVIDIA is installed.

## Adding a DPU to MAAS

DPUs are added similarly to regular machines, with specific requirements to ensure proper registration.

### Via the MAAS UI

1. Navigate to **Machines** → **Add Machine**  
2. Enter the DPU details:  
   - **Architecture**: `arm64/generic`  
   - **Minimum kernel**: `hwe-22.04` or newer  
   - **MAC address**: The DPU's primary MAC address  
3. Configure power settings:  
   - **Power type**: `Redfish`  
   - **Power address**: DPU BMC IP address  
   - **Power user**: BMC username  
   - **Power password**: BMC password  
4. **Important**: Check the **"Register as DPU"** checkbox  
5. Click **Save**

### Via the MAAS CLI

```shell
maas $PROFILE machines create \
  architecture=arm64/generic \
  min_hwe_kernel="hwe-22.04" \
  mac_addresses=$MAC_ADDRESS \
  is_dpu=true \
  power_type=redfish \
  power_parameters_power_user=$BMC_USER \
  power_parameters_power_address=$BMC_IP \
  power_parameters_power_pass=$BMC_PASS
```

**Critical**: Always set `is_dpu=true` to avoid undefined behavior.

### Post-Registration Configuration

#### Optional: Create a Tag for Boot Parameters

To add required kernel boot parameters for console access:

```shell
maas $PROFILE tags create \
  name=bf3 \
  kernel_opts="console=hvc0 console=ttyAMA0 earlycon=pl011,0x13010000 fixrtc net.ifnames=0 biosdevname=0 iommu.passthrough=1"
```

Then assign this tag to the DPU machine.

## Commissioning the DPU

Commissioning discovers hardware details and prepares the DPU for deployment.

### Prerequisites

- DPU is powered on (via powered-on host)  
- DPU is set to PXE boot  
- Minimum kernel is `hwe-22.04` or newer

### Commissioning Process

#### Via the MAAS UI

1. Select the DPU machine  
2. Click **Take action** → **Commission**  
3. Optionally select additional commissioning scripts  
4. Click **Commission machine**

#### Via the MAAS CLI

```shell
maas $PROFILE machine commission $SYSTEM_ID
```

### Verification

MAAS will:

- Reset the DPU via the BMC  
- Boot into an ephemeral Noble environment  
- Detect hardware (CPU, memory, OOB interface, P0, P1)  
- Run commissioning scripts  
- Mark the DPU as **Ready**

**Note**: Only the OOB, P0, and P1 interfaces are detected during commissioning. Host representor interfaces (`pf0hpf`, `pf1hpf`) and `tmfifo_net0` only appear after deploying an OS with DOCA runtime packages.

## Deployment

Deploy the DPU with an operating system and configuration.

### Deployment Options

You have two main deployment strategies:

1. **Standard Ubuntu images** (Jammy HWE or Noble)  
2. **Custom packer-maas images** with DOCA packages pre-installed

For production deployments, consider using [packer-maas](https://github.com/canonical/packer-maas) to build custom Ubuntu images that include the BlueField kernel, DOCA runtime, and required NVIDIA packages. The repository includes example customization scripts for DOCA 2.9 LTS and DOCA 3.2.0 that handle package installation and configuration. Build on an ARM64 machine using

```shell
make custom-cloudimg.tar.gz SERIES=jammy ARCH=arm64 CUSTOMIZE=scripts/examples/bluefield-doca-2-9-lts.sh
```

Then upload the resulting image to MAAS. See the [Ubuntu image build documentation](https://github.com/canonical/packer-maas/tree/main/ubuntu) for details.

### Prerequisites

- DPU must be in **Ready** state  
- Jammy HWE (`hwe-22.04`) or Noble kernel required  
- For custom images: Upload custom image with DOCA packages

### Deploy via MAAS UI

1. Select the commissioned DPU  
2. Click **Take action** → **Deploy**  
3. Configure deployment:  
   - **Operating system**: Ubuntu  
   - **Release**: Ubuntu 22.04 LTS (Jammy Jellyfish) or later  
   - **Kernel**: `hwe-22.04` or `ga-24.04`  
4. (Optional) Add cloud-init user-data for post-deployment configuration  
5. Click **Start deployment**

### Deploy via MAAS CLI

Using a standard image:

```shell
maas $PROFILE machine deploy $SYSTEM_ID \
  distro_series=jammy \
  hwe_kernel=hwe-22.04
```

Using a custom image:

```shell
maas $PROFILE machine deploy $SYSTEM_ID \
  osystem=custom \
  distro_series=ubuntu-bf-doca-2-9 \
  user_data=$(base64 -w0 cloud-init.yaml)
```

### Deployment Process

MAAS will:

1. Reset the DPU  
2. Configure PXE boot  
3. Boot into ephemeral environment  
4. Partition storage and install OS  
5. Reboot into installed OS  
6. Run cloud-init for final configuration  
7. Mark as **Deployed**

### Cloud-Init Customization

Example cloud-init configuration for DOCA services:

```
#cloud-config
packages:
  - mlnx-ofed-kernel-modules
  - doca-runtime

runcmd:
  - systemctl enable openvswitch-switch
  - systemctl start openvswitch-switch
```

### Verification

After deployment:

1. Check status in MAAS UI (should show **Deployed**)  
2. SSH to the DPU:

```shell
ssh ubuntu@<dpu-ip-address>
```

3. Verify services:

```shell
systemctl status openvswitch-switch
ip link show
```

## Releasing a DPU

When finished with a DPU, release it back to the available pool.

### Important Notes

- Releasing a DPU marks it as **Ready** but does **not**:  
    
  - Reset the DPU configuration  
  - Erase disks  
  - Run post-release scripts


- To ensure the DPU is brought into a clean slate, redeploy it

### Release via MAAS UI

1. Select the deployed DPU  
2. Click **Take action** → **Release**  
3. Click **Release machine**

### Release via MAAS CLI

```shell
maas $PROFILE machine release $SYSTEM_ID
```

## Important Considerations

### DPU-Host Relationship

- The DPU's power state is tied to the host machine  
- Host must remain powered on during DPU commissioning/deployment  
- A host power cycle is required to apply firmware configuration changes

### Network Interface Detection

- During commissioning: Only OOB, P0, and P1 interfaces are detected  
- After DOCA deployment: Additional interfaces appear (`tmfifo_net0`, `pf0hpf`, `pf1hpf`)  
- MAAS cannot currently manage OVS bridges or these additional interfaces via UI  
- Use cloud-init or manual configuration for advanced networking

### Firmware Compatibility

- Firmware version must match the DOCA version in the deployed image  
  - With customized images or when installing the firmware updater in the deployed machine, you can trigger firmware installation from cloud-init by using: `/opt/mellanox/mlnx-fw-updater/mlnx_fw_updater.pl -v --fw-dir /opt/mellanox/mlnx-fw-updater/firmware --force-fw-update`  
- Firmware mismatch can cause high-speed interface initialization failures  
- Always use OOB interface for PXE boot to avoid connectivity loss  
- Firmware updates may require a host power cycle to apply changes

### Limitations

- HW sync during deployment detects some interfaces but causes issues on re-deployment  
- OVS bridge creation triggered by MAAS marking openvswitch as required, conflicts with NVIDIA DOCA OVS (when using customized packer images that include this version of OVS instead of upstream)  
- No automatic post-release cleanup

## Troubleshooting

### DPU Fails to Commission

- Verify host machine is powered on  
- Check BMC connectivity and credentials  
- Ensure PXE boot is configured on OOB interface  
- Confirm Noble ARM64 images are synced  
- Review logs: `/var/log/maas/rackd.log` and `/var/log/maas/regiond.log`

### Deployment Hangs or Fails

- Verify minimum kernel is `hwe-22.04` or newer  
- Check network configuration (DHCP, TFTP, HTTP)  
- Review deployment logs in MAAS UI or via CLI:

```shell
maas $PROFILE events query machine=$SYSTEM_ID
```

- Check cloud-init logs on DPU: `/var/log/cloud-init.log`

### BMC Power Control Issues

- Test BMC access manually:

```shell
curl -k -u $BMC_USER:$BMC_PASS https://$BMC_IP/redfish/v1/Systems/Bluefield
```

- Verify BMC credentials and network accessibility  
- Check for firmware compatibility issues

### Network Interfaces Not Detected

- Ensure DOCA runtime packages are installed  
- Verify firmware version matches DOCA version  
- Check that DPU is in DPU mode (not NIC or Restricted)  
- Review kernel logs: `dmesg | grep mlx`

### Firmware Version Mismatch

- Update firmware from host or BMC before deployment  
- Use cloud-init to trigger firmware update on first boot  
- Perform host power cycle to apply firmware changes

## Additional Resources

- [MAAS Documentation \- How to Manage Machines](https://maas.io/docs/how-to-manage-machines)  
- [NVIDIA BlueField Documentation](https://docs.nvidia.com/networking/category/bluefieldsw)  
- [BlueField BSP Documentation](https://docs.nvidia.com/networking/display/bluefieldbsp491)  
- [Building Custom Images with packer-maas](https://github.com/canonical/packer-maas/tree/main/ubuntu)
