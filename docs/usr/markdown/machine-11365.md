Abort a node operation

```bash
maas $PROFILE machine abort [--help] [-d] [-k] system_id [data ...]

```

#### **Positional arguments**
| Argument | Effect |
|---|---|
| system_id | The system ID of the machine/device (e.g., `abc123`) |


#### **Command-line options**
| Option | Effect |
|---|---|
| --help, -h | Show this help message and exit. |
| -d, --debug | Display more information about API responses. |
| -k, --insecure | Disable SSL certificate check. |


#### **Keywords**
Abort a node's current operation.

##### Keyword "comment"
Optional String. Comment for the event log.


Note: This command accepts JSON.


Clear set default gateways

```bash
maas $PROFILE machine clear-default-gateways [--help] [-d] [-k] system_id

```

#### **Positional arguments**
| Argument | Effect |
|---|---|
| system_id | The system ID of the machine/device (e.g., `abc123`) |


#### **Command-line options**
| Option | Effect |
|---|---|
| --help, -h | Show this help message and exit. |
| -d, --debug | Display more information about API responses. |
| -k, --insecure | Disable SSL certificate check. |


#### **Keywords**
Clear any set default gateways on a machine with the given<br>system_id. This will clear both IPv4 and IPv6 gateways on the machine. This will<br>transition the logic of identifying the best gateway to MAAS. This logic<br>is determined based the following criteria:<br><br>1. Managed subnets over unmanaged subnets.<br>2. Bond interfaces over physical interfaces.<br>3. Machine's boot interface over all other interfaces except bonds.<br>4. Physical interfaces over VLAN interfaces.<br>5. Sticky IP links over user reserved IP links.<br>6. User reserved IP links over auto IP links. If the default gateways need to be specific for this machine you can<br>set which interface and subnet's gateway to use when this machine is<br>deployed with the `interfaces set-default-gateway` API.





Commission a machine

```bash
maas $PROFILE machine commission [--help] [-d] [-k] system_id [data ...]

```

#### **Positional arguments**
| Argument | Effect |
|---|---|
| system_id | The system ID of the machine/device (e.g., `abc123`) |


#### **Command-line options**
| Option | Effect |
|---|---|
| --help, -h | Show this help message and exit. |
| -d, --debug | Display more information about API responses. |
| -k, --insecure | Disable SSL certificate check. |


#### **Keywords**
Begin commissioning process for a machine. A machine in the 'ready', 'declared' or 'failed test' state may<br>initiate a commissioning cycle where it is checked out and tested in<br>preparation for transitioning to the 'ready' state. If it is already in<br>the 'ready' state this is considered a re-commissioning process which<br>is useful if commissioning tests were changed after it previously<br>commissioned.

##### Keyword "enable_ssh"
Optional Int. Whether to enable SSH for<br>the commissioning environment using the user's SSH key(s). '1' == True,<br>'0' == False.
##### Keyword "skip_bmc_config"
Optional Int. Whether to skip<br>re-configuration of the BMC for IPMI based machines. '1' == True, '0'<br>== False.
##### Keyword "skip_networking"
Optional Int. Whether to skip<br>re-configuring the networking on the machine after the commissioning<br>has completed. '1' == True, '0' == False.
##### Keyword "skip_storage"
Optional Int. Whether to skip<br>re-configuring the storage on the machine after the commissioning has<br>completed. '1' == True, '0' == False.
##### Keyword "commissioning_scripts"
Optional String. A comma<br>separated list of commissioning script names and tags to be run. By<br>default all custom commissioning scripts are run. Built-in<br>commissioning scripts always run. Selecting 'update_firmware' or<br>'configure_hba' will run firmware updates or configure HBA's on<br>matching machines.
##### Keyword "testing_scripts"
Optional String. A comma separated<br>list of testing script names and tags to be run. By default all tests<br>tagged 'commissioning' will be run. Set to 'none' to disable running<br>tests.
##### Keyword "parameters"
Optional String. Scripts selected to run<br>may define their own parameters. These parameters may be passed using<br>the parameter name. Optionally a parameter may have the script name<br>prepended to have that parameter only apply to that specific script.


Note: This command accepts JSON.


Delete a machine

```bash
maas $PROFILE machine delete [--help] [-d] [-k] system_id

```

#### **Positional arguments**
| Argument | Effect |
|---|---|
| system_id | The system ID of the machine/device (e.g., `abc123`) |


#### **Command-line options**
| Option | Effect |
|---|---|
| --help, -h | Show this help message and exit. |
| -d, --debug | Display more information about API responses. |
| -k, --insecure | Disable SSL certificate check. |


#### **Keywords**
Deletes a machine with the given system_id. Note: A machine cannot be deleted if it hosts pod virtual machines.<br>Use ``force`` to override this behavior. Forcing deletion will also<br>remove hosted pods. E.g. ``/machines/abc123/?force=1``.





Deploy a machine

```bash
maas $PROFILE machine deploy [--help] [-d] [-k] system_id [data ...]

```

#### **Positional arguments**
| Argument | Effect |
|---|---|
| system_id | The system ID of the machine/device (e.g., `abc123`) |


#### **Command-line options**
| Option | Effect |
|---|---|
| --help, -h | Show this help message and exit. |
| -d, --debug | Display more information about API responses. |
| -k, --insecure | Disable SSL certificate check. |


#### **Keywords**
Deploys an operating system to a machine with the given<br>system_id.

##### Keyword "user_data"
Optional String. If present, this blob of<br>base64-encoded user-data to be made available to the machines through<br>the metadata service.
##### Keyword "distro_series"
Optional String. If present, this<br>parameter specifies the OS release the machine will use. For example<br>valid values to deploy Jammy Jellyfish are ``ubuntu/jammy``, ``jammy`` and<br>``ubuntu/22.04``, ``22.04``.
##### Keyword "hwe_kernel"
Optional String. If present, this<br>parameter specified the kernel to be used on the machine
##### Keyword "agent_name"
Optional String. An optional agent name to<br>attach to the acquired machine.
##### Keyword "bridge_all"
Optional Boolean. Optionally create a<br>bridge interface for every configured interface on the machine. The<br>created bridges will be removed once the machine is released.<br>(Default: false)
##### Keyword "bridge_type"
Optional String. Optionally create the<br>bridges with this type. Possible values are: ``standard``, ``ovs``.
##### Keyword "bridge_stp"
Optional Boolean. Optionally turn spanning<br>tree protocol on or off for the bridges created on every configured<br>interface. (Default: false)
##### Keyword "bridge_fd"
Optional Int. Optionally adjust the forward<br>delay to time seconds. (Default: 15)
##### Keyword "comment"
Optional String. comment for the<br>event log.
##### Keyword "install_rackd"
Optional Boolean. If true, the rack<br>controller will be installed on this machine.
##### Keyword "install_kvm"
Optional Boolean. If true, KVM will be<br>installed on this machine and added to MAAS.
##### Keyword "register_vmhost"
Optional Boolean. If true, the<br>machine will be registered as a LXD VM host in MAAS.
##### Keyword "ephemeral_deploy"
Optional Boolean. If true, machine<br>will be deployed ephemerally even if it has disks.
##### Keyword "enable_kernel_crash_dump"
Optional Boolean. If true, machine<br>will be deployed with the kernel crash dump feature enabled and configured automatically.
##### Keyword "vcenter_registration"
Optional Boolean. If false, do<br>not send globally defined VMware vCenter credentials to the machine.
##### Keyword "enable_hw_sync"
Optional Boolean. If true, machine<br>will be deployed with a small agent periodically pushing hardware data to detect<br>any change in devices.


Note: This command accepts JSON.


Get system details

```bash
maas $PROFILE machine details [--help] [-d] [-k] system_id

```

#### **Positional arguments**
| Argument | Effect |
|---|---|
| system_id | The system ID of the machine/device (e.g., `abc123`) |


#### **Command-line options**
| Option | Effect |
|---|---|
| --help, -h | Show this help message and exit. |
| -d, --debug | Display more information about API responses. |
| -k, --insecure | Disable SSL certificate check. |


#### **Keywords**
Returns system details -- for example, LLDP and<br>``lshw`` XML dumps. Returns a ``{detail_type: xml, …}`` map, where<br>``detail_type`` is something like "lldp" or "lshw". Note that this is returned as BSON and not JSON. This is for<br>efficiency, but mainly because JSON can't do binary content without<br>applying additional encoding like base-64. The example output below is<br>represented in ASCII using ``bsondump example.bson`` and is for<br>demonstrative purposes.





Exit rescue mode

```bash
maas $PROFILE machine exit-rescue-mode [--help] [-d] [-k] system_id

```

#### **Positional arguments**
| Argument | Effect |
|---|---|
| system_id | The system ID of the machine/device (e.g., `abc123`) |


#### **Command-line options**
| Option | Effect |
|---|---|
| --help, -h | Show this help message and exit. |
| -d, --debug | Display more information about API responses. |
| -k, --insecure | Disable SSL certificate check. |


#### **Keywords**
Exits the rescue mode process on a machine with the given<br>system_id. A machine in the 'rescue mode' state may exit the rescue mode<br>process.





Get curtin configuration

```bash
maas $PROFILE machine get-curtin-config [--help] [-d] [-k] system_id

```

#### **Positional arguments**
| Argument | Effect |
|---|---|
| system_id | The system ID of the machine/device (e.g., `abc123`) |


#### **Command-line options**
| Option | Effect |
|---|---|
| --help, -h | Show this help message and exit. |
| -d, --debug | Display more information about API responses. |
| -k, --insecure | Disable SSL certificate check. |


#### **Keywords**
Return the rendered curtin configuration for the machine.





Get a machine token

```bash
maas $PROFILE machine get-token [--help] [-d] [-k] system_id

```

#### **Positional arguments**
| Argument | Effect |
|---|---|
| system_id | The system ID of the machine/device (e.g., `abc123`) |


#### **Command-line options**
| Option | Effect |
|---|---|
| --help, -h | Show this help message and exit. |
| -d, --debug | Display more information about API responses. |
| -k, --insecure | Disable SSL certificate check. |






Lock a machine

```bash
maas $PROFILE machine lock [--help] [-d] [-k] system_id [data ...]

```

#### **Positional arguments**
| Argument | Effect |
|---|---|
| system_id | The system ID of the machine/device (e.g., `abc123`) |


#### **Command-line options**
| Option | Effect |
|---|---|
| --help, -h | Show this help message and exit. |
| -d, --debug | Display more information about API responses. |
| -k, --insecure | Disable SSL certificate check. |


#### **Keywords**
Mark a machine with the given system_id as 'Locked' to<br>prevent changes.

##### Keyword "comment"
Optional String. comment for the<br>event log.


Note: This command accepts JSON.


Mark a machine as Broken

```bash
maas $PROFILE machine mark-broken [--help] [-d] [-k] system_id [data ...]

```

#### **Positional arguments**
| Argument | Effect |
|---|---|
| system_id | The system ID of the machine/device (e.g., `abc123`) |


#### **Command-line options**
| Option | Effect |
|---|---|
| --help, -h | Show this help message and exit. |
| -d, --debug | Display more information about API responses. |
| -k, --insecure | Disable SSL certificate check. |


#### **Keywords**
Mark a machine with the given system_id as 'Broken'. If the node is allocated, release it first.

##### Keyword "comment"
Optional String. comment for the<br>event log. Will be displayed on the node as an error description until<br>marked fixed.


Note: This command accepts JSON.


Mark a machine as Fixed

```bash
maas $PROFILE machine mark-fixed [--help] [-d] [-k] system_id [data ...]

```

#### **Positional arguments**
| Argument | Effect |
|---|---|
| system_id | The system ID of the machine/device (e.g., `abc123`) |


#### **Command-line options**
| Option | Effect |
|---|---|
| --help, -h | Show this help message and exit. |
| -d, --debug | Display more information about API responses. |
| -k, --insecure | Disable SSL certificate check. |


#### **Keywords**
Mark a machine with the given system_id as 'Fixed'.

##### Keyword "comment"
Optional String. comment for the<br>event log.


Note: This command accepts JSON.


Mount a special-purpose filesystem

```bash
maas $PROFILE machine mount-special [--help] [-d] [-k] system_id [data ...]

```

#### **Positional arguments**
| Argument | Effect |
|---|---|
| system_id | The system ID of the machine/device (e.g., `abc123`) |


#### **Command-line options**
| Option | Effect |
|---|---|
| --help, -h | Show this help message and exit. |
| -d, --debug | Display more information about API responses. |
| -k, --insecure | Disable SSL certificate check. |


#### **Keywords**
Mount a special-purpose filesystem, like tmpfs on a<br>machine with the given system_id.

##### Keyword "fstype"
Optional String. The filesystem type. This must<br>be a filesystem that does not require a block special device.
##### Keyword "mount_point"
Optional String. Path on the filesystem to<br>mount.
##### Keyword "mount_option"
Optional String. Options to pass to<br>mount(8).


Note: This command accepts JSON.


Ignore failed tests

```bash
maas $PROFILE machine override-failed-testing [--help] [-d] [-k] system_id [data ...]

```

#### **Positional arguments**
| Argument | Effect |
|---|---|
| system_id | The system ID of the machine/device (e.g., `abc123`) |


#### **Command-line options**
| Option | Effect |
|---|---|
| --help, -h | Show this help message and exit. |
| -d, --debug | Display more information about API responses. |
| -k, --insecure | Disable SSL certificate check. |


#### **Keywords**
Ignore failed tests and put node back into a usable state.

##### Keyword "comment"
Optional String. Comment for the event log.


Note: This command accepts JSON.


Power off a node

```bash
maas $PROFILE machine power-off [--help] [-d] [-k] system_id [data ...]

```

#### **Positional arguments**
| Argument | Effect |
|---|---|
| system_id | The system ID of the machine/device (e.g., `abc123`) |


#### **Command-line options**
| Option | Effect |
|---|---|
| --help, -h | Show this help message and exit. |
| -d, --debug | Display more information about API responses. |
| -k, --insecure | Disable SSL certificate check. |


#### **Keywords**
Powers off a given node.

##### Keyword "stop_mode"
Optional String. Power-off mode. If 'soft',<br>perform a soft power down if the node's power type supports it,<br>otherwise perform a hard power off. For all values other than 'soft',<br>and by default, perform a hard power off. A soft power off generally<br>asks the OS to shutdown the system gracefully before powering off,<br>while a hard power off occurs immediately without any warning to the<br>OS.
##### Keyword "comment"
Optional String. Comment for the event log.


Note: This command accepts JSON.


Turn on a node

```bash
maas $PROFILE machine power-on [--help] [-d] [-k] system_id [data ...]

```

#### **Positional arguments**
| Argument | Effect |
|---|---|
| system_id | The system ID of the machine/device (e.g., `abc123`) |


#### **Command-line options**
| Option | Effect |
|---|---|
| --help, -h | Show this help message and exit. |
| -d, --debug | Display more information about API responses. |
| -k, --insecure | Disable SSL certificate check. |


#### **Keywords**
Turn on the given node with optional user-data and<br>comment.

##### Keyword "user_data"
Optional String. Base64-encoded blob of<br>data to be made available to the nodes through the metadata service.
##### Keyword "comment"
Optional String. Comment for the event log.


Note: This command accepts JSON.


Get power parameters

```bash
maas $PROFILE machine power-parameters [--help] [-d] [-k] system_id

```

#### **Positional arguments**
| Argument | Effect |
|---|---|
| system_id | The system ID of the machine/device (e.g., `abc123`) |


#### **Command-line options**
| Option | Effect |
|---|---|
| --help, -h | Show this help message and exit. |
| -d, --debug | Display more information about API responses. |
| -k, --insecure | Disable SSL certificate check. |


#### **Keywords**
Gets power parameters for a given system_id, if any. For<br>some types of power control this will include private information such<br>as passwords and secret keys. Note that this method is reserved for admin users and returns a 403 if<br>the user is not one.





Get the power state of a node

```bash
maas $PROFILE machine query-power-state [--help] [-d] [-k] system_id [data ...]

```

#### **Positional arguments**
| Argument | Effect |
|---|---|
| system_id | The system ID of the machine/device (e.g., `abc123`) |


#### **Command-line options**
| Option | Effect |
|---|---|
| --help, -h | Show this help message and exit. |
| -d, --debug | Display more information about API responses. |
| -k, --insecure | Disable SSL certificate check. |


#### **Keywords**
Gets the power state of a given node. MAAS sends a request<br>to the node's power controller, which asks it about the node's state.<br>The reply to this could be delayed by up to 30 seconds while waiting<br>for the power controller to respond. Use this method sparingly as it<br>ties up an appserver thread while waiting.

##### Keyword "system_id"
Optional String. The node to query.


Note: This command accepts JSON.


Read a node

```bash
maas $PROFILE machine read [--help] [-d] [-k] system_id

```

#### **Positional arguments**
| Argument | Effect |
|---|---|
| system_id | The system ID of the machine/device (e.g., `abc123`) |


#### **Command-line options**
| Option | Effect |
|---|---|
| --help, -h | Show this help message and exit. |
| -d, --debug | Display more information about API responses. |
| -k, --insecure | Disable SSL certificate check. |


#### **Keywords**
Reads a node with the given system_id.





Release a machine

```bash
maas $PROFILE machine release [--help] [-d] [-k] system_id [data ...]

```

#### **Positional arguments**
| Argument | Effect |
|---|---|
| system_id | The system ID of the machine/device (e.g., `abc123`) |


#### **Command-line options**
| Option | Effect |
|---|---|
| --help, -h | Show this help message and exit. |
| -d, --debug | Display more information about API responses. |
| -k, --insecure | Disable SSL certificate check. |


#### **Keywords**
Releases a machine with the given system_id. Note that<br>this operation is the opposite of allocating a machine. **Erasing drives**:<br><br>If neither ``secure_erase`` nor ``quick_erase`` are specified, MAAS<br>will overwrite the whole disk with null bytes. This can be slow. If both ``secure_erase`` and ``quick_erase`` are specified and the<br>drive does NOT have a secure erase feature, MAAS will behave as if only<br>``quick_erase`` was specified. If ``secure_erase`` is specified and ``quick_erase`` is NOT specified<br>and the drive does NOT have a secure erase feature, MAAS will behave as<br>if ``secure_erase`` was NOT specified, i.e. MAAS will overwrite the<br>whole disk with null bytes. This can be slow.

##### Keyword "comment"
Optional String. comment for the<br>event log.
##### Keyword "erase"
Optional Boolean. Erase the disk when<br>releasing.
##### Keyword "secure_erase"
Optional Boolean. Use the drive's secure<br>erase feature if available. In some cases, this can be much faster<br>than overwriting the drive. Some drives implement secure erasure by<br>overwriting themselves so this could still be slow.
##### Keyword "quick_erase"
Optional Boolean. Wipe 2MiB at the start<br>and at the end of the drive to make data recovery inconvenient and<br>unlikely to happen by accident. This is not secure.
##### Keyword "force"
Optional Boolean. Will force the release of a<br>machine. If the machine was deployed as a KVM host, this will be<br>deleted as well as all machines inside the KVM host. USE WITH CAUTION.


Note: This command accepts JSON.


Enter rescue mode

```bash
maas $PROFILE machine rescue-mode [--help] [-d] [-k] system_id

```

#### **Positional arguments**
| Argument | Effect |
|---|---|
| system_id | The system ID of the machine/device (e.g., `abc123`) |


#### **Command-line options**
| Option | Effect |
|---|---|
| --help, -h | Show this help message and exit. |
| -d, --debug | Display more information about API responses. |
| -k, --insecure | Disable SSL certificate check. |


#### **Keywords**
Begins the rescue mode process on a machine with the given<br>system_id. A machine in the 'deployed' or 'broken' state may initiate the<br>rescue mode process.





Restore default configuration

```bash
maas $PROFILE machine restore-default-configuration [--help] [-d] [-k] system_id

```

#### **Positional arguments**
| Argument | Effect |
|---|---|
| system_id | The system ID of the machine/device (e.g., `abc123`) |


#### **Command-line options**
| Option | Effect |
|---|---|
| --help, -h | Show this help message and exit. |
| -d, --debug | Display more information about API responses. |
| -k, --insecure | Disable SSL certificate check. |


#### **Keywords**
Restores the default configuration options on a machine<br>with the given system_id.





Restore networking options

```bash
maas $PROFILE machine restore-networking-configuration [--help] [-d] [-k] system_id

```

#### **Positional arguments**
| Argument | Effect |
|---|---|
| system_id | The system ID of the machine/device (e.g., `abc123`) |


#### **Command-line options**
| Option | Effect |
|---|---|
| --help, -h | Show this help message and exit. |
| -d, --debug | Display more information about API responses. |
| -k, --insecure | Disable SSL certificate check. |


#### **Keywords**
Restores networking options to their initial state on a<br>machine with the given system_id.





Restore storage configuration

```bash
maas $PROFILE machine restore-storage-configuration [--help] [-d] [-k] system_id

```

#### **Positional arguments**
| Argument | Effect |
|---|---|
| system_id | The system ID of the machine/device (e.g., `abc123`) |


#### **Command-line options**
| Option | Effect |
|---|---|
| --help, -h | Show this help message and exit. |
| -d, --debug | Display more information about API responses. |
| -k, --insecure | Disable SSL certificate check. |


#### **Keywords**
Restores storage configuration options to their initial<br>state on a machine with the given system_id.





Deprecated, use set-workload-annotations.

```bash
maas $PROFILE machine set-owner-data [--help] [-d] [-k] system_id

```

#### **Positional arguments**
| Argument | Effect |
|---|---|
| system_id | The system ID of the machine/device (e.g., `abc123`) |


#### **Command-line options**
| Option | Effect |
|---|---|
| --help, -h | Show this help message and exit. |
| -d, --debug | Display more information about API responses. |
| -k, --insecure | Disable SSL certificate check. |


#### **Keywords**
Deprecated, use set-workload-annotations instead.





Change storage layout

```bash
maas $PROFILE machine set-storage-layout [--help] [-d] [-k] system_id [data ...]

```

#### **Positional arguments**
| Argument | Effect |
|---|---|
| system_id | The system ID of the machine/device (e.g., `abc123`) |


#### **Command-line options**
| Option | Effect |
|---|---|
| --help, -h | Show this help message and exit. |
| -d, --debug | Display more information about API responses. |
| -k, --insecure | Disable SSL certificate check. |


#### **Keywords**
Changes the storage layout on machine with the given<br>system_id. This operation can only be performed on a machine with a status<br>of 'Ready'. Note: This will clear the current storage layout and any extra<br>configuration and replace it will the new layout.

##### Keyword "storage_layout"
Optional String. Storage layout for the<br>machine: ``flat``, ``lvm``, ``bcache``, ``vmfs6``, ``vmfs7``,<br>``custom`` or ``blank``.
##### Keyword "boot_size"
Optional String. Size of the boot partition<br>(e.g. 512M, 1G).
##### Keyword "root_size"
Optional String. Size of the root partition<br>(e.g. 24G).
##### Keyword "root_device"
Optional String. Physical block device to<br>place the root partition (e.g. /dev/sda).
##### Keyword "vg_name"
Optional String. LVM only. Name of created<br>volume group.
##### Keyword "lv_name"
Optional String. LVM only. Name of created<br>logical volume.
##### Keyword "lv_size"
Optional String. LVM only. Size of created<br>logical volume.
##### Keyword "cache_device"
Optional String. Bcache only. Physical<br>block device to use as the cache device (e.g. /dev/sda).
##### Keyword "cache_mode"
Optional String. Bcache only. Cache mode<br>for bcache device: ``writeback``, ``writethrough``, ``writearound``.
##### Keyword "cache_size"
Optional String. Bcache only. Size of the<br>cache partition to create on the cache device (e.g. 48G).
##### Keyword "cache_no_part"
Optional Boolean. Bcache only. Don't<br>create a partition on the cache device. Use the entire disk as the<br>cache device.


Note: This command accepts JSON.


Set key=value data

```bash
maas $PROFILE machine set-workload-annotations [--help] [-d] [-k] system_id [data ...]

```

#### **Positional arguments**
| Argument | Effect |
|---|---|
| system_id | The system ID of the machine/device (e.g., `abc123`) |


#### **Command-line options**
| Option | Effect |
|---|---|
| --help, -h | Show this help message and exit. |
| -d, --debug | Display more information about API responses. |
| -k, --insecure | Disable SSL certificate check. |


#### **Keywords**
Set key=value data for the current owner. Pass any key=value form data to this method to add, modify, or remove.<br>A key is removed when the value for that key is set to an empty string. This operation will not remove any previous keys unless explicitly<br>passed with an empty string. All workload annotations are removed when<br>the machine is no longer allocated to a user.

##### Keyword "key"
Optional String. ``key`` can be any string value.


Note: This command accepts JSON.


Begin testing process for a node

```bash
maas $PROFILE machine test [--help] [-d] [-k] system_id [data ...]

```

#### **Positional arguments**
| Argument | Effect |
|---|---|
| system_id | The system ID of the machine/device (e.g., `abc123`) |


#### **Command-line options**
| Option | Effect |
|---|---|
| --help, -h | Show this help message and exit. |
| -d, --debug | Display more information about API responses. |
| -k, --insecure | Disable SSL certificate check. |


#### **Keywords**
Begins the testing process for a given node. A node in the 'ready', 'allocated', 'deployed', 'broken', or any failed<br>state may run tests. If testing is started and successfully passes from<br>'broken' or any failed state besides 'failed commissioning' the node<br>will be returned to a ready state. Otherwise the node will return to<br>the state it was when testing started.

##### Keyword "enable_ssh"
Optional Int. Whether to enable SSH for<br>the testing environment using the user's SSH key(s). 0 == false. 1 ==<br>true.
##### Keyword "testing_scripts"
Optional String. A comma-separated<br>list of testing script names and tags to be run. By default all tests<br>tagged 'commissioning' will be run.
##### Keyword "parameters"
Optional String. Scripts selected to run<br>may define their own parameters. These parameters may be passed using<br>the parameter name. Optionally a parameter may have the script name<br>prepended to have that parameter only apply to that specific script.


Note: This command accepts JSON.


Unlock a machine

```bash
maas $PROFILE machine unlock [--help] [-d] [-k] system_id [data ...]

```

#### **Positional arguments**
| Argument | Effect |
|---|---|
| system_id | The system ID of the machine/device (e.g., `abc123`) |


#### **Command-line options**
| Option | Effect |
|---|---|
| --help, -h | Show this help message and exit. |
| -d, --debug | Display more information about API responses. |
| -k, --insecure | Disable SSL certificate check. |


#### **Keywords**
Mark a machine with the given system_id as 'Unlocked' to<br>allow changes.

##### Keyword "comment"
Optional String. comment for the<br>event log.


Note: This command accepts JSON.


Unmount a special-purpose filesystem

```bash
maas $PROFILE machine unmount-special [--help] [-d] [-k] system_id [data ...]

```

#### **Positional arguments**
| Argument | Effect |
|---|---|
| system_id | The system ID of the machine/device (e.g., `abc123`) |


#### **Command-line options**
| Option | Effect |
|---|---|
| --help, -h | Show this help message and exit. |
| -d, --debug | Display more information about API responses. |
| -k, --insecure | Disable SSL certificate check. |


#### **Keywords**
Unmount a special-purpose filesystem, like tmpfs, on a<br>machine with the given system_id.

##### Keyword "mount_point"
Optional String. Path on the filesystem to<br>unmount.


Note: This command accepts JSON.


Update a machine

```bash
maas $PROFILE machine update [--help] [-d] [-k] system_id [data ...]

```

#### **Positional arguments**
| Argument | Effect |
|---|---|
| system_id | The system ID of the machine/device (e.g., `abc123`) |


#### **Command-line options**
| Option | Effect |
|---|---|
| --help, -h | Show this help message and exit. |
| -d, --debug | Display more information about API responses. |
| -k, --insecure | Disable SSL certificate check. |


#### **Keywords**
Updates a machine with the given system_id.

##### Keyword "hostname"
Optional String. The new hostname for this<br>machine.
##### Keyword "description"
Optional String. The new description for<br>this machine.
##### Keyword "domain"
Optional String. The domain for this machine.<br>If not given the default domain is used.
##### Keyword "architecture"
Optional String. The new architecture<br>for this machine.
##### Keyword "min_hwe_kernel"
Optional String. A string containing<br>the minimum kernel version allowed to be ran on this machine.
##### Keyword "power_type"
Optional String. The new power type for<br>this machine. If you use the default value, power_parameters will be<br>set to the empty string. Available to admin users. See the `Power<br>types`_ section for a list of the available power types.
##### Keyword "power_parameters_skip_check"
Optional Boolean. Whether or not the new power parameters for this machine should be<br>checked against the expected power parameters for the machine's power<br>type ('true' or 'false'). The default is 'false'.
##### Keyword "pool"
Optional String. The resource pool to which the<br>machine should belong. All machines belong to the 'default' resource<br>pool if they do not belong to any other resource pool.
##### Keyword "zone"
Optional String. Name of a valid physical zone<br>in which to place this machine.
##### Keyword "swap_size"
Optional String. Specifies the size of the<br>swap file, in bytes. Field accept K, M, G and T suffixes for values<br>expressed respectively in kilobytes, megabytes, gigabytes and<br>terabytes.
##### Keyword "disable_ipv4"
Optional Boolean. Deprecated. If<br>specified, must be false.
##### Keyword "cpu_count"
Optional Int. The amount of CPU cores the<br>machine has.
##### Keyword "memory"
Optional String. How much memory the machine<br>has. Field accept K, M, G and T suffixes for values expressed<br>respectively in kilobytes, megabytes, gigabytes and terabytes.


Note: This command accepts JSON.


Accept declared machines

```bash
maas $PROFILE machines accept [--help] [-d] [-k] [data ...]

```


#### **Command-line options**
| Option | Effect |
|---|---|
| --help, -h | Show this help message and exit. |
| -d, --debug | Display more information about API responses. |
| -k, --insecure | Disable SSL certificate check. |


#### **Keywords**
Accept declared machines into MAAS. Machines can be enlisted in the MAAS anonymously or by non-admin users,<br>as opposed to by an admin. These machines are held in the New<br>state; a MAAS admin must first verify the authenticity of these<br>enlistments, and accept them. Enlistments can be accepted en masse, by passing multiple machines to<br>this call. Accepting an already accepted machine is not an error, but<br>accepting one that is already allocated, broken, etc. is.

##### Keyword "machines"
Optional String. A list of system_ids of the<br>machines whose enlistment is to be accepted. (An empty list is<br>acceptable).


Note: This command accepts JSON.


Accept all declared machines

```bash
maas $PROFILE machines accept-all [--help] [-d] [-k]

```


#### **Command-line options**
| Option | Effect |
|---|---|
| --help, -h | Show this help message and exit. |
| -d, --debug | Display more information about API responses. |
| -k, --insecure | Disable SSL certificate check. |


#### **Keywords**
Accept all declared machines into MAAS. Machines can be enlisted in the MAAS anonymously or by non-admin users,<br>as opposed to by an admin. These machines are held in the New<br>state; a MAAS admin must first verify the authenticity of these<br>enlistments, and accept them.





Add special hardware

```bash
maas $PROFILE machines add-chassis [--help] [-d] [-k] [data ...]

```


#### **Command-line options**
| Option | Effect |
|---|---|
| --help, -h | Show this help message and exit. |
| -d, --debug | Display more information about API responses. |
| -k, --insecure | Disable SSL certificate check. |


#### **Keywords**
Add special hardware types.

##### Keyword "chassis_type"
Optional String. The type<br>of hardware:<br><br>- ``hmcz``: IBM Hardware Management Console (HMC) for Z<br>- ``mscm``: Moonshot Chassis Manager.<br>- ``msftocs``: Microsoft OCS Chassis Manager.<br>- ``powerkvm``: Virtual Machines on Power KVM, managed by Virsh.<br>- ``proxmox``: Virtual Machines managed by Proxmox<br>- ``recs_box``: Christmann RECS\|Box servers.<br>- ``sm15k``: Seamicro 1500 Chassis.<br>- ``ucsm``: Cisco UCS Manager.<br>- ``virsh``: virtual machines managed by Virsh.<br>- ``vmware`` is the type for virtual machines managed by VMware.
##### Keyword "hostname"
Optional String. The URL, hostname, or IP<br>address to access the chassis.
##### Keyword "username"
Optional String. The username used to access<br>the chassis. This field is required for the recs_box, seamicro15k,<br>vmware, mscm, msftocs, ucsm, and hmcz chassis types.
##### Keyword "password"
Optional String. The password used to access<br>the chassis. This field is required for the ``recs_box``,<br>``seamicro15k``, ``vmware``, ``mscm``, ``msftocs``, ``ucsm``, and<br>``hmcz`` chassis types.
##### Keyword "accept_all"
Optional String. If true, all enlisted<br>machines will be commissioned.
##### Keyword "rack_controller"
Optional String. The system_id of the<br>rack controller to send the add chassis command through. If none is<br>specified MAAS will automatically determine the rack controller to use.
##### Keyword "domain"
Optional String. The domain that each new<br>machine added should use.
##### Keyword "prefix_filter"
Optional String. (``virsh``,<br>``vmware``, ``powerkvm``, ``proxmox``, ``hmcz`` only.) Filter machines<br>with supplied prefix.
##### Keyword "power_control"
Optional String. (``seamicro15k`` only)<br>The power_control to use, either ipmi (default), restapi, or restapi2. The following are optional if you are adding a proxmox chassis.
##### Keyword "token_name"
Optional String. The name the<br>authentication token to be used instead of a password.
##### Keyword "token_secret"
Optional String. The token secret<br>to be used in combination with the power_token_name used in place of<br>a password.
##### Keyword "verify_ssl"
Optional Boolean. Whether SSL<br>connections should be verified. The following are optional if you are adding a recs_box, vmware or<br>msftocs chassis.
##### Keyword "port"
Optional Int. (``recs_box``, ``vmware``,<br>``msftocs`` only) The port to use when accessing the chassis. The following are optional if you are adding a vmware chassis:
##### Keyword "protocol"
Optional String. (``vmware`` only) The<br>protocol to use when accessing the VMware chassis (default: https). :return: A string containing the chassis powered on by which rack<br>controller.


Note: This command accepts JSON.


Allocate a machine

```bash
maas $PROFILE machines allocate [--help] [-d] [-k] [data ...]

```


#### **Command-line options**
| Option | Effect |
|---|---|
| --help, -h | Show this help message and exit. |
| -d, --debug | Display more information about API responses. |
| -k, --insecure | Disable SSL certificate check. |


#### **Keywords**
Allocates an available machine for deployment. Constraints parameters can be used to allocate a machine that possesses<br>certain characteristics. All the constraints are optional and when<br>multiple constraints are provided, they are combined using 'AND'<br>semantics.

##### Keyword "name"
Optional String. Hostname or FQDN of the desired<br>machine. If a FQDN is specified, both the domain and the hostname<br>portions must match.
##### Keyword "system_id"
Optional String. system_id of the desired<br>machine.
##### Keyword "arch"
Optional String. Architecture of<br>the returned machine (e.g. 'i386/generic', 'amd64', 'armhf/highbank',<br>etc.). If multiple architectures are specified, the machine to acquire may<br>match any of the given architectures. To request multiple<br>architectures, this parameter must be repeated in the request with each<br>value.
##### Keyword "cpu_count"
Optional Int. Minimum<br>number of CPUs a returned machine must have. A machine with additional CPUs may be allocated if there is no exact<br>match, or if the 'mem' constraint is not also specified.
##### Keyword "mem"
Optional Int. The minimum amount of memory<br>(expressed in MB) the returned machine must have. A machine with<br>additional memory may be allocated if there is no exact match, or the<br>'cpu_count' constraint is not also specified.
##### Keyword "tags"
Optional String. Tags the<br>machine must match in order to be acquired. If multiple tag names are specified, the machine must be tagged with<br>all of them. To request multiple tags, this parameter must be repeated<br>in the request with each value.
##### Keyword "not_tags"
Optional String. Tags the machine must NOT<br>match. If multiple tag names are specified, the machine must NOT be<br>tagged with ANY of them. To request exclusion of multiple tags, this<br>parameter must be repeated in the request with each value.
##### Keyword "zone"
Optional String. Physical zone name the machine<br>must be located in.
##### Keyword "not_in_zone"
Optional String. List of physical zones<br>from which the machine must not be acquired. If multiple zones are<br>specified, the machine must NOT be associated with ANY of them. To<br>request multiple zones to exclude, this parameter must be repeated in<br>the request with each value.
##### Keyword "pool"
Optional String. Resource pool name the machine<br>must belong to.
##### Keyword "not_in_pool"
Optional String. List of resource pool<br>from which the machine must not be acquired. If multiple pools are<br>specified, the machine must NOT be associated with ANY of them. To<br>request multiple pools to exclude, this parameter must be repeated in<br>the request with each value.
##### Keyword "pod"
Optional String. Pod the machine must be located<br>in.
##### Keyword "not_pod"
Optional String. Pod the machine must not be<br>located in.
##### Keyword "pod_type"
Optional String. Pod type the machine must<br>be located in.
##### Keyword "not_pod_type"
Optional String. Pod type the machine<br>must not be located in.
##### Keyword "subnets"
Optional String. Subnets that<br>must be linked to the machine. "Linked to" means the node must be configured to acquire an address in<br>the specified subnet, have a static IP address in the specified subnet,<br>or have been observed to DHCP from the specified subnet during<br>commissioning time (which implies that it *could* have an address on<br>the specified subnet). Subnets can be specified by one of the following criteria:<br><br>- <id>: Match the subnet by its 'id' field<br>- fabric:<fabric-spec>: Match all subnets in a given fabric.<br>- ip:<ip-address>: Match the subnet containing <ip-address> with the<br>with the longest-prefix match.<br>- name:<subnet-name>: Match a subnet with the given name.<br>- space:<space-spec>: Match all subnets in a given space.<br>- vid:<vid-integer>: Match a subnet on a VLAN with the specified VID.<br>Valid values range from 0 through 4094 (inclusive). An untagged VLAN<br>can be specified by using the value “0”.<br>- vlan:<vlan-spec>: Match all subnets on the given VLAN. Note that (as of this writing), the 'fabric', 'space', 'vid', and<br>'vlan' specifiers are only useful for the 'not_spaces' version of this<br>constraint, because they will most likely force the query to match ALL<br>the subnets in each fabric, space, or VLAN, and thus not return any<br>nodes. (This is not a particularly useful behavior, so may be changed<br>in the future.)<br><br>If multiple subnets are specified, the machine must be associated with<br>all of them. To request multiple subnets, this parameter must be<br>repeated in the request with each value. Note that this replaces the legacy 'networks' constraint in MAAS 1.x.
##### Keyword "not_subnets"
Optional String. Subnets<br>that must NOT be linked to the machine. See the 'subnets' constraint documentation above for more information<br>about how each subnet can be specified. If multiple subnets are specified, the machine must NOT be associated<br>with ANY of them. To request multiple subnets to exclude, this<br>parameter must be repeated in the request with each value. (Or a<br>fabric, space, or VLAN specifier may be used to match multiple<br>subnets). Note that this replaces the legacy 'not_networks' constraint in MAAS<br>1.x.
##### Keyword "storage"
Optional String. A list of storage constraint<br>identifiers, in the form: ``label:size(tag[,tag[,…])][,label:…]``.
##### Keyword "interfaces"
Optional String. A labeled<br>constraint map associating constraint labels with interface properties<br>that should be matched. Returned nodes must have one or more interface<br>matching the specified constraints. The labeled constraint map must be<br>in the format: ``label:key=value[,key2=value2[,…]]``. Each key can be one of the following:<br><br>- ``id``: Matches an interface with the specific id<br>- ``fabric``: Matches an interface attached to the specified fabric.<br>- ``fabric_class``: Matches an interface attached to a fabric with the<br>specified class.<br>- ``ip``: Matches an interface with the specified IP address assigned<br>to it.<br>- ``mode``: Matches an interface with the specified mode. (Currently,<br>the only supported mode is "unconfigured".)<br>- ``name``: Matches an interface with the specified name. (For<br>example, "eth0".)<br>- ``hostname``: Matches an interface attached to the node with the<br>specified hostname.<br>- ``subnet``: Matches an interface attached to the specified subnet.<br>- ``space``: Matches an interface attached to the specified space.<br>- ``subnet_cidr``: Matches an interface attached to the specified<br>subnet CIDR. (For example, "192.168.0.0/24".)<br>- ``type``: Matches an interface of the specified type. (Valid types:<br>"physical", "vlan", "bond", "bridge", or "unknown".)<br>- ``vlan``: Matches an interface on the specified VLAN.<br>- ``vid``: Matches an interface on a VLAN with the specified VID.<br>- ``tag``: Matches an interface tagged with the specified tag.<br>- ``link_speed``: Matches an interface with link_speed equal to or<br>greater than the specified speed.
##### Keyword "fabrics"
Optional String. Set of fabrics that the<br>machine must be associated with in order to be acquired. If multiple<br>fabrics names are specified, the machine can be in any of the specified<br>fabrics. To request multiple possible fabrics to match, this parameter<br>must be repeated in the request with each value.
##### Keyword "not_fabrics"
Optional String. Fabrics the machine must<br>NOT be associated with in order to be acquired. If multiple fabrics<br>names are specified, the machine must NOT be in ANY of them. To request<br>exclusion of multiple fabrics, this parameter must be repeated in the<br>request with each value.
##### Keyword "fabric_classes"
Optional String. Set of fabric class<br>types whose fabrics the machine must be associated with in order to be<br>acquired. If multiple fabrics class types are specified, the machine<br>can be in any matching fabric. To request multiple possible fabrics<br>class types to match, this parameter must be repeated in the request<br>with each value.
##### Keyword "not_fabric_classes"
Optional String. Fabric class<br>types whose fabrics the machine must NOT be associated with in order to<br>be acquired. If multiple fabrics names are specified, the machine must<br>NOT be in ANY of them. To request exclusion of multiple fabrics, this<br>parameter must be repeated in the request with each value.
##### Keyword "agent_name"
Optional String. An optional agent name to<br>attach to the acquired machine.
##### Keyword "comment"
Optional String. Comment for the event log.
##### Keyword "bridge_all"
Optional Boolean. Optionally create a<br>bridge interface for every configured interface on the machine. The<br>created bridges will be removed once the machine is released.<br>(Default: False)
##### Keyword "bridge_stp"
Optional Boolean. Optionally turn spanning<br>tree protocol on or off for the bridges created on every configured<br>interface. (Default: off)
##### Keyword "bridge_fd"
Optional Int. Optionally adjust the forward<br>delay to time seconds. (Default: 15)
##### Keyword "devices"
Optional String. Only return a node which<br>have one or more devices containing the following constraints in the<br>format key=value[,key2=value2[,…]]<br><br>Each key can be one of the following:<br><br>- ``vendor_id``: The device vendor id<br>- ``product_id``: The device product id<br>- ``vendor_name``: The device vendor name, not case sensitive<br>- ``product_name``: The device product name, not case sensitive<br>- ``commissioning_driver``: The device uses this driver during<br>commissioning.
##### Keyword "dry_run"
Optional Boolean. boolean to<br>indicate that the machine should not actually be acquired (this is for<br>support/troubleshooting, or users who want to see which machine would<br>match a constraint, without acquiring a machine). Defaults to False.
##### Keyword "verbose"
Optional Boolean. boolean to<br>indicate that the user would like additional verbosity in the<br>constraints_by_type field (each constraint will be prefixed by<br>``verbose_``, and contain the full data structure that indicates which<br>machine(s) matched).


Note: This command accepts JSON.


Clone storage and/or interface configurations

```bash
maas $PROFILE machines clone [--help] [-d] [-k] [data ...]

```


#### **Command-line options**
| Option | Effect |
|---|---|
| --help, -h | Show this help message and exit. |
| -d, --debug | Display more information about API responses. |
| -k, --insecure | Disable SSL certificate check. |


#### **Keywords**
Clone storage and/or interface configurations<br><br>A machine storage and/or interface configuration can be cloned to a<br>set of destination machines. For storage configuration, cloning the destination machine must have at<br>least the same number of physical block devices or more, along with<br>the physical block devices being the same size or greater. For interface configuration, cloning the destination machine must have<br>at least the same number of interfaces with the same names. The<br>destination machine can have more interfaces than the source, as long<br>as the subset of interfaces on the destination have the same matching<br>names as the source.

##### Keyword "source"
Optional String. The system_id of the machine<br>that is the source of the configuration.
##### Keyword "destinations"
Optional String. A list of system_ids to<br>clone the configuration to.
##### Keyword "interfaces"
Optional Boolean. Whether to clone<br>interface configuration. Defaults to False.
##### Keyword "storage"
Optional Boolean. Whether to clone storage<br>configuration. Defaults to False.


Note: This command accepts JSON.


Create a new machine

```bash
maas $PROFILE machines create [--help] [-d] [-k] [data ...]

```


#### **Command-line options**
| Option | Effect |
|---|---|
| --help, -h | Show this help message and exit. |
| -d, --debug | Display more information about API responses. |
| -k, --insecure | Disable SSL certificate check. |


#### **Keywords**
Create a new machine. Adding a server to MAAS will (by default) cause the machine to<br>network boot into an ephemeral environment to collect hardware<br>information. In anonymous enlistment (and when the enlistment is done by a<br>non-admin), the machine is held in the “New” state for approval<br>by a MAAS admin. The minimum data required is:<br><br>architecture=<arch string> (e.g. "i386/generic")<br>mac_addresses=<value> (e.g. "aa:bb:cc:dd:ee:ff")

##### Keyword "architecture"
Optional String. A string containing the<br>architecture type of the machine. (For example, “i386”, or “amd64”.) To
##### Keyword "min_hwe_kernel"
Optional String. A string containing<br>the minimum kernel version allowed to be ran on this machine.
##### Keyword "subarchitecture"
Optional String. A string containing<br>the subarchitecture type of the machine. (For example, “generic” or<br>“hwe-t”.) To determine the supported subarchitectures, use the<br>boot-resources endpoint.
##### Keyword "mac_addresses"
Optional String. One or more MAC<br>addresses for the machine. To specify more than one MAC address, the<br>parameter must be specified twice. (such as "machines new<br>mac_addresses=01:02:03:04:05:06 mac_addresses=02:03:04:05:06:07")
##### Keyword "hostname"
Optional String. A hostname. If not given,<br>one will be generated.
##### Keyword "description"
Optional String. A optional description.
##### Keyword "domain"
Optional String. The domain of the machine. If<br>not given the default domain is used.
##### Keyword "power_type"
Optional String. A power management type,<br>if applicable (e.g. “virsh”, “ipmi”).
##### Keyword "commission"
Optional Boolean. Request<br>the newly created machine to be created with status set to<br>COMMISSIONING. Machines will wait for COMMISSIONING results and not<br>time out. Machines created by administrators will be commissioned<br>unless set to false.
##### Keyword "deployed"
Optional Boolean. Request<br>the newly created machine to be created with status set to<br>DEPLOYED. Setting this to true implies commissioning=false,<br>meaning that the machine won't go through the commissioning<br>process.
##### Keyword "enable_ssh"
Optional Int. Whether to enable SSH for<br>the commissioning environment using the user's SSH key(s). '1' == True,<br>'0' == False.
##### Keyword "skip_bmc_config"
Optional Int. Whether to skip<br>re-configuration of the BMC for IPMI based machines. '1' == True, '0'<br>== False.
##### Keyword "skip_networking"
Optional Int. Whether to skip<br>re-configuring the networking on the machine after the commissioning<br>has completed. '1' == True, '0' == False.
##### Keyword "skip_storage"
Optional Int. Whether to skip<br>re-configuring the storage on the machine after the commissioning has<br>completed. '1' == True, '0' == False.
##### Keyword "commissioning_scripts"
Optional String. A comma<br>separated list of commissioning script names and tags to be run. By<br>default all custom commissioning scripts are run. Built-in<br>commissioning scripts always run. Selecting 'update_firmware' or<br>'configure_hba' will run firmware updates or configure HBA's on<br>matching machines.
##### Keyword "is_dpu"
Optional Boolean. Whether the machine is a DPU<br>or not. If not provided, the machine is considered a non-DPU machine.
##### Keyword "testing_scripts"
Optional String. A comma separated<br>list of testing script names and tags to be run. By default all tests<br>tagged 'commissioning' will be run. Set to 'none' to disable running<br>tests.


Note: This command accepts JSON.


MAC address registered

```bash
maas $PROFILE machines is-registered [--help] [-d] [-k] [data ...]

```


#### **Command-line options**
| Option | Effect |
|---|---|
| --help, -h | Show this help message and exit. |
| -d, --debug | Display more information about API responses. |
| -k, --insecure | Disable SSL certificate check. |


#### **Keywords**
Returns whether or not the given MAC address is registered<br>within this MAAS (and attached to a non-retired node).

##### Keyword "mac_address"
Optional URL String. The MAC address to be<br>checked.


Note: This command accepts JSON.


List allocated

```bash
maas $PROFILE machines list-allocated [--help] [-d] [-k]

```


#### **Command-line options**
| Option | Effect |
|---|---|
| --help, -h | Show this help message and exit. |
| -d, --debug | Display more information about API responses. |
| -k, --insecure | Disable SSL certificate check. |


#### **Keywords**
List machines that were allocated to the User.





Get power parameters

```bash
maas $PROFILE machines power-parameters [--help] [-d] [-k] [data ...]

```


#### **Command-line options**
| Option | Effect |
|---|---|
| --help, -h | Show this help message and exit. |
| -d, --debug | Display more information about API responses. |
| -k, --insecure | Disable SSL certificate check. |


#### **Keywords**
Get power parameters for multiple machines. To request<br>power parameters for a specific machine or more than one machine:<br>``op=power_parameters&id=abc123&id=def456``.

##### Keyword "id"
Optional URL String. A system ID. To request more<br>than one machine, provide multiple ``id`` arguments in the request.<br>Only machines with matching system ids will be returned.


Note: This command accepts JSON.


List Nodes visible to the user

```bash
maas $PROFILE machines read [--help] [-d] [-k] [data ...]

```


#### **Command-line options**
| Option | Effect |
|---|---|
| --help, -h | Show this help message and exit. |
| -d, --debug | Display more information about API responses. |
| -k, --insecure | Disable SSL certificate check. |


#### **Keywords**
List nodes visible to current user, optionally filtered by<br>criteria. Nodes are sorted by id (i.e. most recent last) and grouped by type.

##### Keyword "hostname"
Optional String. Only nodes relating to the<br>node with the matching hostname will be returned. This can be specified<br>multiple times to see multiple nodes.
##### Keyword "cpu_count"
Optional Int. Only nodes with the specified<br>minimum number of CPUs will be included.
##### Keyword "mem"
Optional String. Only nodes with the specified<br>minimum amount of RAM (in MiB) will be included.
##### Keyword "mac_address"
Optional String. Only nodes relating to<br>the node owning the specified MAC address will be returned. This can be<br>specified multiple times to see multiple nodes.
##### Keyword "id"
Optional String. Only nodes relating to the nodes<br>with matching system ids will be returned.
##### Keyword "domain"
Optional String. Only nodes relating to the<br>nodes in the domain will be returned.
##### Keyword "zone"
Optional String. Only nodes relating to the<br>nodes in the zone will be returned.
##### Keyword "pool"
Optional String. Only nodes belonging to the<br>pool will be returned.
##### Keyword "agent_name"
Optional String. Only nodes relating to<br>the nodes with matching agent names will be returned.
##### Keyword "fabrics"
Optional String. Only nodes with interfaces<br>in specified fabrics will be returned.
##### Keyword "not_fabrics"
Optional String. Only nodes with<br>interfaces not in specified fabrics will be returned.
##### Keyword "vlans"
Optional String. Only nodes with interfaces in<br>specified VLANs will be returned.
##### Keyword "not_vlans"
Optional String. Only nodes with interfaces<br>not in specified VLANs will be returned.
##### Keyword "subnets"
Optional String. Only nodes with interfaces<br>in specified subnets will be returned.
##### Keyword "not_subnets"
Optional String. Only nodes with<br>interfaces not in specified subnets will be returned.
##### Keyword "link_speed"
Optional String. Only nodes with<br>interfaces with link speeds greater than or equal to link_speed will<br>be returned.
##### Keyword "status"
Optional String. Only nodes with specified<br>status will be returned.
##### Keyword "pod"
Optional String. Only nodes that belong to a<br>specified pod will be returned.
##### Keyword "not_pod"
Optional String. Only nodes that don't<br>belong to a specified pod will be returned.
##### Keyword "pod_type"
Optional String. Only nodes that belong to<br>a pod of the specified type will be returned.
##### Keyword "not_pod_type"
Optional String. Only nodes that don't<br>belong a pod of the specified type will be returned.
##### Keyword "devices"
Optional String. Only return nodes which<br>have one or more devices containing the following constraints in the<br>format key=value[,key2=value2[,…]]<br><br>Each key can be one of the following:<br><br>- ``vendor_id``: The device vendor id<br>- ``product_id``: The device product id<br>- ``vendor_name``: The device vendor name, not case sensitive<br>- ``product_name``: The device product name, not case sensitive<br>- ``commissioning_driver``: The device uses this driver during<br>commissioning.


Note: This command accepts JSON.


Release machines

```bash
maas $PROFILE machines release [--help] [-d] [-k] [data ...]

```


#### **Command-line options**
| Option | Effect |
|---|---|
| --help, -h | Show this help message and exit. |
| -d, --debug | Display more information about API responses. |
| -k, --insecure | Disable SSL certificate check. |


#### **Keywords**
Release multiple machines. Places the machines back into<br>the pool, ready to be reallocated.

##### Keyword "machines"
Optional String. A list of system_ids of the<br>machines which are to be released. (An empty list is acceptable).
##### Keyword "comment"
Optional String. comment for the<br>event log.


Note: This command accepts JSON.


Assign nodes to a zone

```bash
maas $PROFILE machines set-zone [--help] [-d] [-k] [data ...]

```


#### **Command-line options**
| Option | Effect |
|---|---|
| --help, -h | Show this help message and exit. |
| -d, --debug | Display more information about API responses. |
| -k, --insecure | Disable SSL certificate check. |


#### **Keywords**
Assigns a given node to a given zone.

##### Keyword "zone"
Optional String. The zone name.
##### Keyword "nodes"
Optional String. The node to add.


Note: This command accepts JSON.
