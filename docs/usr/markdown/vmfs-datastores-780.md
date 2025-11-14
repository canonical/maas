Delete the specified VMFS datastore.

```bash
maas $PROFILE vmfs-datastore delete [--help] [-d] [-k] system_id id

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
Delete a VMFS datastore with the given id from the machine<br>with the given system_id.





Read a VMFS datastore.

```bash
maas $PROFILE vmfs-datastore read [--help] [-d] [-k] system_id id

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
Read a VMFS datastore with the given id on the machine<br>with the given system_id.





Update a VMFS datastore.

```bash
maas $PROFILE vmfs-datastore update [--help] [-d] [-k] system_id id [data ...]

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
Update a VMFS datastore with the given id on the machine<br>with the given system_id.

##### Keyword "name"
Optional String. Name of the VMFS datastore.
##### Keyword "uuid"
Optional String. UUID of the VMFS datastore.
##### Keyword "add_block_devices"
Optional String. Block devices to<br>add to the VMFS datastore.
##### Keyword "add_partitions"
Optional String. Partitions to add to<br>the VMFS datastore.
##### Keyword "remove_partitions"
Optional String. Partitions to<br>remove from the VMFS datastore.


Note: This command accepts JSON.


Create a VMFS datastore.

```bash
maas $PROFILE vmfs-datastores create [--help] [-d] [-k] system_id [data ...]

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
Create a VMFS datastore belonging to a machine with the<br>given system_id. Note that at least one valid block device or partition is required.

##### Keyword "name"
Optional String. Name of the VMFS datastore.
##### Keyword "uuid"
Optional String. (optional) UUID of the VMFS<br>group.
##### Keyword "block_devices"
Optional String. Block devices to add<br>to the VMFS datastore.
##### Keyword "partitions"
Optional String. Partitions to add to the<br>VMFS datastore.


Note: This command accepts JSON.


List all VMFS datastores.

```bash
maas $PROFILE vmfs-datastores read [--help] [-d] [-k] system_id

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
List all VMFS datastores belonging to a machine with the<br>given system_id.
