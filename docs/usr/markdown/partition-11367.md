Enter keyword arguments in the form `key=value`.

## Create a partition

```bash
maas $PROFILE partitions create [--help] [-d] [-k] system_id device_id [data ...]
```

#### Positional arguments
- system_id
- device_id


Create a partition on a block device.

#### Keyword "size"
Optional Int. The size of the partition in bytes. If not specified, all available space will be used.

#### Keyword "uuid"
Optional String. UUID for the partition. Only used if the partition table type for the block device is GPT.

#### Keyword "bootable"
Optional Boolean. If the partition should be marked bootable.

#### Command-line options
| Option         | Effect                                        |
|----------------|-----------------------------------------------|
| --help, -h     | Show this help message and exit              |
| -d, --debug    | Display more information about API responses |
| -k, --insecure | Disable SSL certificate check                 |

## List partitions

```bash
maas $PROFILE partitions read [--help] [-d] [-k] system_id device_id [data ...]
```

#### Positional arguments
- system_id
- device_id

List partitions on a device with the given system_id and device_id.

#### Command-line options
| Option         | Effect                                       |
|----------------|----------------------------------------------|
| --help, -h     | Show this help message and exit              |
| -d, --debug    | Display more information about API responses |
| -k, --insecure | Disable SSL certificate check                |

