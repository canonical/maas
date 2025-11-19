Create a logical volume

```bash
maas $PROFILE volume-group create-logical-volume [--help] [-d] [-k] system_id id [data ...]

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
Create a logical volume in the volume group with the given<br>id on the machine with the given system_id.

##### Keyword "name"
Optional String. Name of the logical volume.
##### Keyword "uuid"
Optional String. (optional) UUID of the logical<br>volume.
##### Keyword "size"
Optional String. (optional) Size of the logical<br>volume. Must be larger than or equal to 4,194,304 bytes. E.g. ``4194304``. Will default to free space in the volume group if not given.


Note: This command accepts JSON.


Delete volume group

```bash
maas $PROFILE volume-group delete [--help] [-d] [-k] system_id id

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
Delete a volume group with the given id from the machine<br>with the given system_id.





Delete a logical volume

```bash
maas $PROFILE volume-group delete-logical-volume [--help] [-d] [-k] system_id id [data ...]

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
Delete a logical volume in the volume group with the given<br>id on the machine with the given system_id. Note: this operation returns HTTP status code 204 even if the logical<br>volume id does not exist.

##### Keyword "id"
Optional Int. The logical volume id.


Note: This command accepts JSON.


Read a volume group

```bash
maas $PROFILE volume-group read [--help] [-d] [-k] system_id id

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
Read a volume group with the given id on the machine with<br>the given system_id.





Update a volume group

```bash
maas $PROFILE volume-group update [--help] [-d] [-k] system_id id [data ...]

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
Update a volume group with the given id on the machine<br>with the given system_id.

##### Keyword "name"
Optional String. Name of the volume group.
##### Keyword "uuid"
Optional String. UUID of the volume group.
##### Keyword "add_block_devices"
Optional String. Block devices to<br>add to the volume group.
##### Keyword "remove_block_devices"
Optional String. Block devices<br>to remove from the volume group.
##### Keyword "add_partitions"
Optional String. Partitions to add to<br>the volume group.
##### Keyword "remove_partitions"
Optional String. Partitions to<br>remove from the volume group.


Note: This command accepts JSON.


Create a volume group

```bash
maas $PROFILE volume-groups create [--help] [-d] [-k] system_id [data ...]

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
Create a volume group belonging to a machine with the<br>given system_id. Note that at least one valid block device or partition is required.

##### Keyword "name"
Optional String. Name of the volume group.
##### Keyword "uuid"
Optional String. (optional) UUID of the volume<br>group.
##### Keyword "block_devices"
Optional String. Block devices to add<br>to the volume group.
##### Keyword "partitions"
Optional String. Partitions to add to the<br>volume group.


Note: This command accepts JSON.


List all volume groups

```bash
maas $PROFILE volume-groups read [--help] [-d] [-k] system_id

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
List all volume groups belonging to a machine with the<br>given system_id.
