Delete a bcache

```bash
maas $PROFILE bcache delete [--help] [-d] [-k] system_id id

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
Delete bcache on a machine.





Read a bcache device

```bash
maas $PROFILE bcache read [--help] [-d] [-k] system_id id

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
Read bcache device on a machine.





Update a bcache

```bash
maas $PROFILE bcache update [--help] [-d] [-k] system_id id [data ...]

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
Update bcache on a machine. Specifying both a device and a partition for a given role (cache or<br>backing) is not allowed.

##### Keyword "name"
Optional String. Name of the Bcache.
##### Keyword "uuid"
Optional String. UUID of the Bcache.
##### Keyword "cache_set"
Optional String. Cache set to replace<br>current one.
##### Keyword "backing_device"
Optional String. Backing block device<br>to replace current one.
##### Keyword "backing_partition"
Optional String. Backing partition<br>to replace current one.
##### Keyword "cache_mode"
Optional String. Cache mode:<br>``WRITEBACK``, ``WRITETHROUGH``, ``WRITEAROUND``.


Note: This command accepts JSON.


Creates a bcache

```bash
maas $PROFILE bcaches create [--help] [-d] [-k] system_id [data ...]

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
Creates a bcache. Specifying both a device and a partition for a given role (cache or<br>backing) is not allowed.

##### Keyword "name"
Optional String. Name of the Bcache.
##### Keyword "uuid"
Optional String. UUID of the Bcache.
##### Keyword "cache_set"
Optional String. Cache set.
##### Keyword "backing_device"
Optional String. Backing block device.
##### Keyword "backing_partition"
Optional String. Backing partition.
##### Keyword "cache_mode"
Optional String. Cache mode:<br>``WRITEBACK``, ``WRITETHROUGH``, ``WRITEAROUND``.


Note: This command accepts JSON.


List all bcache devices

```bash
maas $PROFILE bcaches read [--help] [-d] [-k] system_id

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
List all bcache devices belonging to a<br>machine.
