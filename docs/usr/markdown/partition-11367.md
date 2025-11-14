Add a tag

```bash
maas $PROFILE partition add-tag [--help] [-d] [-k] system_id device_id id [data ...]

```

#### **Positional arguments**
| Argument | Effect |
|---|---|
| system_id | The system ID of the machine/device (e.g., `abc123`) |
| device_id | The device_id parameter |
| id | The ID of the resource (e.g., `1`, `abc123`) |


#### **Command-line options**
| Option | Effect |
|---|---|
| --help, -h | Show this help message and exit. |
| -d, --debug | Display more information about API responses. |
| -k, --insecure | Disable SSL certificate check. |


#### **Keywords**
Add a tag to a partition on machine system_id, device<br>device_id and partition id.

##### Keyword "tag"
Optional String. The tag being added.


Note: This command accepts JSON.


Delete a partition

```bash
maas $PROFILE partition delete [--help] [-d] [-k] system_id device_id id

```

#### **Positional arguments**
| Argument | Effect |
|---|---|
| system_id | The system ID of the machine/device (e.g., `abc123`) |
| device_id | The device_id parameter |
| id | The ID of the resource (e.g., `1`, `abc123`) |


#### **Command-line options**
| Option | Effect |
|---|---|
| --help, -h | Show this help message and exit. |
| -d, --debug | Display more information about API responses. |
| -k, --insecure | Disable SSL certificate check. |


#### **Keywords**
Delete the partition from machine system_id and device<br>device_id with the given partition id.





Format a partition

```bash
maas $PROFILE partition format [--help] [-d] [-k] system_id device_id id [data ...]

```

#### **Positional arguments**
| Argument | Effect |
|---|---|
| system_id | The system ID of the machine/device (e.g., `abc123`) |
| device_id | The device_id parameter |
| id | The ID of the resource (e.g., `1`, `abc123`) |


#### **Command-line options**
| Option | Effect |
|---|---|
| --help, -h | Show this help message and exit. |
| -d, --debug | Display more information about API responses. |
| -k, --insecure | Disable SSL certificate check. |


#### **Keywords**
Format the partition on machine system_id and device<br>device_id with the given partition id.

##### Keyword "fstype"
Optional String. Type of filesystem.
##### Keyword "uuid"
Optional String. The UUID for the filesystem.
##### Keyword "label"
Optional String. The label for the filesystem.


Note: This command accepts JSON.


Mount a filesystem

```bash
maas $PROFILE partition mount [--help] [-d] [-k] system_id device_id id [data ...]

```

#### **Positional arguments**
| Argument | Effect |
|---|---|
| system_id | The system ID of the machine/device (e.g., `abc123`) |
| device_id | The device_id parameter |
| id | The ID of the resource (e.g., `1`, `abc123`) |


#### **Command-line options**
| Option | Effect |
|---|---|
| --help, -h | Show this help message and exit. |
| -d, --debug | Display more information about API responses. |
| -k, --insecure | Disable SSL certificate check. |


#### **Keywords**
Mount a filesystem on machine system_id, device device_id<br>and partition id.

##### Keyword "mount_point"
Optional String. Path on the filesystem to<br>mount.
##### Keyword "mount_options"
Optional String. Options to pass to<br>mount(8).


Note: This command accepts JSON.


Read a partition

```bash
maas $PROFILE partition read [--help] [-d] [-k] system_id device_id id

```

#### **Positional arguments**
| Argument | Effect |
|---|---|
| system_id | The system ID of the machine/device (e.g., `abc123`) |
| device_id | The device_id parameter |
| id | The ID of the resource (e.g., `1`, `abc123`) |


#### **Command-line options**
| Option | Effect |
|---|---|
| --help, -h | Show this help message and exit. |
| -d, --debug | Display more information about API responses. |
| -k, --insecure | Disable SSL certificate check. |


#### **Keywords**
Read the partition from machine system_id and device<br>device_id with the given partition id.





Remove a tag

```bash
maas $PROFILE partition remove-tag [--help] [-d] [-k] system_id device_id id [data ...]

```

#### **Positional arguments**
| Argument | Effect |
|---|---|
| system_id | The system ID of the machine/device (e.g., `abc123`) |
| device_id | The device_id parameter |
| id | The ID of the resource (e.g., `1`, `abc123`) |


#### **Command-line options**
| Option | Effect |
|---|---|
| --help, -h | Show this help message and exit. |
| -d, --debug | Display more information about API responses. |
| -k, --insecure | Disable SSL certificate check. |


#### **Keywords**
Remove a tag from a partition on machine system_id, device<br>device_id and partition id.

##### Keyword "tag"
Optional String. The tag being removed.


Note: This command accepts JSON.


Unformat a partition

```bash
maas $PROFILE partition unformat [--help] [-d] [-k] system_id device_id id

```

#### **Positional arguments**
| Argument | Effect |
|---|---|
| system_id | The system ID of the machine/device (e.g., `abc123`) |
| device_id | The device_id parameter |
| id | The ID of the resource (e.g., `1`, `abc123`) |


#### **Command-line options**
| Option | Effect |
|---|---|
| --help, -h | Show this help message and exit. |
| -d, --debug | Display more information about API responses. |
| -k, --insecure | Disable SSL certificate check. |


#### **Keywords**
Unformat the partition on machine system_id and device<br>device_id with the given partition id.





Unmount a filesystem

```bash
maas $PROFILE partition unmount [--help] [-d] [-k] system_id device_id id

```

#### **Positional arguments**
| Argument | Effect |
|---|---|
| system_id | The system ID of the machine/device (e.g., `abc123`) |
| device_id | The device_id parameter |
| id | The ID of the resource (e.g., `1`, `abc123`) |


#### **Command-line options**
| Option | Effect |
|---|---|
| --help, -h | Show this help message and exit. |
| -d, --debug | Display more information about API responses. |
| -k, --insecure | Disable SSL certificate check. |


#### **Keywords**
Unmount a filesystem on machine system_id, device<br>device_id and partition id.





Create a partition

```bash
maas $PROFILE partitions create [--help] [-d] [-k] system_id device_id [data ...]

```

#### **Positional arguments**
| Argument | Effect |
|---|---|
| system_id | The system ID of the machine/device (e.g., `abc123`) |
| device_id | The device_id parameter |


#### **Command-line options**
| Option | Effect |
|---|---|
| --help, -h | Show this help message and exit. |
| -d, --debug | Display more information about API responses. |
| -k, --insecure | Disable SSL certificate check. |


#### **Keywords**
Create a partition on a block device.

##### Keyword "size"
Optional Int. The size of the partition in bytes.<br>If not specified, all available space will be used.
##### Keyword "uuid"
Optional String. UUID for the partition. Only<br>used if the partition table type for the block device is GPT.
##### Keyword "bootable"
Optional Boolean. If the partition should be<br>marked bootable.


Note: This command accepts JSON.


List partitions

```bash
maas $PROFILE partitions read [--help] [-d] [-k] system_id device_id

```

#### **Positional arguments**
| Argument | Effect |
|---|---|
| system_id | The system ID of the machine/device (e.g., `abc123`) |
| device_id | The device_id parameter |


#### **Command-line options**
| Option | Effect |
|---|---|
| --help, -h | Show this help message and exit. |
| -d, --debug | Display more information about API responses. |
| -k, --insecure | Disable SSL certificate check. |


#### **Keywords**
List partitions on a device with the given system_id and<br>device_id.
