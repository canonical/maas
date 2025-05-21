Enter keyword arguments in the form `key=value`.

## Delete a bcache set

```bash
maas $PROFILE bcache-cache-set delete [--help] [-d] [-k] system_id id [data ...]
```

#### Positional arguments
- system_id
- id

Delete bcache cache set on a machine.

#### Command-line options
| Option | Effect |
|-----|-----|
| --help, -h | Show this help message and exit. |
| -d, --debug | Display more information about API responses. |
| -k, --insecure | Disable SSL certificate check |

## Read a bcache cache set

```bash
maas $PROFILE bcache-cache-set read [--help] [-d] [-k] system_id id [data ...]
```

#### Positional arguments
- system_id
- id

Read bcache cache set on a machine.

#### Command-line options
| Option | Effect |
|-----|-----|
| --help, -h | Show this help message and exit. |
| -d, --debug | Display more information about API responses. |
| -k, --insecure | Disable SSL certificate check |

## Update a bcache set

```bash
maas $PROFILE bcache-cache-set update [--help] [-d] [-k] system_id id [data ...]
```

#### Positional arguments
- system_id
- id


Update bcache cache set on a machine.

Note: specifying both a cache_device and a cache_partition is not allowed.

#### Keyword "cache_device"
Optional String. Cache block device to replace current one.

#### Keyword "cache_partition"
Optional String. Cache partition to replace current one.

#### Command-line options
| Option | Effect |
|-----|-----|
| --help, -h | Show this help message and exit. |
| -d, --debug | Display more information about API responses. |
| -k, --insecure | Disable SSL certificate check |

## Creates a bcache cache set

```bash
maas $PROFILE bcache-cache-sets create [--help] [-d] [-k] system_id [data ...]
```

#### Positional arguments
- system_id


Creates a bcache cache set.

Note: specifying both a cache_device and a cache_partition is not allowed.

#### Keyword "cache_device"
Optional String. Cache block device.

#### Keyword "cache_partition"
Optional String. Cache partition.

#### Command-line options
| Option | Effect |
|-----|-----|
| --help, -h | Show this help message and exit. |
| -d, --debug | Display more information about API responses. |
| -k, --insecure | Disable SSL certificate check |

## List bcache sets

```bash
maas $PROFILE bcache-cache-sets read [--help] [-d] [-k] system_id [data ...]
```

#### Positional arguments
- system_id

List all bcache cache sets belonging to a machine.

#### Command-line options
| Option | Effect |
|-----|-----|
| --help, -h | Show this help message and exit. |
| -d, --debug | Display more information about API responses. |
| -k, --insecure | Disable SSL certificate check |

