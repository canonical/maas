Delete a bcache set

```bash
maas $PROFILE bcache-cache-set delete [--help] [-d] [-k] system_id id

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
Delete bcache cache set on a machine.





Read a bcache cache set

```bash
maas $PROFILE bcache-cache-set read [--help] [-d] [-k] system_id id

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
Read bcache cache set on a machine.





Update a bcache set

```bash
maas $PROFILE bcache-cache-set update [--help] [-d] [-k] system_id id [data ...]

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
Update bcache cache set on a machine. Note: specifying both a cache_device and a cache_partition is not<br>allowed.

##### Keyword "cache_device"
Optional String. Cache block device to<br>replace current one.
##### Keyword "cache_partition"
Optional String. Cache partition to<br>replace current one.


Note: This command accepts JSON.


Creates a bcache cache set

```bash
maas $PROFILE bcache-cache-sets create [--help] [-d] [-k] system_id [data ...]

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
Creates a bcache cache set. Note: specifying both a cache_device and a cache_partition is not<br>allowed.

##### Keyword "cache_device"
Optional String. Cache block device.
##### Keyword "cache_partition"
Optional String. Cache partition.


Note: This command accepts JSON.


List bcache sets

```bash
maas $PROFILE bcache-cache-sets read [--help] [-d] [-k] system_id

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
List all bcache cache sets belonging to a machine.
