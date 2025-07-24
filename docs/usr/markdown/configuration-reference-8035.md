Configure several aspects of MAAS:

- MAAS behavior settings
- Rack controller port settings
- Interface parameters

## MAAS behavior settings

Change MAAS settings and behavior to suit your environment.  For the CLI, prefix the listed commands with:
```bash
maas $PROFILE maas set-config ...
```

> *Check the special commands at the bottom of the table, also*

| **Setting**                                  | **Description**                                                 | **UI** *Settings* >                   | **CLI**                     | **Example/Notes**                                |
|----------------------------------------------|-----------------------------------------------------------------|---------------------------------------|-----------------------------|--------------------------------------------------|
| **MAAS Name**                                | Assign a unique name and emoji to identify your MAAS instance.  | *Configuration* > *General*           | maas_name                   | `US-west-2 🇺🇸 MAAS-prod`                         |
| **Theme Main Colour**                        | Set a custom theme colour for the MAAS interface.               | *Configuration* > *General*           |                             | Helps differentiate instances visually.          |
| **Data Analytics**                           | Enable analytics to improve user experience.                    | *Configuration* > *General*           | enable_analytics            | Uses Google Analytics, Usabilla, and Sentry.     |
| **Notifications**                            | Enable notifications for new releases.                          | *Configuration* > *General*           | release_notifications       | Helps keep you informed of updates.              |
| **Default Ubuntu Release for Commissioning** | Set the default Ubuntu version for new machine commissioning.   | *Configuration* > *Commissioning*     | commissioning_distro_series | Default: Ubuntu 20.04 LTS.                       |
| **Default Minimum Kernel Version**           | Set the lowest allowed kernel version for new nodes.            | *Configuration* > *Commissioning*     | default_min_hwe_kernel      | No minimum by default.                           |
| **Default OS for Deployment**                | Set the default operating system for deployments.               | *Configuration* > *Deploy*            | default_osystem             | Example: Ubuntu, CentOS.                         |
| **Default OS Release for Deployment**        | Set the specific OS release for deployments.                    | *Configuration* > *Deploy*            | default_distro_series       | Example: Ubuntu 22.04, CentOS 7.                 |
| **Hardware Sync Interval**                   | Frequency of hardware info syncs (in minutes).                  | *Configuration* > *Deploy*            | hardware_sync_interval      | Default: 15 minutes.                             |
| **Global Kernel Parameters**                 | Set boot parameters for all machines.                           | *Configuration* > *Kernel parameters* | kernel_opts                 | Apply settings consistently during boot.         |
| **Session Timeout**                          | Set how long user sessions remain active.                       | *Security* > *Session timeout*        | session_length              | Max: 14 days. Example: “2 weeks” or “336 hours.” |
| **IPMI Settings**                            | Configure IPMI username, key, and privilege level.              | *Security* > *IPMI settings*          | maas_auto_ipmi_...          | Privilege levels: Admin, Operator, User.         |
| **User Management**                          | Manage users, including adding, editing, and deleting users.    | *Users*                               |                             | Search and sort users easily.                    |
| **Proprietary Drivers**                      | Enable proprietary drivers (e.g., HPVSA).                       | *Images* > *Ubuntu*                   | enable_third_party_drivers  | Needed for certain hardware setups.              |
| **Windows KMS Host**                         | Set the host for Windows KMS activation.                        | *Images* > *Windows*                  | windows_kms_host            | Enter FQDN or IP of the KMS host.                |
| **VMware vCenter Server**                    | Configure VMware vCenter settings (FQDN, username, datacenter). | *Images* > *VMware*                   | vcenter_...                 | Required for VMware ESXi deployments.            |
| **License Keys**                             | Add and manage product license keys.                            | *License keys*                        |                             | Sortable, searchable table for licenses.         |
| **Default Storage Layout**                   | Set the storage layout applied during commissioning.            | *Storage*                             | default_storage_layout      | Options: Bcache, Flat, LVM, etc.                 |
| **Disk Erasure Options**                     | Choose secure or quick disk erasure methods.                    | *Storage*                             | disk_erase_with_...         | Secure erase for supported devices.              |
| **HTTP Proxy**                               | Configure proxy for image downloads and package access.         | *Network* > *Proxy*                   | http_proxy                  | Options: No proxy, Built-in, External, Peer.     |
| **Upstream DNS**                             | Set DNS servers for resolving external domains.                 | *Network* > *DNS*                     | upstream_DNS                | Example: `8.8.8.8` for Google DNS.               |
| **NTP Server**                               | Configure NTP servers for time sync.                            | *Network* > *NTP*                     | ntp_servers                 | Use external NTP servers only if needed.         |
| **Remote Syslog Server**                     | Forward logs to a remote syslog server.                         | *Network* > *Syslog*                  | remote_syslog               | Helps centralize logging.                        |
| **Network Discovery**                        | Enable passive or active network discovery.                     | *Network* > *Network discovery*       | network_discovery           | Keeps discovery info accurate.                   |
| **Commissioning Scripts**                    | Upload and manage commissioning scripts.                        | *Scripts* > *Commissioning scripts*   |                             | Scripts run during hardware setup.               |
| **Testing Scripts**                          | Upload and manage testing scripts.                              | *Scripts* > *Testing scripts*         |                             | Scripts run to test hardware.                    |
| **DHCP Snippets**                            | Manage DHCP configuration snippets.                             | *DHCP snippets*                       |                             | Useful for custom DHCP settings.                 |
| **Package Repos**                            | Add and manage APT/YUM repositories.                            | *Package repos*                       |                             | Add PPAs or custom repos.                        |

### Special commands

To enable TLS for secure communication: 
```bash 
sudo maas config-tls enable $key $cert --port YYYY
```

To enable Vault for secure secrets management:
```bash
sudo maas config-vault configure ...
```

## Controller port settings

Essential TCP ports for MAAS communication:

| Port(s)         | Description                                                                               |
|-----------------|-------------------------------------------------------------------------------------------|
| `5240`          | HTTP traffic with each region controller. In HA environments, port `80` is commonly used. |
| `5241` - `5247` | Allocated for MAAS internal services.                                                    |
| `5248`          | Designated for rack HTTP communication.                                                  |
| `5250` - `5270` | Reserved for region workers (RPC).                                                       |
| `5271` - `5274` | Required for communication between Rack Controller (specifically maas-agent) and Region Controller | 
| `5281` - `5284` | Region Controller Temporal cluster membership gossip communication         |

## Interface parameters

The following tables may be needed to manage MAAS interfaces.

### Bond interface parameters
| Parameter               | Description                 | Req'd? | Allowable values  |
|-------------------------|-----------------------------|--------|-------------------|
| `name`                  | I/F name                    | Yes    | String data       |
| `mac_address`           | MAC address of the I/F      | No     | String data       |
| `tags`                  | Tags to apply to the I/F    | No     | String data       |
| `vlan`                  | VLAN connected to I/F       | No     | String data       |
| `parents`               | Bonded I/F IDs              | Yes    | Integers          |
| `bond-mode`             | Operating mode of the bond  | No     | *See table below* |
| `bond_miimon`           | Link monitoring freq in ms  | No     | Integer           |
| `bond_downdelay`        | Slave timeout in ms         | No     | Integer           |
| `bond-updelay`          | Reset recovery delay in ms  | No     | Integer           |
| `bond_lacp-rate`        | LACPDU 802.3ad rate         | No     | "Fast"/"Slow"     |
| `bond_xmit_hash_policy` | Slave selection hash policy | No     | String            |
| `bond_num_grat_arp`     | Peer failover ping count    | No     | Integer           |
| `mtu`                   | Max transmission unit size  | No     | Integer           |
| `accept_ra`             | Accept router adverts       | No     | Boolean           |

> *See [Bond two interfaces](https://maas.io/docs/how-to-manage-maas-networks#p-9070-bond-two-interfaces) for instructions on how to use and apply these parameters.*

### Physical interface parameters 
| key         | value                    | format  | type     |
|-------------|--------------------------|---------|----------|
| name        | name of the interface    | string  | optional |
| mac_address | MAC address of interface | string  | required |
| tags        | tags                     | string  | optional |
| vlan        | connected, untagged VLAN | string  | optional |
| mtu         | max transmission unit    | integer | optional |
| accept_ra   | accept router adverts    | boolean | optional |

> *Note that if no VLAN is specified, the interface is considered disconnected.*

### VLAN interface parameters 
| key       | value                    | format  | type     |
|-----------|--------------------------|---------|----------|
| tags      | tags                     | string  | optional |
| vlan      | connected, untagged VLAN | string  | required |
| parent    | parent interface ID      | string  | required |
| mtu       | max transmission unit    | integer | optional |
| accept_ra | accept router adverts    | boolean | optional |

### Interface-subnet link parameters 
| key             | value                 | format  | type     | mode    |
|-----------------|-----------------------|---------|----------|---------|
| mode            | See table below       | string  | required | ----    |
| subnet          | the linked subnet     | integer | required | any     |
| ip_address      | IP addr for interface | string  | optional | STATIC  |
| force           | force up, any VLAN    | boolean | optional | LINK_UP |
| default_gateway | subnet gateway IP     | string  | optional | AUTO    |
| ^^              |                       |         |          | STATIC  |


#### Interface-subnet link modes
| mode    | description                                                                                                                                                                       |
|---------|-----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| AUTO    | Assign this interface a static IP address from the provided subnet. The subnet must be a managed subnet. The IP address will not  be assigned until the node goes to be deployed. |
| DHCP    | Bring this interface up with DHCP on the given subnet. Only one subnet can be set to ``DHCP``. If the subnet is managed this interface will pull from the dynamic IP range.       |
| STATIC  | Bring this interface up with a static IP address on the given subnet. Any number of static links can exist on an interface.                                                       |
| LINK_UP | Bring this interface up only on the given subnet. No IP address will be assigned to this interface. The interface cannot have any current ``AUTO``, ``DHCP`` or ``STATIC`` links. |
