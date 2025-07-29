Enter keyword arguments in the form `key=value`.

## Delete a bcache

```bash
maas $PROFILE bcache delete [--help] [-d] [-k] system_id id [data ...] 
```

### Positional arguments
- system_id
- id

Delete bcache on a machine.

#### Command-line options
| Option | Effect |
|-----|-----|
| --help, -h | Show this help message and exit. |
| -d, --debug | Display more information about API responses. |
| -k, --insecure | Disable SSL certificate check |

## Read a bcache device

```bash
maas $PROFILE bcache read [--help] [-d] [-k] system_id id [data ...] 
```

### Positional arguments
- system_id
- id

Read bcache device on a machine.

#### Command-line options
| Option | Effect |
|-----|-----|
| --help, -h | Show this help message and exit. |
| -d, --debug | Display more information about API responses. |
| -k, --insecure | Disable SSL certificate check |

## Update a bcache

```bash
maas $PROFILE bcache update [--help] [-d] [-k] system_id id [data ...] 
```

#### Positional arguments
- system_id
- id


Update bcache on a machine.

Specifying both a device and a partition for a given role (cache or backing) is not allowed.

#### Keyword "name"
Optional String. Name of the Bcache.

#### Keyword "uuid"
Optional String. UUID of the Bcache.

#### Keyword "cache_set"
Optional String. Cache set to replace current one.

#### Keyword "backing_device"
Optional String. Backing block device to replace current one.

#### Keyword "backing_partition"
Optional String. Backing partition to replace current one.

#### Keyword "cache_mode"
Optional String. Cache mode: ``WRITEBACK``, ``WRITETHROUGH``, ``WRITEAROUND``.

#### Command-line options
| Option | Effect |
|-----|-----|
| --help, -h | Show this help message and exit. |
| -d, --debug | Display more information about API responses. |
| -k, --insecure | Disable SSL certificate check |

## Creates a bcache

```bash
maas $PROFILE bcaches create [--help] [-d] [-k] system_id [data ...] 
```

#### Positional arguments
- system_id


Creates a bcache.

Specifying both a device and a partition for a given role (cache or backing) is not allowed.

#### Keyword "name"
Optional String. Name of the Bcache.

#### Keyword "uuid"
Optional String. UUID of the Bcache.

#### Keyword "cache_set"
Optional String. Cache set.

#### Keyword "backing_device"
Optional String. Backing block device.

#### Keyword "backing_partition"
Optional String. Backing partition.

#### Keyword "cache_mode"
Optional String. Cache mode: ``WRITEBACK``, ``WRITETHROUGH``, ``WRITEAROUND``.

#### Command-line options
| Option | Effect |
|-----|-----|
| --help, -h | Show this help message and exit. |
| -d, --debug | Display more information about API responses. |
| -k, --insecure | Disable SSL certificate check |

## Creates a bcache

```bash
maas $PROFILE bcaches create [--help] [-d] [-k] system_id [data ...] 
```

#### Positional arguments
- system_id


Creates a bcache.

Specifying both a device and a partition for a given role (cache or backing) is not allowed.

#### Keyword "name"
Optional String. Name of the Bcache.

#### Keyword "uuid"
Optional String. UUID of the Bcache.

#### Keyword "cache_set"
Optional String. Cache set.

#### Keyword "backing_device"
Optional String. Backing block device.

#### Keyword "backing_partition"
Optional String. Backing partition.

#### Keyword "cache_mode"
Optional String. Cache mode: ``WRITEBACK``, ``WRITETHROUGH``, ``WRITEAROUND``.

#### Command-line options
| Option | Effect |
|-----|-----|
| --help, -h | Show this help message and exit. |
| -d, --debug | Display more information about API responses. |
| -k, --insecure | Disable SSL certificate check |
