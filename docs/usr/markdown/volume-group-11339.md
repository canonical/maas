Enter keyword arguments in the form `key=value`.

## [data ...]

```bash
maas $PROFILE volume-group create-logical-volume [--help] [-d] [-k] system_id id
```

Create a logical volume 

#### Positional arguments
- system_id
- id


Create a logical volume in the volume group with the given id on the machine with the given system_id.

#### Keyword "name"
Required String. Name of the logical volume.

#### Keyword "uuid"
Optional String. (optional) UUID of the logical volume.

#### Keyword "size"
Optional String. (optional) Size of the logical volume. Must be larger than or equal to 4,194,304 bytes. E.g. ``4194304``. Will default to free space in the volume group if not given.

#### Command-line options
| Option | Effect |
|-----|-----|
| --help, -h | Show this help message and exit. |
| -d, --debug | Display more information about API responses. |
| -k, --insecure | Disable SSL certificate check |

## Delete volume group

```bash
maas $PROFILE volume-group delete [--help] [-d] [-k] system_id id [data ...]
```

#### Positional arguments
- system_id
- id

Delete a volume group with the given id from the machine with the given system_id.

#### Command-line options
| Option | Effect |
|-----|-----|
| --help, -h | Show this help message and exit. |
| -d, --debug | Display more information about API responses. |
| -k, --insecure | Disable SSL certificate check |

## [data ...]

```bash
maas $PROFILE volume-group delete-logical-volume [--help] [-d] [-k] system_id id
```

Delete a logical volume 

#### Positional arguments
- system_id
- id


Delete a logical volume in the volume group with the given id on the machine with the given system_id.

Note: this operation returns HTTP status code 204 even if the logical volume id does not exist.

#### Keyword "id"
Required Int. The logical volume id.

#### Command-line options
| Option | Effect |
|-----|-----|
| --help, -h | Show this help message and exit. |
| -d, --debug | Display more information about API responses. |
| -k, --insecure | Disable SSL certificate check |

## Read a volume group

```bash
maas $PROFILE volume-group read [--help] [-d] [-k] system_id id [data ...]
```

#### Positional arguments
- system_id
- id

Read a volume group with the given id on the machine with the given system_id.

#### Command-line options
| Option | Effect |
|-----|-----|
| --help, -h | Show this help message and exit. |
| -d, --debug | Display more information about API responses. |
| -k, --insecure | Disable SSL certificate check |

## Update a volume group

```bash
maas $PROFILE volume-group update [--help] [-d] [-k] system_id id [data ...]
```

#### Positional arguments
- system_id
- id


Update a volume group with the given id on the machine with the given system_id.

#### Keyword "name"
Optional String. Name of the volume group.

#### Keyword "uuid"
Optional String. UUID of the volume group.

#### Keyword "add_block_devices"
Optional String. Block devices to add to the volume group.

#### Keyword "remove_block_devices"
Optional String. Block devices to remove from the volume group.

#### Keyword "add_partitions"
Optional String. Partitions to add to the volume group.

#### Keyword "remove_partitions"
Optional String. Partitions to remove from the volume group.

#### Command-line options
| Option | Effect |
|-----|-----|
| --help, -h | Show this help message and exit. |
| -d, --debug | Display more information about API responses. |
| -k, --insecure | Disable SSL certificate check |

## Create a volume group

```bash
maas $PROFILE volume-groups create [--help] [-d] [-k] system_id [data ...]
```

#### Positional arguments
- system_id


Create a volume group belonging to a machine with the given system_id.

Note that at least one valid block device or partition is required.

#### Keyword "name"
Required String. Name of the volume group.

#### Keyword "uuid"
Optional String. (optional) UUID of the volume group.

#### Keyword "block_devices"
Optional String. Block devices to add to the volume group.

#### Keyword "partitions"
Optional String. Partitions to add to the volume group.

#### Command-line options
| Option | Effect |
|-----|-----|
| --help, -h | Show this help message and exit. |
| -d, --debug | Display more information about API responses. |
| -k, --insecure | Disable SSL certificate check |

## List all volume groups

```bash
maas $PROFILE volume-groups read [--help] [-d] [-k] system_id [data ...]
```

#### Positional arguments
- system_id

List all volume groups belonging to a machine with the given system_id.

#### Command-line options
| Option | Effect |
|-----|-----|
| --help, -h | Show this help message and exit. |
| -d, --debug | Display more information about API responses. |
| -k, --insecure | Disable SSL certificate check |
