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


## Format a partition

```bash
maas $PROFILE partition format [--help] [-d] [-k] system_id device_id id [data ...]
```

#### Positional arguments
- system_id
- device_id
- id


Format the partition on machine system_id and device device_id with the given partition id.

#### Keyword "fstype"
Required String. Type of filesystem.

#### Keyword "uuid"
Optional String. The UUID for the filesystem.

#### Keyword "label"
Optional String. The label for the filesystem.

#### Command-line options
| Option         | Effect                                        |
|----------------|-----------------------------------------------|
| --help, -h     | Show this help message and exit.              |
| -d, --debug    | Display more information about API responses. |
| -k, --insecure | Disable SSL certificate check                 |

## Mount a filesystem

```bash
maas $PROFILE partition mount [--help] [-d] [-k] system_id device_id id [data ...]
```

#### Positional arguments
- system_id
- device_id
- id


Mount a filesystem on machine system_id, device device_id and partition id.

#### Keyword "mount_point"
Required String. Path on the filesystem to mount.

#### Keyword "mount_options"
Optional String. Options to pass to mount(8).

#### Command-line options
| Option         | Effect                                        |
|----------------|-----------------------------------------------|
| --help, -h     | Show this help message and exit.              |
| -d, --debug    | Display more information about API responses. |
| -k, --insecure | Disable SSL certificate check                 |

## Read a partition

```bash
maas $PROFILE partition read [--help] [-d] [-k] system_id device_id id [data ...]
```

#### Positional arguments
- system_id
- device_id
- id

Read the partition from machine system_id and device device_id with the given partition id.

#### Command-line options
| Option | Effect |
|-----|-----|
| --help, -h | Show this help message and exit. |
| -d, --debug | Display more information about API responses. |
| -k, --insecure | Disable SSL certificate check |

## Remove a tag

```bash
maas $PROFILE partition remove-tag [--help] [-d] [-k] system_id device_id id [data ...]
```

#### Positional arguments
- system_id
- device_id
- id


Remove a tag from a partition on machine system_id, device device_id and partition id.

#### Keyword "tag"
Required String. The tag being removed.

#### Command-line options
| Option         | Effect                                        |
|----------------|-----------------------------------------------|
| --help, -h     | Show this help message and exit.              |
| -d, --debug    | Display more information about API responses. |
| -k, --insecure | Disable SSL certificate check                 |
|                |                                               |

## Unformat a partition

```bash
maas $PROFILE partition unformat [--help] [-d] [-k] system_id device_id id [data ...]
```

#### Positional arguments
- system_id
- device_id
- id

Unformat the partition on machine system_id and device device_id with the given partition id.

#### Command-line options
| Option         | Effect                                        |
|----------------|-----------------------------------------------|
| --help, -h     | Show this help message and exit.              |
| -d, --debug    | Display more information about API responses. |
| -k, --insecure | Disable SSL certificate check                 |

## Unmount a filesystem

```bash
maas $PROFILE partition unmount [--help] [-d] [-k] system_id device_id id [data ...]
```

#### Positional arguments
- system_id
- device_id
- id

Unmount a filesystem on machine system_id, device device_id and partition id.

#### Command-line options
| Option         | Effect                                        |
|----------------|-----------------------------------------------|
| --help, -h     | Show this help message and exit.              |
| -d, --debug    | Display more information about API responses. |
| -k, --insecure | Disable SSL certificate check                 |
