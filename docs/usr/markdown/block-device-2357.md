Add a tag

```bash
maas $PROFILE block-device add-tag [--help] [-d] [-k] system_id id [data ...]

```

#### **Positional arguments**
| Argument | Effect |
|---|---|
| system_id | The system ID of the machine/device (e.g., `abc123`) |
| id | The ID of the resource (e.g., `1`, `abc123`) |


#### **Command-line options**
| Option | Effect |
|---|---|
| --help, -h | Show this help message and exit. |
| -d, --debug | Display more information about API responses. |
| -k, --insecure | Disable SSL certificate check. |


#### **Keywords**
Add a tag to block device on a given machine.

##### Keyword "tag"
Optional String. The tag being added.


Note: This command accepts JSON.


Delete a block device

```bash
maas $PROFILE block-device delete [--help] [-d] [-k] system_id id

```

#### **Positional arguments**
| Argument | Effect |
|---|---|
| system_id | The system ID of the machine/device (e.g., `abc123`) |
| id | The ID of the resource (e.g., `1`, `abc123`) |


#### **Command-line options**
| Option | Effect |
|---|---|
| --help, -h | Show this help message and exit. |
| -d, --debug | Display more information about API responses. |
| -k, --insecure | Disable SSL certificate check. |


#### **Keywords**
Delete block device on a given machine.





Format block device

```bash
maas $PROFILE block-device format [--help] [-d] [-k] system_id id [data ...]

```

#### **Positional arguments**
| Argument | Effect |
|---|---|
| system_id | The system ID of the machine/device (e.g., `abc123`) |
| id | The ID of the resource (e.g., `1`, `abc123`) |


#### **Command-line options**
| Option | Effect |
|---|---|
| --help, -h | Show this help message and exit. |
| -d, --debug | Display more information about API responses. |
| -k, --insecure | Disable SSL certificate check. |


#### **Keywords**
Format block device with filesystem.

##### Keyword "fstype"
Optional String. Type of filesystem.
##### Keyword "uuid"
Optional String. UUID of the filesystem.


Note: This command accepts JSON.


Mount a filesystem

```bash
maas $PROFILE block-device mount [--help] [-d] [-k] system_id id [data ...]

```

#### **Positional arguments**
| Argument | Effect |
|---|---|
| system_id | The system ID of the machine/device (e.g., `abc123`) |
| id | The ID of the resource (e.g., `1`, `abc123`) |


#### **Command-line options**
| Option | Effect |
|---|---|
| --help, -h | Show this help message and exit. |
| -d, --debug | Display more information about API responses. |
| -k, --insecure | Disable SSL certificate check. |


#### **Keywords**
Mount the filesystem on block device.

##### Keyword "mount_point"
Optional String. Path on the filesystem<br>to mount.
##### Keyword "mount_options"
Optional String. Options to pass to<br>mount(8).


Note: This command accepts JSON.


Read a block device

```bash
maas $PROFILE block-device read [--help] [-d] [-k] system_id id

```

#### **Positional arguments**
| Argument | Effect |
|---|---|
| system_id | The system ID of the machine/device (e.g., `abc123`) |
| id | The ID of the resource (e.g., `1`, `abc123`) |


#### **Command-line options**
| Option | Effect |
|---|---|
| --help, -h | Show this help message and exit. |
| -d, --debug | Display more information about API responses. |
| -k, --insecure | Disable SSL certificate check. |


#### **Keywords**
Read a block device on a given machine.





Remove a tag

```bash
maas $PROFILE block-device remove-tag [--help] [-d] [-k] system_id id [data ...]

```

#### **Positional arguments**
| Argument | Effect |
|---|---|
| system_id | The system ID of the machine/device (e.g., `abc123`) |
| id | The ID of the resource (e.g., `1`, `abc123`) |


#### **Command-line options**
| Option | Effect |
|---|---|
| --help, -h | Show this help message and exit. |
| -d, --debug | Display more information about API responses. |
| -k, --insecure | Disable SSL certificate check. |


#### **Keywords**
Remove a tag from block device on a given machine.

##### Keyword "tag"
Optional String. The tag being removed.


Note: This command accepts JSON.


Set boot disk

```bash
maas $PROFILE block-device set-boot-disk [--help] [-d] [-k] system_id id

```

#### **Positional arguments**
| Argument | Effect |
|---|---|
| system_id | The system ID of the machine/device (e.g., `abc123`) |
| id | The ID of the resource (e.g., `1`, `abc123`) |


#### **Command-line options**
| Option | Effect |
|---|---|
| --help, -h | Show this help message and exit. |
| -d, --debug | Display more information about API responses. |
| -k, --insecure | Disable SSL certificate check. |


#### **Keywords**
Set a block device as the boot disk for the machine.





Unformat a block device

```bash
maas $PROFILE block-device unformat [--help] [-d] [-k] system_id id

```

#### **Positional arguments**
| Argument | Effect |
|---|---|
| system_id | The system ID of the machine/device (e.g., `abc123`) |
| id | The ID of the resource (e.g., `1`, `abc123`) |


#### **Command-line options**
| Option | Effect |
|---|---|
| --help, -h | Show this help message and exit. |
| -d, --debug | Display more information about API responses. |
| -k, --insecure | Disable SSL certificate check. |


#### **Keywords**
Unformat a previously formatted block device.





Unmount a filesystem

```bash
maas $PROFILE block-device unmount [--help] [-d] [-k] system_id id

```

#### **Positional arguments**
| Argument | Effect |
|---|---|
| system_id | The system ID of the machine/device (e.g., `abc123`) |
| id | The ID of the resource (e.g., `1`, `abc123`) |


#### **Command-line options**
| Option | Effect |
|---|---|
| --help, -h | Show this help message and exit. |
| -d, --debug | Display more information about API responses. |
| -k, --insecure | Disable SSL certificate check. |


#### **Keywords**
Unmount the filesystem on block device.





Update a block device

```bash
maas $PROFILE block-device update [--help] [-d] [-k] system_id id [data ...]

```

#### **Positional arguments**
| Argument | Effect |
|---|---|
| system_id | The system ID of the machine/device (e.g., `abc123`) |
| id | The ID of the resource (e.g., `1`, `abc123`) |


#### **Command-line options**
| Option | Effect |
|---|---|
| --help, -h | Show this help message and exit. |
| -d, --debug | Display more information about API responses. |
| -k, --insecure | Disable SSL certificate check. |


#### **Keywords**
Update block device on a given machine. Machines must have a status of Ready to have access to all options.<br>Machines with Deployed status can only have the name, model, serial,<br>and/or id_path updated for a block device. This is intended to allow a<br>bad block device to be replaced while the machine remains deployed.

##### Keyword "name"
Optional String. (Virtual devices) Name of<br>the block device.
##### Keyword "model"
Optional String. (Physical devices) Model of<br>the block device.
##### Keyword "serial"
Optional String. (Physical devices) Serial<br>number of the block device.
##### Keyword "id_path"
Optional String. (Physical devices) Only used<br>if model and serial cannot be provided. This should be a path that is<br>fixed and doesn't change depending on the boot order or kernel version.
##### Keyword "size"
Optional String. (Virtual devices) Size of<br>the block device. (Only allowed for logical volumes.)
##### Keyword "block_size"
Optional String. (Physical devices) Block<br>size of the block device.
##### Keyword "uuid"
Optional String. (Virtual devices) UUID of<br>the block device.


Note: This command accepts JSON.


Create a block device

```bash
maas $PROFILE block-devices create [--help] [-d] [-k] system_id [data ...]

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
Create a physical block device.

##### Keyword "name"
Optional String. Name of the block device.
##### Keyword "model"
Optional String. Model of the block device.
##### Keyword "serial"
Optional String. Serial number of the block<br>device.
##### Keyword "id_path"
Optional String. Only used if model and<br>serial cannot be provided. This should be a path that is fixed and<br>doesn't change depending on the boot order or kernel version.
##### Keyword "size"
Optional String. Size of the block device.
##### Keyword "block_size"
Optional String. Block size of the block<br>device.


Note: This command accepts JSON.


List block devices

```bash
maas $PROFILE block-devices read [--help] [-d] [-k] system_id

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
List all block devices belonging to a machine.
