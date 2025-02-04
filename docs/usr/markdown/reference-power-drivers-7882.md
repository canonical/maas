The following page catalogs the fields in the "create machine" dialogue for each supported power driver. Note that most of the multiple-choice fields have drop-down menus to assist with your choice.  In the next section we introduce configuring power drivers using the UI. In "CLI parameter expressions," you will find how to configure them using the CLI.

## UI parameter expressions 
### Intel AMT

| Form field | Description | Required |
|:-----|:-----|:-----|
| Power password | Password to access unit | Optional |
| Power address | IP address of unit | Required |

### American Power Conversion (APC) PDU

| Form field | Description | Required |
|:-----|:-----|:-----|
| IP for APC PDU | IP address of unit | Required |
| APU PDU node outlet number (1-16) | PDU node outlet number | Required |
| Power ON outlet delay (seconds) | outlet power ON delay | Optional, default=5 |

### Digital Loggers, Inc. PDU

| Form field | Description | Required |
|:-----|:-----|:-----|
| Outlet ID | outlet ID | Required |
| Power address | IP address of unit | Required |
| Power user | Username to login | Optional |
| Power password | Password to access unit | Optional |

### IBM Hardware Management Console (HMC)

| Form field | Description | Required |
|:-----|:-----|:-----|
| IP for HMC | IP address of unit | Required |
| HMC username | Username to login | Optional |
| HMC password | Password to access unit | Optional |
| HMC Managed System server name | HMC managed server name | Required |
| HMC logical partition | HMC logical partition of unit | Required |

### LXD VMs

| Form field | Description | Required |
|:-----|:-----|:-----|
| LXD address | IP address of unit | Required |
| Instance name | LXD container instance name | Required |
| LXD password | Password to access unit | Optional |

### IPMI

Some of the fields for this power type have fixed choices, indicated in the "Choices" column.

| Form field | Description | Choices | Required |
|:-----------|:------------|:--------|:---------|
| Power driver | Power driver |`LAN [IPMI 1.5]` | Required |
| | | `LAN_2_0 [IPMI 2.0]`| |
| Power boot type | Boot type | `Automatic` | Required |
| | | `Legacy boot` | |
| | | `EFI boot` | |
| IP address | IP address of unit || Required |
| Power user | Username to login || Optional |
| Power password | Password to access unit || Optional |
| Power MAC | MAC address of unit || Optional |
| K_g | K_g BMC key | | Optional |
| Cipher suite | Cipher suite ID | - `17` <small>(17 - HMAC-SHA256::HMAC_SHA256_128::AES-CBC-128)</small> | Optional |
| | |`3` <small>(3 - HMAC-SHA1::HMAC-SHA1-96::AES-CBC-128)</small> | |
| | |` ` (blank) <small>(freeipmi-tools default)</small> | |
| | |`8` <small>(8 - HMAC-MD5::HMAC-MD5-128::AES-CBC-128)</small> | |
| | |`12` <small>(12 - HMAC-MD5::MD5-128::AES-CBC-128)</small> | |
| Privilege level | IPMI privilege level | `User` | Optional  |
| | | `Operator` | |
| | | `Administrator` | |

### Manual power configuration

Manual power configuration means exactly that -- manually configured at the unit -- hence there are no parameters to set in the "create machine" UI.

### HP Moonshot - iLO4 (IPMI)

| Form field | Description | Required |
|:-----|:-----|:-----|
| Power address | IP address of unit | Required |
| Power user | Username to login | Optional |
| Power password | Password to access unit | Optional |
| Power hardware address | Hardware address of unit | Required |

### HP Moonshot - iLO Chassis Manager

| Form field | Description | Required |
|:-----|:-----|:-----|
| IP for MSCM CLI API | IP address of unit | Required |
| MSCM CLI API user | Username to login | Optional |
| MSCM CLI API password | Password to access unit | Optional |
| Node ID | cXnY | Required |
|  - where  | X = cartridge number | |
|           | Y = node number | |

### Microsoft OCS - Chassis Manager

| Form field | Description | Required |
|:-----|:-----|:-----|
| Power address | IP address of unit | Required |
| Power port | Port where unit is attached | Optional |
| Power user | Username to login | Optional |
| Power password | Password to access unit | Optional |
| Blade ID | Blade ID (usu. 1-24) | Required |

### OpenStack Nova

| Form field | Description | Required |
|:-----|:-----|:-----|
| Host UUID | Host UUID | Required |
| Tenant name | Tenant name | Required |
| Username | Username to login | Required |
| Password | Password to access unit | Required |
| Auth URL | URL to access unit | Required |

### Proxmox

| Form field | Description | Required |
|:-----|:-----|:-----|
| Power type | Proxmox | Required |
| Host name or IP | Power address for the Proxmox driver | Required |
| Username, including realm | Power user, along with realm (i.e., Username@Realm | Required |
| Password | Required if a token name and secret aren't given | Provisional |
| API token name | Token name: must include Username without realm (i.e., Username!Token-name | Provisional |
| API token secret | Token secret | Provisional |
| Node ID | VM name or ID | Optional |
| Verify SSL connections... | Boolean, whether or not to verify SSL connections with the system's root CA certificate | Required |

### OpenBMC Power Driver

| Form field | Description | Required |
|:-----|:-----|:-----|
| OpenBMC address | IP address of unit | Required |
| OpenBMC user | Username to login | Required |
| OpenBMC password | Password to access unit | Required |

### Christmann RECS-Box Power Driver

| Form field | Description | Required |
|:-----|:-----|:-----|
| Node ID | Node ID | Required |
| Power address | IP address of unit | Required |
| Power port | Port where unit is attached | Optional |
| Power user | Username to login | Optional |
| Power password | Password to access unit | Optional |

### Redfish

| Form field | Description | Required |
|:-----|:-----|:-----|
| Redfish address | IP address of unit | Required |
| Redfish user | Username to login | Required |
| Redfish password | Password to access unit | Required |
| Node ID | Node ID | Optional |

### SeaMicro 15000

Some of the fields for this power type have fixed choices, indicated in the "Choices" column.

| Form field | Description | Choices | Required |
|:-----|:-----|:-----|:-----|
| System ID | System ID || Required |
| Power address | IP address of unit || Required |
| Power user | Username to login || Optional |
| Power password | Password to access unit || Optional |
| Power control type | Password to access unit| IPMI | Required |
|  |  | REST API v0.9 | |
|  |  | REST API v2.0 | |

### Cisco UCS Manager

| Form field | Description | Required |
|:-----|:-----|:-----|
| Server UUID | Server UUID | Required |
| URL for XML API | XML API URL | Required |
| API user | API user | Optional |
| API password | API password | Optional |

### virsh - libvirt KVM

| Form field | Description | Required |
|:-----|:-----|:-----|
| Address | URL of VM | Required |
| Password | API password | Optional |
| Virsh VM ID | libvirt VM UUID | Required |

### VMware

| Form field | Description | Required |
|:-----|:-----|:-----|
| VM Name | VM name (if UUID unknown) | Optional |
| VM UUID | VM UUID (if known) | Optional |
| VMware IP | IP address of VM | Required |
| VMware username | Username to access VM | Required |
| VMware password | Password to access VM | Required |
| VMware API port | VMware API port number | Optional |
| VMware API protocol | VMware API protocol | Optional |

### Facebook's Wedge

| Form field | Description | Required |
|:-----|:-----|:-----|
| IP address | IP address of unit | Required |
| Power user | Username to access unit | Optional |
| Power password | Password to access unit | Optional |

### Virsh power type (UI)

Consider a machine backed by VM. Below, a 'Power type' of `Virsh` has been selected, and the 'Power address' of `qemu+ssh://ubuntu@192.168.1.2/system` has been entered (replace values as appropriate). The value of 'Power ID' is the VM domain (guest) name, here `node2`.

<a href="https://assets.ubuntu.com/v1/c75e00a8-nodes-power-types__2.4_example-virsh.png" target = "_blank"><img src="upload://srGpNVADogLofh3aNSB9rBKX95C.png"></a>

> **Pro tip**: The machine's hostname -- according to MAAS -- is a randomly chosen string (here `dear.ant`). You should change this hostname to something descriptive, that helps you remember why this machine is in your MAAS network.

### Webhook

It's important to understand that the Webhook power driver is more generic than other drivers, so it has some flexibility that the underlying power driver may not support. For example, Webhook doesn't require a username or password for the power driver, because not all power drivers work that way. Nevertheless, the power driver you're connecting to Webhook may actually require a username and/or password. Understanding and implementing these fields correctly for the chosen back-end power driver is the user's responsibility.

To that end, the "Required" column for this driver refers only to whether Webhook requires a value in each field. Just because a field is optional for Webhook itself does not mean that the underlying power driver will ultimately allow that field to be unspecified.

| Form field | Description | Required (by Webhook) |
|:-----|:-----|:-----|
| Power type | Webhook (from drop-down list) | Required |
| URI to power on the node | URI to access power driver's API for power on | Required |
| URI to power off the node | URI to access power driver's API for power off | Required |
| URI to query the nodes power status | URI to access power driver's API for power status | Required |
| Regex to confirm the node is on | Regex expression that will return a string if the power is on, and no string if the power is off | Required, defaults supplied |
| Regex to confirm the node is off | Regex expression that will return a string if the power is off, and no string if the power is on | Required, defaults supplied |
| Power user | Username to log into the power driver | Optional |
| Power password | Password to access unit | Optional |
| Power token | Power driver API token (used instead of user and password, if set) | Optional |
| Verify SSL connections... | Boolean, whether or not to verify SSL connections with the system's root CA certificate | Required |

## CLI parameter expressions
### Intel AMT

All parameters are entered as `key=value`, e.g., `power_type=amt`. The MAAS CLI will refuse the request with informative errors if required parameters are excluded.

| Parameter | Description | Required |
|:-----|:-----|:-----|
| `power_type` | `amt` | Required |
| `power_address` | IP address of unit | Required |
| `power_pass` | Password to access unit | Optional |

### American Power Conversion (APC) PDU

All parameters are entered as `key=value`, e.g., `power_type=apc`. The MAAS CLI will refuse the request with informative errors if required parameters are excluded.

| Parameter | Description | Required |
|:-----|:-----|:-----|
| `power_type` | `apc` | Required |
| `power_address` | IP address of unit | Required |
| `node_outlet` | PDU node outlet number | Required |
| `power_on_delay` | outlet power ON delay | Optional, default=5 |

### Digital Loggers, Inc. PDU

All parameters are entered as `key=value`, e.g., `power_type=dli`. The MAAS CLI will refuse the request with informative errors if required parameters are excluded.

| Parameter | Description | Required |
|:-----|:-----|:-----|
| `power_type` | `dli` | Required |
| `outlet_id` | outlet ID | Required |
| `power_address` | IP address of unit | Required |
| `power_user` | Username to login | Optional |
| `power_pass` | Password to access unit | Optional |

### Eaton PDU

All parameters are entered as `key=value`, e.g., `power_type=eaton`. The MAAS CLI will refuse the request with informative errors if required parameters are excluded.

| Parameter | Description | Required |
|:-----|:-----|:-----|
| `power_type` | `eaton` | Required |
| `power_address` | IP address of unit | Required |
| `node_outlet` | PDU node outlet number | Required |
| `power_on_delay` | outlet power ON delay | Optional, default=5 |

### IBM Hardware Management Console (HMC)

All parameters are entered as `key=value`, e.g., `power_type=hmc`. The MAAS CLI will refuse the request with informative errors if required parameters are excluded.

| Parameter | Description | Required |
|:-----|:-----|:-----|
| `power_type` | `hmc` | Required |
| `power_address` | IP address of unit | Required |
| `server_name` | HMC managed server name | Required |
| `lpar` | HMC logical partition of unit | Required |
| `power_user` | Username to login | Optional |
| `power_pass` | Password to access unit | Optional |

### LXD VMs

All parameters are entered as `key=value`, e.g., `power_type=lxd`. The MAAS CLI will refuse the request with informative errors if required parameters are excluded.

| Parameter | Description | Required |
|:-----|:-----|:-----|
| `power_type` | `lxd` | Required |
| `power_address` | IP address of unit | Required |
| `instance_name` | LXD container instance name | Required |
| `power_pass` | Password to access unit | Optional |

### IPMI

All parameters are entered as `key=value`, e.g., `power_type=amt`. The MAAS CLI will refuse the request with informative errors if required parameters are excluded. Power driver specific parameters should be prefixed with `power_parameters_{key}`.

Some of the fields for this power type have fixed choices, indicated in the "Choices" column.

| Form field | Description | Choices | Required |
|:-----------|:------------|:--------|:---------|
| `power_driver` | Power driver |`LAN [IPMI 1.5]` | Required |
| | | `LAN_2_0 [IPMI 2.0]`| |
| `power_boot_type` | Boot type | `Automatic` | Required |
| | | `Legacy boot` | |
| | | `EFI boot` | |
| `power_address` | IP address of unit || Required |
| `power_user` | Username to login || Optional |
| `power_pass` | Password to access unit || Optional |
| `mac_address` | MAC address of unit || Optional |
| `k_g` | K_g BMC key | | Optional |
| `cipher_suite_id` | Cipher suite ID |`17` <small>(17 - HMAC-SHA256::HMAC_SHA256_128::AES-CBC-128)</small> | Optional |
| | |`3` <small>(3 - HMAC-SHA1::HMAC-SHA1-96::AES-CBC-128)</small> | |
| | |` ` (blank) <small>(freeipmi-tools default)</small> | |
| | |`8` <small>(8 - HMAC-MD5::HMAC-MD5-128::AES-CBC-128)</small> | |
| | |`12` <small>(12 - HMAC-MD5::MD5-128::AES-CBC-128)</small> | |
| `privilege_level` | IPMI privilege level | `User` | Optional  |
| | | `Operator` | |
| | | `Administrator` | |

### Manual power configuration

Manual power configuration means exactly that -- manually configured at the unit. The only MAAS CLI parameter is `power_type=amt`. 

### HP Moonshot - iLO4 (IPMI)

All parameters are entered as `key=value`, e.g., `power_type=moonshot`. The MAAS CLI will refuse the request with informative errors if required parameters are excluded.

| Parameter | Description | Required |
|:-----|:-----|:-----|
| `power_type | `moonshot` | Required |
| `power_address` | IP address of unit | Required |
| `power_hwaddress` | Hardware address of unit | Required |
| `power_user` | Username to login | Optional |
| `power_pass` | Password to access unit | Optional |

### HP Moonshot - iLO Chassis Manager

All parameters are entered as `key=value`, e.g., `power_type=mscm`. The MAAS CLI will refuse the request with informative errors if required parameters are excluded.

| Parameter | Description | Required |
|:-----|:-----|:-----|
| `power_type | `mscm` | Required |
| `power_address` | IP address of unit | Required |
| `node_id` | cXnY | Required |
|  - where  | X = cartridge number | |
|           | Y = node number | |
| `power_user` | Username to login | Optional |
| `power_pass` | Password to access unit | Optional |

### Microsoft OCS - Chassis Manager

All parameters are entered as `key=value`, e.g., `power_type=msftocs`. The MAAS CLI will refuse the request with informative errors if required parameters are excluded.

| Parameter | Description | Required |
|:-----|:-----|:-----|
| `power_type | `msftocs` | Required |
| `power_address` | IP address of unit | Required |
| `blade_id` | Blade ID (usu. 1-24) | Required |
| `power_port` | Port where unit is attached | Optional |
| `power_user` | Username to login | Optional |
| `power_pass` | Password to access unit | Optional |

### OpenStack Nova

All parameters are entered as `key=value`, e.g., `power_type=nova`. The MAAS CLI will refuse the request with informative errors if required parameters are excluded.

| Parameter | Description | Required |
|:-----|:-----|:-----|
| `power_type | `nova` | Required |
| `nova_id` | Host UUID | Required |
| `os_tenantname` | Tenant name | Required |
| `os_username` | Username to login | Required |
| `os_password` | Password to access unit | Required |
| `os_authurl` | URL to access unit | Required |

### OpenBMC Power Driver

All parameters are entered as `key=value`, e.g., `power_type=openbmc`. The MAAS CLI will refuse the request with informative errors if required parameters are excluded.

| Parameter | Description | Required |
|:-----|:-----|:-----|
| `power_type` | `openbmc` | Required |
| `power_address` | IP address of unit | Required |
| `power_user` | Username to login | Required |
| `power_pass` | Password to access unit | Required |

### Christmann RECS-Box Power Driver

All parameters are entered as `key=value`, e.g., `power_type=recs_box`. The MAAS CLI will refuse the request with informative errors if required parameters are excluded.

| Parameter | Description | Required |
|:-----|:-----|:-----|
| `power_type | `recs_box` | Required |
| `node_id` | Node ID | Required |
| `power_address` | IP address of unit | Required |
| `power_port` | Port where unit is attached | Optional |
| `power_user` | Username to login | Optional |
| `power_pass` | Password to access unit | Optional |

### Redfish

All parameters are entered as `key=value`, e.g., `power_type=redfish`. The MAAS CLI will refuse the request with informative errors if required parameters are excluded.

| Parameter | Description | Required |
|:-----|:-----|:-----|
| `power_type | `redfish` | Required |
| `power_address` | IP address of unit | Required |
| `power_user` | Username to login | Required |
| `power_pass` | Password to access unit | Required |
| `node_id` | Node ID | Optional |

### SeaMicro 15000

All parameters are entered as `key=value`, e.g., `power_type=sm15k`. The MAAS CLI will refuse the request with informative errors if required parameters are excluded.

Some of the fields for this power type have fixed choices, indicated in the "Choices" column.

| Parameter | Description | Choices | Required |
|:-----|:-----|:-----|:-----|
| `power_type` | `sm15k` | | Required |
| `system_id` | System ID || Required |
| `power_address` | IP address of unit || Required |
| `power_control` | Password to access unit| ipmi | Required |
|  |  | restapi | |
|  |  | restapi2 | |
| `power_user` | Username to login || Optional |
| `power_pass` | Password to access unit || Optional |

### Cisco UCS Manager

All parameters are entered as `key=value`, e.g., `power_type=ucsm`. The MAAS CLI will refuse the request with informative errors if required parameters are excluded.

| Parameter | Description | Required |
|:-----|:-----|:-----|
| `power_type` | `ucsm` | Required |
| `uuid` | Server UUID | Required |
| `power_address` | URL for XML API | Required |
| `power_user` | API user | Optional |
| `power_pass` | API password | Optional |

### virsh - libvirt KVM

All parameters are entered as `key=value`, e.g., `power_type=virsh`. The MAAS CLI will refuse the request with informative errors if required parameters are excluded.

| Parameter | Description | Required |
|:-----|:-----|:-----|
| `power_type` | `virsh` | Required |
| `power_id` | libvirt VM UUID | Required |
| `power_address` | URL of VM | Required |
| `power_pass` | API password | Optional |

### VMware

All parameters are entered as `key=value`, e.g., `power_type=vmware`. The MAAS CLI will refuse the request with informative errors if required parameters are excluded.

| Parameter | Description | Required |
|:-----|:-----|:-----|
| `power_type` | `vmware` | Required |
| `power_vm_name` | VM name (if UUID unknown) | Optional |
| `power_uuid` | VM UUID (if known) | Optional |
| `power_address` | IP address of VM | Required |
| `power_user` | Username to access VM | Required |
| `power_pass` | Password to access VM | Required |
| `power_port` | VMware API port number | Optional |
| `power_protocol` | VMware API protocol | Optional |

### Facebook's Wedge

All parameters are entered as `key=value`, e.g., `power_type=amt`. The MAAS CLI will refuse the request with informative errors if required parameters are excluded.

| Parameter | Description | Required |
|:-----|:-----|:-----|
| `power_type` | `wedge` | Required |
| `power_address` | IP address of unit | Required |
| `power_user` | Username to access unit | Optional |
| `power_pass` | Password to access unit | Optional |



### Virsh power type (CLI)

Consider a machine backed by a KVM, accessed via `virsh`. You can create a corresponding MAAS machine and set its power parameters with a command like this one:

    maas admin machines create \
    architecture=amd64 \
    mac_addresses=52:54:00:15:36:f2 \
    power_type=virsh \
    power_parameters_power_id=f677a842-571c-4e65-adc9-11e2cf92d363 \
    power_parameters_power_address=qemu+ssh://stormrider@192.168.123.1/system \
    power_parameters_power_pass=xxxxxxxx

If successful, this will return: 

    Success.

Machine-readable output follows this announcement. The JSON generated by this command is shown in the detail block.

<details><summary>MAAS command JSON response</summary>
```
{
    "storage": 0.0,
    "tag_names": [],
    "special_filesystems": [],
    "memory": 0,
    "boot_disk": null,
    "virtualblockdevice_set": [],
    "hardware_info": {
        "system_vendor": "Unknown",
        "system_product": "Unknown",
        "system_family": "Unknown",
        "system_version": "Unknown",
        "system_sku": "Unknown",
        "system_serial": "Unknown",
        "cpu_model": "Unknown",
        "mainboard_vendor": "Unknown",
        "mainboard_product": "Unknown",
        "mainboard_serial": "Unknown",
        "mainboard_version": "Unknown",
        "mainboard_firmware_vendor": "Unknown",
        "mainboard_firmware_date": "Unknown",
        "mainboard_firmware_version": "Unknown",
        "chassis_vendor": "Unknown",
        "chassis_type": "Unknown",
        "chassis_serial": "Unknown",
        "chassis_version": "Unknown"
    },
    "address_ttl": null,
    "memory_test_status": -1,
    "other_test_status_name": "Unknown",
    "osystem": ",
    "status_message": "Commissioning",
    "netboot": true,
    "physicalblockdevice_set": [],
    "node_type": 0,
    "cpu_test_status": -1,
    "memory_test_status_name": "Unknown",
    "bcaches": [],
    "storage_test_status": 0,
    "system_id": "bhxws3",
    "status": 1,
    "commissioning_status": 0,
    "power_type": "virsh",
    "locked": false,
    "numanode_set": [
        {
            "index": 0,
            "memory": 0,
            "cores": []
        }
    ],
    "bios_boot_method": null,
    "fqdn": "ace-swan.maas",
    "node_type_name": "Machine",
    "hostname": "ace-swan",
    "volume_groups": [],
    "testing_status": 0,
    "network_test_status": -1,
    "other_test_status": -1,
    "interface_test_status": -1,
    "hwe_kernel": null,
    "blockdevice_set": [],
    "testing_status_name": "Pending",
    "power_state": "unknown",
    "min_hwe_kernel": ",
    "owner": "admin",
    "distro_series": ",
    "storage_test_status_name": "Pending",
    "cpu_speed": 0,
    "swap_size": null,
    "cpu_test_status_name": "Unknown",
    "hardware_uuid": null,
    "architecture": "amd64/generic",
    "pool": {
        "name": "default",
        "description": "Default pool",
        "id": 0,
        "resource_uri": "/MAAS/api/2.0/resourcepool/0/"
    },
    "cache_sets": [],
    "pod": null,
    "iscsiblockdevice_set": [],
    "disable_ipv4": false,
    "status_action": ",
    "boot_interface": {
        "name": "eth0",
        "id": 10,
        "product": null,
        "system_id": "bhxws3",
        "effective_mtu": 1500,
        "children": [],
        "link_connected": true,
        "enabled": true,
        "interface_speed": 0,
        "numa_node": 0,
        "firmware_version": null,
        "parents": [],
        "discovered": null,
        "params": ",
        "links": [],
        "sriov_max_vf": 0,
        "tags": [],
        "type": "physical",
        "vlan": null,
        "vendor": null,
        "link_speed": 0,
        "mac_address": "52:54:00:15:36:f2",
        "resource_uri": "/MAAS/api/2.0/nodes/bhxws3/interfaces/10/"
    },
    "cpu_count": 0,
    "domain": {
        "authoritative": true,
        "ttl": null,
        "resource_record_count": 0,
        "name": "maas",
        "is_default": true,
        "id": 0,
        "resource_uri": "/MAAS/api/2.0/domains/0/"
    },
    "current_testing_result_id": 7,
    "default_gateways": {
        "ipv4": {
            "gateway_ip": null,
            "link_id": null
        },
        "ipv6": {
            "gateway_ip": null,
            "link_id": null
        }
    },
    "interface_set": [
        {
            "name": "eth0",
            "id": 10,
            "product": null,
            "system_id": "bhxws3",
            "effective_mtu": 1500,
            "children": [],
            "link_connected": true,
            "enabled": true,
            "interface_speed": 0,
            "numa_node": 0,
            "firmware_version": null,
            "parents": [],
            "discovered": null,
            "params": ",
            "links": [],
            "sriov_max_vf": 0,
            "tags": [],
            "type": "physical",
            "vlan": null,
            "vendor": null,
            "link_speed": 0,
            "mac_address": "52:54:00:15:36:f2",
            "resource_uri": "/MAAS/api/2.0/nodes/bhxws3/interfaces/10/"
        }
    ],
    "status_name": "Commissioning",
    "commissioning_status_name": "Pending",
    "owner_data": {},
    "ip_addresses": [],
    "raids": [],
    "network_test_status_name": "Unknown",
    "description": ",
    "current_commissioning_result_id": 6,
    "interface_test_status_name": "Unknown",
    "current_installation_result_id": null,
    "zone": {
        "name": "default",
        "description": ",
        "id": 1,
        "resource_uri": "/MAAS/api/2.0/zones/default/"
    },
    "resource_uri": "/MAAS/api/2.0/machines/bhxws3/"
}
```
</details>
