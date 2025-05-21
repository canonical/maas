Enter keyword arguments in the form `key=value`.

## Abort a node operation

```bash
maas $PROFILE machine abort [--help] [-d] [-k] system_id [data ...] 
```

#### Positional arguments
- system_id


Abort a node's current operation.

#### Keyword "comment"
Optional String. Comment for the event log.

#### Command-line options
| Option | Effect |
|-----|-----|
| --help, -h | Show this help message and exit. |
| -d, --debug | Display more information about API responses. |
| -k, --insecure | Disable SSL certificate check |

## Clear set default gateways

```bash
maas $PROFILE machine clear-default-gateways [--help] [-d] [-k] system_id [data ...]
```

#### Positional arguments
- system_id

Clear any set default gateways on a machine with the given system_id.

This will clear both IPv4 and IPv6 gateways on the machine. This will transition the logic of identifing the best gateway to MAAS. This logic is determined based the following criteria:

1. Managed subnets over unmanaged subnets.
2. Bond interfaces over physical interfaces.
3. Machine's boot interface over all other interfaces except bonds.
4. Physical interfaces over VLAN interfaces.
5. Sticky IP links over user reserved IP links.
6. User reserved IP links over auto IP links.

If the default gateways need to be specific for this machine you can set which interface and subnet's gateway to use when this machine is deployed with the `interfaces set-default-gateway` API.

#### Command-line options
| Option | Effect |
|-----|-----|
| --help, -h | Show this help message and exit. |
| -d, --debug | Display more information about API responses. |
| -k, --insecure | Disable SSL certificate check |

## Commission a machine

```bash
maas $PROFILE machine commission [--help] [-d] [-k] system_id [data ...]
```

#### Positional arguments
- system_id


Begin commissioning process for a machine.

A machine in the 'ready', 'declared' or 'failed test' state may initiate a commissioning cycle where it is checked out and tested in preparation for transitioning to the 'ready' state. If it is already in the 'ready' state this is considered a re-commissioning process which is useful if commissioning tests were changed after it previously commissioned.

#### Keyword "enable_ssh"
Optional Int. Whether to enable SSH for the commissioning environment using the user's SSH key(s). '1' == True, '0' == False.

#### Keyword "skip_bmc_config"
Optional Int.  Whether to skip re-configuration of the BMC for IPMI based machines. '1' == True, '0' == False.

#### Keyword "skip_networking"
Optional Int.  Whether to skip re-configuring the networking on the machine after the commissioning has completed. '1' == True, '0' == False.

#### Keyword "skip_storage"
Optional Int.  Whether to skip re-configuring the storage on the machine after the commissioning has completed. '1' == True, '0' == False.

#### Keyword "commissioning_scripts"
Optional String.  A comma separated list of commissioning script names and tags to be run. By default all custom commissioning scripts are run. Built-in commissioning scripts always run. Selecting 'update_firmware' or 'configure_hba' will run firmware updates or configure HBA's on matching machines.

#### Keyword "testing_scripts"
Optional String.  A comma separated list of testing script names and tags to be run. By default all tests tagged 'commissioning' will be run. Set to 'none' to disable running tests.

#### Keyword "parameters"
Optional String.  Scripts selected to run may define their own parameters. These parameters may be passed using the parameter name. Optionally a parameter may have the script name prepended to have that parameter only apply to that specific script.

#### Command-line options
| Option | Effect |
|-----|-----|
| --help, -h | Show this help message and exit. |
| -d, --debug | Display more information about API responses. |
| -k, --insecure | Disable SSL certificate check |

## Delete a machine

```bash
maas $PROFILE machine delete [--help] [-d] [-k] system_id [data ...] 
```

#### Positional arguments
- system_id

Deletes a machine with the given system_id.

Note: A machine cannot be deleted if it hosts pod virtual machines. Use ``force`` to override this behavior. Forcing deletion will also remove hosted pods. E.g. ``/machines/abc123/?force=1``.

#### Command-line options
| Option | Effect |
|-----|-----|
| --help, -h | Show this help message and exit. |
| -d, --debug | Display more information about API responses. |
| -k, --insecure | Disable SSL certificate check |

## Deploy a machine

```bash
maas $PROFILE machine deploy [--help] [-d] [-k] system_id [data ...] 
```

#### Positional arguments
- system_id


Deploys an operating system to a machine with the given system_id.

#### Keyword "user_data"
Optional String.  If present, this blob of base64-encoded user-data to be made available to the machines through the metadata service.

#### Keyword "distro_series"
Optional String. If present, this parameter specifies the OS release the machine will use.

#### Keyword "hwe_kernel"
Optional String. If present, this parameter specified the kernel to be used on the machine

#### Keyword "agent_name"
Optional String. An optional agent name to attach to the acquired machine.

#### Keyword "bridge_all"
Optional Boolean.  Optionally create a bridge interface for every configured interface on the machine. The created bridges will be removed once the machine is released. (Default: false)

#### Keyword "bridge_type"
Optional String. Optionally create the bridges with this type. Possible values are: ``standard``, ``ovs``.

#### Keyword "bridge_stp"
Optional Boolean.  Optionally turn spanning tree protocol on or off for the bridges created on every configured interface.  (Default: false)

#### Keyword "bridge_fd"
Optional Int. Optionally adjust the forward delay to time seconds.  (Default: 15)

#### Keyword "comment"
Optional String. Optional comment for the event log.

#### Keyword "install_rackd"
Optional Boolean. If true, the rack controller will be installed on this machine.

#### Keyword "install_kvm"
Optional Boolean. If true, KVM will be installed on this machine and added to MAAS.

#### Keyword "register_vmhost"
Optional Boolean. If true, the machine will be registered as a LXD VM host in MAAS.

#### Keyword "ephemeral_deploy"
Optional Boolean. If true, machine will be deployed ephemerally even if it has disks.

#### Keyword "vcenter_registration"
Optional Boolean. If false, do not send globally defined VMware vCenter credentials to the machine.

#### Keyword "enable_hw_sync"
Optional Boolean.  If true, machine will be deployed with a small agent periodically pushing hardware data to detect any change in devices.

#### Command-line options
| Option | Effect |
|-----|-----|
| --help, -h | Show this help message and exit. |
| -d, --debug | Display more information about API responses. |
| -k, --insecure | Disable SSL certificate check |

## Get system details

```bash
maas $PROFILE machine details [--help] [-d] [-k] system_id [data ...] 
```

#### Positional arguments
- system_id

Returns system details -- for example, LLDP and ``lshw`` XML dumps.

Returns a ``{detail_type: xml, ...}`` map, where ``detail_type`` is something like "lldp" or "lshw".

Note that this is returned as BSON and not JSON. This is for efficiency, but mainly because JSON can't do binary content without applying additional encoding like base-64. The example output below is represented in ASCII using ``bsondump example.bson`` and is for demonstrative purposes.

#### Command-line options
| Option | Effect |
|-----|-----|
| --help, -h | Show this help message and exit. |
| -d, --debug | Display more information about API responses. |
| -k, --insecure | Disable SSL certificate check |

## Exit rescue mode

```bash
maas $PROFILE machine exit-rescue-mode [--help] [-d] [-k] system_id [data ...]
```

#### Positional arguments
- system_id

Exits the rescue mode process on a machine with the given system_id.

A machine in the 'rescue mode' state may exit the rescue mode process.

#### Command-line options
| Option | Effect |
|-----|-----|
| --help, -h | Show this help message and exit. |
| -d, --debug | Display more information about API responses. |
| -k, --insecure | Disable SSL certificate check |

## Get curtin configuration

```bash
maas $PROFILE machine get-curtin-config [--help] [-d] [-k] system_id [data ...]
```

#### Positional arguments
- system_id

Return the rendered curtin configuration for the machine.

#### Command-line options
| Option | Effect |
|-----|-----|
| --help, -h | Show this help message and exit. |
| -d, --debug | Display more information about API responses. |
| -k, --insecure | Disable SSL certificate check |

## Get a machine token

```bash
maas $PROFILE machine get-token [--help] [-d] [-k] system_id [data ...] 
```

#### Positional arguments
- system_id

#### Command-line options
| Option | Effect |
|-----|-----|
| --help, -h | Show this help message and exit. |
| -d, --debug | Display more information about API responses. |
| -k, --insecure | Disable SSL certificate check |

## Lock a machine

```bash
maas $PROFILE machine lock [--help] [-d] [-k] system_id [data ...] 
```

#### Positional arguments
- system_id


Mark a machine with the given system_id as 'Locked' to prevent changes.

#### Keyword "comment"
Optional String. Optional comment for the event log.

#### Command-line options
| Option | Effect |
|-----|-----|
| --help, -h | Show this help message and exit. |
| -d, --debug | Display more information about API responses. |
| -k, --insecure | Disable SSL certificate check |

## Mark a machine as Broken

```bash
maas $PROFILE machine mark-broken [--help] [-d] [-k] system_id [data ...]
```

#### Positional arguments
- system_id


Mark a machine with the given system_id as 'Broken'.

If the node is allocated, release it first.

#### Keyword "comment"
Optional.  Optional comment for the event log. Will be displayed on the node as an error description until marked fixed.

#### Command-line options
| Option | Effect |
|-----|-----|
| --help, -h | Show this help message and exit. |
| -d, --debug | Display more information about API responses. |
| -k, --insecure | Disable SSL certificate check |

## Mark a machine as Fixed

```bash
maas $PROFILE machine mark-fixed [--help] [-d] [-k] system_id [data ...]
```

#### Positional arguments
- system_id


Mark a machine with the given system_id as 'Fixed'.

#### Keyword "comment"
Optional String. Optional comment for the event log.

#### Command-line options
| Option | Effect |
|-----|-----|
| --help, -h | Show this help message and exit. |
| -d, --debug | Display more information about API responses. |
| -k, --insecure | Disable SSL certificate check |

## Mount a special-purpose filesystem

```bash
maas $PROFILE machine mount-special [--help] [-d] [-k] system_id [data ...]
```

#### Positional arguments
- system_id


Mount a special-purpose filesystem, like tmpfs on a machine with the given system_id.

#### Keyword "fstype"
Required String. The filesystem type. This must be a filesystem that does not require a block special device.

#### Keyword "mount_point"
Required String. Path on the filesystem to mount.

#### Keyword "mount_option"
Optional String. Options to pass to mount(8).

#### Command-line options
| Option | Effect |
|-----|-----|
| --help, -h | Show this help message and exit. |
| -d, --debug | Display more information about API responses. |
| -k, --insecure | Disable SSL certificate check |

## Ignore failed tests

```bash
maas $PROFILE machine override-failed-testing [--help] [-d] [-k] system_id [data ...]
```

#### Positional arguments
- system_id


Ignore failed tests and put node back into a usable state.

#### Keyword "comment"
Optional String. Comment for the event log.

#### Command-line options
| Option | Effect |
|-----|-----|
| --help, -h | Show this help message and exit. |
| -d, --debug | Display more information about API responses. |
| -k, --insecure | Disable SSL certificate check |

## Power off a node

```bash
maas $PROFILE machine power-off [--help] [-d] [-k] system_id [data ...] 
```

#### Positional arguments
- system_id


Powers off a given node.

#### Keyword "stop_mode"
Optional String.  Power-off mode. If 'soft', perform a soft power down if the node's power type supports it, otherwise perform a hard power off. For all values other than 'soft', and by default, perform a hard power off. A soft power off generally asks the OS to shutdown the system gracefully before powering off, while a hard power off occurs immediately without any warning to the OS.

#### Keyword "comment"
Optional String. Comment for the event log.

#### Command-line options
| Option | Effect |
|-----|-----|
| --help, -h | Show this help message and exit. |
| -d, --debug | Display more information about API responses. |
| -k, --insecure | Disable SSL certificate check |

## Turn on a node

```bash
maas $PROFILE machine power-on [--help] [-d] [-k] system_id [data ...] 
```

#### Positional arguments
- system_id


Turn on the given node with optional user-data and comment.

#### Keyword "user_data"
Optional String. Base64-encoded blob of data to be made available to the nodes through the metadata service.

#### Keyword "comment"
Optional String. Comment for the event log.

#### Command-line options
| Option | Effect |
|-----|-----|
| --help, -h | Show this help message and exit. |
| -d, --debug | Display more information about API responses. |
| -k, --insecure | Disable SSL certificate check |

## Get power parameters

```bash
maas $PROFILE machine power-parameters [--help] [-d] [-k] system_id [data ...]
```

#### Positional arguments
- system_id

Gets power parameters for a given system_id, if any. For some types of power control this will include private information such as passwords and secret keys.

Note that this method is reserved for admin users and returns a 403 if the user is not one.

#### Command-line options
| Option | Effect |
|-----|-----|
| --help, -h | Show this help message and exit. |
| -d, --debug | Display more information about API responses. |
| -k, --insecure | Disable SSL certificate check |

## Get the power state of a node

```bash
maas $PROFILE machine query-power-state [--help] [-d] [-k] system_id [data ...]
```

#### Positional arguments
- system_id


Gets the power state of a given node. MAAS sends a request to the node's power controller, which asks it about the node's state. The reply to this could be delayed by up to 30 seconds while waiting for the power controller to respond.  Use this method sparingly as it ties up an appserver thread while waiting.

#### Keyword "system_id"
Required String. The node to query.

#### Command-line options
| Option | Effect |
|-----|-----|
| --help, -h | Show this help message and exit. |
| -d, --debug | Display more information about API responses. |
| -k, --insecure | Disable SSL certificate check |

## Read a node

```bash
maas $PROFILE machine read [--help] [-d] [-k] system_id [data ...] 
```

#### Positional arguments
- system_id

Reads a node with the given system_id.

#### Command-line options
| Option | Effect |
|-----|-----|
| --help, -h | Show this help message and exit. |
| -d, --debug | Display more information about API responses. |
| -k, --insecure | Disable SSL certificate check |

## Release a machine

```bash
maas $PROFILE machine release [--help] [-d] [-k] system_id [data ...] 
```

#### Positional arguments
- system_id


Releases a machine with the given system_id. Note that this operation is the opposite of allocating a machine.

**Erasing drives**:

If neither ``secure_erase`` nor ``quick_erase`` are specified, MAAS will overwrite the whole disk with null bytes. This can be very slow.

If both ``secure_erase`` and ``quick_erase`` are specified and the drive does NOT have a secure erase feature, MAAS will behave as if only ``quick_erase`` was specified.

If ``secure_erase`` is specified and ``quick_erase`` is NOT specified and the drive does NOT have a secure erase feature, MAAS will behave as if ``secure_erase`` was NOT specified, i.e. MAAS will overwrite the whole disk with null bytes. This can be very slow.

#### Keyword "comment"
Optional String. Optional comment for the event log.

#### Keyword "erase"
Optional Boolean. Erase the disk when releasing.

#### Keyword "secure_erase"
Optional Boolean.  Use the drive's secure erase feature if available.  In some cases, this can be much faster than overwriting the drive.  Some drives implement secure erasure by overwriting themselves so this could still be slow. 

#### Keyword "quick_erase"
Optional Boolean.  Wipe 2MiB at the start and at the end of the drive to make data recovery inconvenient and unlikely to happen by accident. This is not secure.

#### Keyword "force"
Optional Boolean.  Will force the release of a machine. If the machine was deployed as a KVM host, this will be deleted as well as all machines inside the KVM host. USE WITH CAUTION. 

#### Command-line options
| Option | Effect |
|-----|-----|
| --help, -h | Show this help message and exit. |
| -d, --debug | Display more information about API responses. |
| -k, --insecure | Disable SSL certificate check |

## Enter rescue mode

```bash
maas $PROFILE machine rescue-mode [--help] [-d] [-k] system_id [data ...]
```

#### Positional arguments
- system_id

Begins the rescue mode process on a machine with the given system_id.

A machine in the 'deployed' or 'broken' state may initiate the rescue mode process.

#### Command-line options
| Option | Effect |
|-----|-----|
| --help, -h | Show this help message and exit. |
| -d, --debug | Display more information about API responses. |
| -k, --insecure | Disable SSL certificate check |

## [data ...]

```bash
maas $PROFILE machine restore-default-configuration [--help] [-d] [-k] system_id
```

Restore default configuration 

#### Positional arguments
- system_id

Restores the default configuration options on a machine with the given system_id.

#### Command-line options
| Option | Effect |
|-----|-----|
| --help, -h | Show this help message and exit. |
| -d, --debug | Display more information about API responses. |
| -k, --insecure | Disable SSL certificate check |

## Restore networking options

```bash
maas $PROFILE machine restore-networking-configuration [--help] [-d] [-k] system_id [data ...]
```

#### Positional arguments
- system_id

Restores networking options to their initial state on a machine with the given system_id.

#### Command-line options
| Option | Effect |
|-----|-----|
| --help, -h | Show this help message and exit. |
| -d, --debug | Display more information about API responses. |
| -k, --insecure | Disable SSL certificate check |

## [data ...]

```bash
maas $PROFILE machine restore-storage-configuration [--help] [-d] [-k] system_id
```

Restore storage configuration 

#### Positional arguments
- system_id

Restores storage configuration options to their initial state on a machine with the given system_id.

#### Command-line options
| Option | Effect |
|-----|-----|
| --help, -h | Show this help message and exit. |
| -d, --debug | Display more information about API responses. |
| -k, --insecure | Disable SSL certificate check |

## Deprecated, use set-workload-annotations.

```bash
maas $PROFILE machine set-owner-data [--help] [-d] [-k] system_id [data ...]
```

#### Positional arguments
- system_id

Deprecated, use set-workload-annotations instead.

#### Command-line options
| Option | Effect |
|-----|-----|
| --help, -h | Show this help message and exit. |
| -d, --debug | Display more information about API responses. |
| -k, --insecure | Disable SSL certificate check |

## Change storage layout

```bash
maas $PROFILE machine set-storage-layout [--help] [-d] [-k] system_id [data ...]
```

#### Positional arguments
- system_id


Changes the storage layout on machine with the given system_id.

This operation can only be performed on a machine with a status of 'Ready'.

Note: This will clear the current storage layout and any extra configuration and replace it will the new layout.

#### Keyword "storage_layout"
Required String.  Storage layout for the machine: ``flat``, ``lvm``, ``bcache``, ``vmfs6``, ``vmfs7``, ``custom`` or ``blank``.

#### Keyword "boot_size"
Optional String. Size of the boot partition (e.g. 512M, 1G).

#### Keyword "root_size"
Optional String. Size of the root partition (e.g. 24G).

#### Keyword "root_device"
Optional String. Physical block device to place the root partition (e.g. /dev/sda).

#### Keyword "vg_name"
Optional String. LVM only. Name of created volume group.

#### Keyword "lv_name"
Optional String. LVM only. Name of created logical volume.

#### Keyword "lv_size"
Optional String. LVM only.  Size of created logical volume.

#### Keyword "cache_device"
Optional String. Bcache only. Physical block device to use as the cache device (e.g. /dev/sda).

#### Keyword "cache_mode"
Optional String. Bcache only. Cache mode for bcache device: ``writeback``, ``writethrough``, ``writearound``.

#### Keyword "cache_size"
Optional String. Bcache only. Size of the cache partition to create on the cache device (e.g. 48G).

#### Keyword "cache_no_part"
Optional Boolean.  Bcache only. Don't create a partition on the cache device.  Use the entire disk as the cache device.

#### Command-line options
| Option | Effect |
|-----|-----|
| --help, -h | Show this help message and exit. |
| -d, --debug | Display more information about API responses. |
| -k, --insecure | Disable SSL certificate check |

## Set key=value data

```bash
maas $PROFILE machine set-workload-annotations [--help] [-d] [-k] system_id [data ...]
```

#### Positional arguments
- system_id


Set key=value data for the current owner.

Pass any key=value form data to this method to add, modify, or remove. A key is removed when the value for that key is set to an empty string.

This operation will not remove any previous keys unless explicitly passed with an empty string. All workload annotations are removed when the machine is no longer allocated to a user.

#### Keyword "key"
Required String. ``key`` can be any string value.

#### Command-line options
| Option | Effect |
|-----|-----|
| --help, -h | Show this help message and exit. |
| -d, --debug | Display more information about API responses. |
| -k, --insecure | Disable SSL certificate check |

## Begin testing process for a node

```bash
maas $PROFILE machine test [--help] [-d] [-k] system_id [data ...] 
```

#### Positional arguments
- system_id


Begins the testing process for a given node.

A node in the 'ready', 'allocated', 'deployed', 'broken', or any failed state may run tests. If testing is started and successfully passes from 'broken' or any failed state besides 'failed commissioning' the node will be returned to a ready state. Otherwise the node will return to the state it was when testing started.

#### Keyword "enable_ssh"
Optional Int.  Whether to enable SSH for the testing environment using the user's SSH key(s). 0 == false. 1 == true.
Type: Int.

#### Keyword "testing_scripts"
Optional String.  A comma-separated list of testing script names and tags to be run. By default all tests tagged 'commissioning' will be run.

#### Keyword "parameters"
Optional String.  Scripts selected to run may define their own parameters. These parameters may be passed using the parameter name. Optionally a parameter may have the script name prepended to have that parameter only apply to that specific script.

#### Command-line options
| Option | Effect |
|-----|-----|
| --help, -h | Show this help message and exit. |
| -d, --debug | Display more information about API responses. |
| -k, --insecure | Disable SSL certificate check |

## Unlock a machine

```bash
maas $PROFILE machine unlock [--help] [-d] [-k] system_id [data ...] 
```

#### Positional arguments
- system_id

Mark a machine with the given system_id as 'Unlocked' to allow changes.

#### Keyword "comment"
Optional String. Optional comment for the event log.

#### Command-line options
| Option | Effect |
|-----|-----|
| --help, -h | Show this help message and exit. |
| -d, --debug | Display more information about API responses. |
| -k, --insecure | Disable SSL certificate check |

## Unmount a special-purpose filesystem

```bash
maas $PROFILE machine unmount-special [--help] [-d] [-k] system_id [data ...]
```

#### Positional arguments
- system_id

Unmount a special-purpose filesystem, like tmpfs, on a machine with the given system_id.

#### Keyword "mount_point"
Required String. Path on the filesystem to unmount.

#### Command-line options
| Option | Effect |
|-----|-----|
| --help, -h | Show this help message and exit. |
| -d, --debug | Display more information about API responses. |
| -k, --insecure | Disable SSL certificate check |

## Update a machine

```bash
maas $PROFILE machine update [--help] [-d] [-k] system_id [data ...] 
```

#### Positional arguments
- system_id


Updates a machine with the given system_id.

#### Keyword "hostname"
Optional String. The new hostname for this machine.

#### Keyword "description"
Optional String. The new description for this machine.

#### Keyword "domain"
Optional String. The domain for this machine. If not given the default domain is used.

#### Keyword "architecture"
Optional String. The new architecture for this machine.

#### Keyword "min_hwe_kernel"
Optional String. A string containing the minimum kernel version allowed to be ran on this machine.

#### Keyword "power_type"
Optional String.  The new power type for this machine. If you use the default value, power_parameters will be set to the empty string.  Available to admin users.  See the `Power types`_ section for a list of the available power types.

#### Keyword "power_parameters_skip_check"
Optional Boolean. Whether or not the new power parameters for this machine should be checked against the expected power parameters for the machine's power type ('true' or 'false').  The default is 'false'. 

#### Keyword "pool"
Optional String.  The resource pool to which the machine should belong. All machines belong to the 'default' resource pool if they do not belong to any other resource pool.

#### Keyword "zone"
Optional String. Name of a valid physical zone in which to place this machine.

#### Keyword "swap_size"
Optional String.  Specifies the size of the swap file, in bytes. Field accept K, M, G and T suffixes for values expressed respectively in kilobytes, megabytes, gigabytes and terabytes.

#### Keyword "disable_ipv4"
Optional Boolean.  Deprecated. If specified, must be false.

#### Keyword "cpu_count"
Optional Int. The amount of CPU cores the machine has.

#### Keyword "memory"
Optional String.  How much memory the machine has.  Field accept K, M, G and T suffixes for values expressed respectively in kilobytes, megabytes, gigabytes and terabytes.

#### Command-line options
| Option | Effect |
|-----|-----|
| --help, -h | Show this help message and exit. |
| -d, --debug | Display more information about API responses. |
| -k, --insecure | Disable SSL certificate check |

## Accept all declared machines

```bash
maas $PROFILE machines accept-all [--help] [-d] [-k] [data ...] 
```

Accept all declared machines into MAAS.  Machines can be enlisted in the MAAS anonymously or by non-admin users, as opposed to by an admin.  These machines are held in the New state; a MAAS admin must first verify the authenticity of these enlistments, and accept them.

#### Command-line options
| Option | Effect |
|-----|-----|
| --help, -h | Show this help message and exit. |
| -d, --debug | Display more information about API responses. |
| -k, --insecure | Disable SSL certificate check |

## Add special hardware

```bash
maas $PROFILE machines add-chassis [--help] [-d] [-k] [data ...] 
```

Add special hardware types.

#### Keyword "chassis_type"
Required String.  The type of hardware:

- ``hmcz``: IBM Hardware Management Console (HMC) for Z
- ``mscm``: Moonshot Chassis Manager.
- ``msftocs``: Microsoft OCS Chassis Manager.
- ``powerkvm``: Virtual Machines on Power KVM, managed by Virsh.
- ``proxmox``: Virtual Machines managed by Proxmox
- ``recs_box``: Christmann RECS|Box servers.
- ``sm15k``: Seamicro 1500 Chassis.
- ``ucsm``: Cisco UCS Manager.
- ``virsh``: virtual machines managed by Virsh.
- ``vmware`` is the type for virtual machines managed by VMware.

#### Keyword "hostname"
Required String. The URL, hostname, or IP address to access the chassis.

#### Keyword "username"
Optional String.  The username used to access the chassis. This field is required for the recs_box, seamicro15k, vmware, mscm, msftocs, ucsm, and hmcz chassis types.

#### Keyword "password"
Optional String.  The password used to access the chassis. This field is required for the ``recs_box``, ``seamicro15k``, ``vmware``, ``mscm``, ``msftocs``, ``ucsm``, and ``hmcz`` chassis types.

#### Keyword "accept_all"
Optional String. If true, all enlisted machines will be commissioned.

#### Keyword "rack_controller"
Optional String.  The system_id of the rack controller to send the add chassis command through. If none is specifed MAAS will automatically determine the rack controller to use.

#### Keyword "domain"
Optional String. The domain that each new machine added should use.

#### Keyword "prefix_filter"
Optional String.  (``virsh``, ``vmware``, ``powerkvm``, ``proxmox``, ``hmcz`` only.) Filter machines with supplied prefix.

#### Keyword "power_control"
Optional String.  (``seamicro15k`` only) The power_control to use, either ipmi (default), restapi, or restapi2. 

The following are optional if you are adding a proxmox chassis.

#### Keyword "token_name"
Optional String. The name the authentication token to be used instead of a password.

#### Keyword "token_secret"
Optional String.  The token secret to be used in combination with the power_token_name used in place of a password.

#### Keyword "verify_ssl"
Optional Boolean.  Whether SSL connections should be verified.

The following are optional if you are adding a recs_box, vmware or msftocs chassis.

#### Keyword "port"
Optional Int.  (``recs_box``, ``vmware``, ``msftocs`` only) The port to use when accessing the chassis.

The following are optional if you are adding a vmware chassis.

#### Keyword "protocol"
Optional String.  (``vmware`` only) The protocol to use when accessing the VMware chassis (default: https).

#### Keyword "return" 
Optional String. A string containing the chassis powered on by which rack
controller.

#### Command-line options
| Option | Effect |
|-----|-----|
| --help, -h | Show this help message and exit. |
| -d, --debug | Display more information about API responses. |
| -k, --insecure | Disable SSL certificate check |

## Allocate a machine

```bash
maas $PROFILE machines allocate [--help] [-d] [-k] [data ...] 
```

Allocates an available machine for deployment.  Constraints parameters can be used to allocate a machine that possesses certain characteristics.  All the constraints are optional and when multiple constraints are provided, they are combined using 'AND' semantics.

#### Keyword "name"
Optional String.  Hostname or FQDN of the desired machine. If a FQDN is specified, both the domain and the hostname portions must match.

#### Keyword "system_id"
Optional String. system_id of the desired machine.

#### Keyword "arch"
Optional String..  Architecture of the returned machine (e.g. 'i386/generic', 'amd64', 'armhf/highbank', etc.). If multiple architectures are specified, the machine to acquire may match any of the given architectures. To request multiple architectures, this parameter must be repeated in the request with each value.

#### Keyword "cpu_count"
Optional Int  Minimum number of CPUs a returned machine must have. A machine with additional CPUs may be allocated if there is no exact match, or if the 'mem' constraint is not also specified.

#### Keyword "mem"
Optional Int.  The minimum amount of memory (expressed in MB) the returned machine must have. A machine with additional memory may be allocated if there is no exact match, or the 'cpu_count' constraint is not also specified.

#### Keyword "tags"
Optional String.  Tags the machine must match in order to be acquired.  If multiple tag names are specified, the machine must be tagged with all of them. To request multiple tags, this parameter must be repeated in the request with each value.

#### Keyword "not_tags"
Optional String.  Tags the machine must NOT match. If multiple tag names are specified, the machine must NOT be tagged with ANY of them. To request exclusion of multiple tags, this parameter must be repeated in the request with each value.

#### Keyword "zone"
Optional String. Physical zone name the machine must be located in.

#### Keyword "not_in_zone"
Optional String.  List of physical zones from which the machine must not be acquired.  If multiple zones are specified, the machine must NOT be associated with ANY of them. To request multiple zones to exclude, this parameter must be repeated in the request with each value.

#### Keyword "pool"
Optional String. Resource pool name the machine must belong to.

#### Keyword "not_in_pool"
Optional String.  List of resource pool from which the machine must not be acquired. If multiple pools are specified, the machine must NOT be associated with ANY of them. To request multiple pools to exclude, this parameter must be repeated in the request with each value.

#### Keyword "pod"
Optional String. Pod the machine must be located in.

#### Keyword "not_pod"
Optional String. Pod the machine must not be located in.

#### Keyword "pod_type"
Optional String. Pod type the machine must be located in.

#### Keyword "not_pod_type"
Optional String. Pod type the machine must not be located in.

#### Keyword "subnets"
Optional String.  Subnets that must be linked to the machine.

"Linked to" means the node must be configured to acquire an address in the specified subnet, have a static IP address in the specified subnet, or have been observed to DHCP from the specified subnet during commissioning time (which implies that it *could* have an address on the specified subnet).

Subnets can be specified by one of the following criteria:

- <id>: Match the subnet by its 'id' field
- fabric:<fabric-spec>: Match all subnets in a given fabric.
- ip:<ip-address>: Match the subnet containing <ip-address> with the
  with the longest-prefix match.
- name:<subnet-name>: Match a subnet with the given name.
- space:<space-spec>: Match all subnets in a given space.
- vid:<vid-integer>: Match a subnet on a VLAN with the specified VID.
  Valid values range from 0 through 4094 (inclusive). An untagged VLAN
  can be specified by using the value "0".
- vlan:<vlan-spec>: Match all subnets on the given VLAN.

Note that (as of this writing), the 'fabric', 'space', 'vid', and 'vlan' specifiers are only useful for the 'not_spaces' version of this constraint, because they will most likely force the query to match ALL the subnets in each fabric, space, or VLAN, and thus not return any nodes. (This is not a particularly useful behavior, so may be changed in the future.)

If multiple subnets are specified, the machine must be associated with all of them. To request multiple subnets, this parameter must be repeated in the request with each value.

Note that this replaces the legacy 'networks' constraint in MAAS 1.x.

#### Keyword "not_subnets"
Optional String.  Subnets that must NOT be linked to the machine.

See the 'subnets' constraint documentation above for more information about how each subnet can be specified.

If multiple subnets are specified, the machine must NOT be associated with ANY of them. To request multiple subnets to exclude, this parameter must be repeated in the request with each value. (Or a fabric, space, or VLAN specifier may be used to match multiple subnets).

Note that this replaces the legacy 'not_networks' constraint in MAAS 1.x.

#### Keyword "storage"
Optional String. A list of storage constraint identifiers, in the form: ``label:size(tag[,tag[,...])][,label:...]``.

#### Keyword "interfaces"
Optional String.  A labeled constraint map associating constraint labels with interface properties that should be matched. Returned nodes must have one or more interface matching the specified constraints. The labeled constraint map must be in the format: ``label:key=value[,key2=value2[,...]]``.

Each key can be one of the following:

- ``id``: Matches an interface with the specific id
- ``fabric``: Matches an interface attached to the specified fabric.
- ``fabric_class``: Matches an interface attached to a fabric with the specified class.
- ``ip``: Matches an interface with the specified IP address assigned to it.
- ``mode``: Matches an interface with the specified mode. (Currently, the only supported mode is "unconfigured".)
- ``name``: Matches an interface with the specified name.  (For example, "eth0".)
- ``hostname``: Matches an interface attached to the node with the specified hostname.
- ``subnet``: Matches an interface attached to the specified subnet.
- ``space``: Matches an interface attached to the specified space.
- ``subnet_cidr``: Matches an interface attached to the specified subnet CIDR. (For example, "192.168.0.0/24".)
- ``type``: Matches an interface of the specified type. (Valid types: "physical", "vlan", "bond", "bridge", or "unknown".)
- ``vlan``: Matches an interface on the specified VLAN.
- ``vid``: Matches an interface on a VLAN with the specified VID.
- ``tag``: Matches an interface tagged with the specified tag.
- ``link_speed``: Matches an interface with link_speed equal to or greater than the specified speed.

#### Keyword "fabrics"
Optional String.  Set of fabrics that the machine must be associated with in order to be acquired. If multiple fabrics names are specified, the machine can be in any of the specified fabrics. To request multiple possible fabrics to match, this parameter must be repeated in the request with each value.

#### Keyword "not_fabrics"
Optional String.  Fabrics the machine must NOT be associated with in order to be acquired. If multiple fabrics names are specified, the machine must NOT be in ANY of them. To request exclusion of multiple fabrics, this parameter must be repeated in the request with each value.

#### Keyword "fabric_classes"
Optional String.  Set of fabric class types whose fabrics the machine must be associated with in order to be acquired. If multiple fabrics class types are specified, the machine can be in any matching fabric. To request multiple possible fabrics class types to match, this parameter must be repeated in the request with each value.

#### Keyword "not_fabric_classes"
Optional String.  Fabric class types whose fabrics the machine must NOT be associated with in order to be acquired. If multiple fabrics names are specified, the machine must NOT be in ANY of them. To request exclusion of multiple fabrics, this parameter must be repeated in the request with each value.

#### Keyword "agent_name"
Optional String. An optional agent name to attach to the acquired machine.

#### Keyword "comment"
Optional String. Comment for the event log.

#### Keyword "bridge_all"
Optional Boolean.  Optionally create a bridge interface for every configured interface on the machine. The created bridges will be removed once the machine is released. (Default: False)

#### Keyword "bridge_stp"
Optional Boolean.  Optionally turn spanning tree protocol on or off for the bridges created on every configured interface.  (Default: off)

#### Keyword "bridge_fd"
Optional Int. Optionally adjust the forward delay to time seconds.  (Default: 15)

#### Keyword "devices"
Optional String.  Only return a node which have one or more devices containing the following constraints in the format `key=value[,key2=value2[,...]]`.

Each key can be one of the following:

- ``vendor_id``: The device vendor id
- ``product_id``: The device product id
- ``vendor_name``: The device vendor name, not case sensative
- ``product_name``: The device product name, not case sensative
- ``commissioning_driver``: The device uses this driver during   commissioning.

#### Keyword "dry_run"
Optional Boolean.  Optional boolean to indicate that the machine should not actually be acquired (this is for support/troubleshooting, or users who want to see which machine would match a constraint, without acquiring a machine). Defaults to False.

#### Keyword "verbose"
Optional Boolean.  Optional boolean to indicate that the user would like additional verbosity in the constraints_by_type field (each constraint will be prefixed by ``verbose_``, and contain the full data structure that indicates which machine(s) matched).

#### Command-line options
| Option | Effect |
|-----|-----|
| --help, -h | Show this help message and exit. |
| -d, --debug | Display more information about API responses. |
| -k, --insecure | Disable SSL certificate check |

## Clone storage and/or interface configurations

```bash
maas $PROFILE machines clone [--help] [-d] [-k] [data ...] 
```

Clone storage and/or interface configurations. A machine storage and/or interface configuration can be cloned to a set of destination machines.

For storage configuration, cloning the destination machine must have at least the same number of physical block devices or more, along with the physical block devices being the same size or greater.

For interface configuration, cloning the destination machine must have at least the same number of interfaces with the same names. The destination machine can have more interfaces than the source, as long as the subset of interfaces on the destination have the same matching names as the source.

#### Keyword "source"
Required String. The system_id of the machine that is the source of the configuration.

#### Keyword "destinations"
Required String. A list of system_ids to clone the configuration to.

#### Keyword "interfaces"
Required Boolean. Whether to clone interface configuration. Defaults to False.

#### Keyword "storage"
Required Boolean. Whether to clone storage configuration. Defaults to False.

#### Command-line options
| Option | Effect |
|-----|-----|
| --help, -h | Show this help message and exit. |
| -d, --debug | Display more information about API responses. |
| -k, --insecure | Disable SSL certificate check |

## Create a new machine

```bash
maas $PROFILE machines create [--help] [-d] [-k] [data ...] 
```

Create a new machine.  Adding a server to MAAS will (by default) cause the machine to network boot into an ephemeral environment to collect hardware information.

In anonymous enlistment (and when the enlistment is done by a non-admin), the machine is held in the "New" state for approval by a MAAS admin.

The minimum data required is:

- architecture=<arch string> (e.g. "i386/generic")
- mac_addresses=<value> (e.g. "aa:bb:cc:dd:ee:ff")

#### Keyword "architecture"
Required String. unicode. A string containing the architecture type of the machine. (For example, "i386", or "amd64".) To

#### Keyword "min_hwe_kernel"
Optional String. A string containing the minimum kernel version allowed to be ran on this machine.

#### Keyword "subarchitecture"
Optional String.  A string containing the subarchitecture type of the machine. (For example, "generic" or "hwe-t".) To determine the supported subarchitectures, use the boot-resources endpoint.

#### Keyword "mac_addresses"
Required String.  One or more MAC addresses for the machine. To specify more than one MAC address, the parameter must be specified twice. (such as "machines new mac_addresses=01:02:03:04:05:06 mac_addresses=02:03:04:05:06:07")

#### Keyword "hostname"
Optional String. A hostname. If not given, one will be generated.

#### Keyword "description"
Optional String. A optional description.

#### Keyword "domain"
Optional String. The domain of the machine. If not given the default domain is used.

#### Keyword "power_type"
Optional String. A power management type, if applicable (e.g.  "virsh", "ipmi").

#### Keyword "commission"
Optional Boolean.  Request the newly created machine to be created with status set to COMMISSIONING. Machines will wait for COMMISSIONING results and not time out. Machines created by administrators will be commissioned unless set to false.

#### Keyword "deployed"
Optional Boolean.  Request the newly created machine to be created with status set to DEPLOYED. Setting this to true implies commissioning=false, meaning that the machine won't go through the commissioning process.

#### Keyword "enable_ssh"
Optional Int. Whether to enable SSH for the commissioning environment using the user's SSH key(s). '1' == True, '0' == False.

#### Keyword "skip_bmc_config"
Optional Int.  Whether to skip re-configuration of the BMC for IPMI based machines. '1' == True, '0' == False.

#### Keyword "skip_networking"
Optional Int.  Whether to skip re-configuring the networking on the machine after the commissioning has completed. '1' == True, '0' == False.

#### Keyword "skip_storage"
Optional Int.  Whether to skip re-configuring the storage on the machine after the commissioning has completed. '1' == True, '0' == False.

#### Keyword "commissioning_scripts"
Optional String.  A comma separated list of commissioning script names and tags to be run. By default all custom commissioning scripts are run. Built-in commissioning scripts always run. Selecting 'update_firmware' or 'configure_hba' will run firmware updates or configure HBA's on matching machines.

#### Keyword "testing_scripts"
Optional.  A comma separated list of testing script names and tags to be run. By default all tests tagged 'commissioning' will be run. Set to 'none' to disable running tests.

#### Command-line options
| Option | Effect |
|-----|-----|
| --help, -h | Show this help message and exit. |
| -d, --debug | Display more information about API responses. |
| -k, --insecure | Disable SSL certificate check |

## MAC address registered

```bash
maas $PROFILE machines is-registered [--help] [-d] [-k] [data ...] 
```

Returns whether or not the given MAC address is registered within this MAAS (and attached to a non-retired node).

#### Keyword "mac_address"
Required URL String. The MAC address to be checked.

#### Command-line options
| Option | Effect |
|-----|-----|
| --help, -h | Show this help message and exit. |
| -d, --debug | Display more information about API responses. |
| -k, --insecure | Disable SSL certificate check |

## List allocated

```bash
maas $PROFILE machines list-allocated [--help] [-d] [-k] [data ...] 
```

List machines that were allocated to the User. 

#### Command-line options
| Option | Effect |
|-----|-----|
| --help, -h | Show this help message and exit. |
| -d, --debug | Display more information about API responses. |
| -k, --insecure | Disable SSL certificate check |

## Get power parameters

```bash
maas $PROFILE machines power-parameters [--help] [-d] [-k] [data ...] 
```

Get power parameters for multiple machines. To request power parameters for a specific machine or more than one machine:
``op=power_parameters&id=abc123&id=def456``.

#### Keyword "id"
Required URL String.  A system ID. To request more than one machine, provide multiple ``id`` arguments in the request. Only machines with matching system ids will be returned.

#### Command-line options
| Option | Effect |
|-----|-----|
| --help, -h | Show this help message and exit. |
| -d, --debug | Display more information about API responses. |
| -k, --insecure | Disable SSL certificate check |

## List Nodes visible to the user

```bash
maas $PROFILE machines read [--help] [-d] [-k] [data ...] 
```

List nodes visible to current user, optionally filtered by criteria.

Nodes are sorted by id (i.e. most recent last) and grouped by type.

#### Keyword "hostname"
Optional String.  Only nodes relating to the node with the matching hostname will be returned. This can be specified multiple times to see multiple nodes.

#### Keyword "cpu_count"
Optional Int. Only nodes with the specified minimum number of CPUs will be included.

#### Keyword "mem"
Optional String. Only nodes with the specified minimum amount of RAM (in MiB) will be included.

#### Keyword "mac_address"
Optional String.  Only nodes relating to the node owning the specified MAC address will be returned. This can be specified multiple times to see multiple nodes.

#### Keyword "id"
Optional String. Only nodes relating to the nodes with matching system ids will be returned.

#### Keyword "domain"
Optional String. Only nodes relating to the nodes in the domain will be returned.

#### Keyword "zone"
Optional String. Only nodes relating to the nodes in the zone will be returned.

#### Keyword "pool"
Optional String. Only nodes belonging to the pool will be returned.

#### Keyword "agent_name"
Optional String. Only nodes relating to the nodes with matching agent names will be returned.

#### Keyword "fabrics"
Optional String. Only nodes with interfaces in specified fabrics will be returned.

#### Keyword "not_fabrics"
Optional String. Only nodes with interfaces not in specified fabrics will be returned.

#### Keyword "vlans"
Optional String. Only nodes with interfaces in specified VLANs will be returned.

#### Keyword "not_vlans"
Optional String. Only nodes with interfaces not in specified VLANs will be returned.

#### Keyword "subnets"
Optional String. Only nodes with interfaces in specified subnets will be returned.

#### Keyword "not_subnets"
Optional String. Only nodes with interfaces not in specified subnets will be returned.

#### Keyword "link_speed"
Optional String.  Only nodes with interfaces with link speeds greater than or equal to link_speed will be returned.

#### Keyword "status"
Optional String. Only nodes with specified status will be returned.

#### Keyword "pod"
Optional String. Only nodes that belong to a specified pod will be returned.

#### Keyword "not_pod"
Optional String. Only nodes that don't belong to a specified pod will be returned.

#### Keyword "pod_type"
Optional String. Only nodes that belong to a pod of the specified type will be returned.

#### Keyword "not_pod_type"
Optional String. Only nodes that don't belong a pod of the specified type will be returned.

#### Keyword "devices"
Optional String.  Only return nodes which have one or more devices containing the following constraints in the format `key=value[,key2=value2[,...]]`.

Each key can be one of the following:

- ``vendor_id``: The device vendor id
- ``product_id``: The device product id
- ``vendor_name``: The device vendor name, not case sensative
- ``product_name``: The device product name, not case sensative
- ``commissioning_driver``: The device uses this driver during   commissioning.

#### Command-line options
| Option | Effect |
|-----|-----|
| --help, -h | Show this help message and exit. |
| -d, --debug | Display more information about API responses. |
| -k, --insecure | Disable SSL certificate check |

## Release machines

```bash
maas $PROFILE machines release [--help] [-d] [-k] [data ...] 
```

Release multiple machines. Places the machines back into the pool, ready to be reallocated.

#### Keyword "machines"
Required String. A list of system_ids of the machines which are to be released.  (An empty list is acceptable).

#### Keyword "comment"
Optional String. Optional comment for the event log.

#### Command-line options
| Option | Effect |
|-----|-----|
| --help, -h | Show this help message and exit. |
| -d, --debug | Display more information about API responses. |
| -k, --insecure | Disable SSL certificate check |

## Assign nodes to a zone

```bash
maas $PROFILE machines set-zone [--help] [-d] [-k] [data ...] 
```

Assigns a given node to a given zone.

#### Keyword "zone"
Required String. The zone name.

#### Keyword "nodes"
Required String. The node to add.

#### Command-line options
| Option | Effect |
|-----|-----|
| --help, -h | Show this help message and exit. |
| -d, --debug | Display more information about API responses. |
| -k, --insecure | Disable SSL certificate check |

