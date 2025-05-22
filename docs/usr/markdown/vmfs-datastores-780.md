Enter keyword arguments in the form `key=value`.

## Delete the specified VMFS datastore.

```bash
maas $PROFILE vmfs-datastore delete [--help] [-d] [-k] system_id id [data ...]
```

#### Positional arguments
- system_id
- id

Delete a VMFS datastore with the given id from the machine with the given system_id.

#### Command-line options
| Option         | Effect                                        |
|----------------|-----------------------------------------------|
| --help, -h     | Show this help message and exit|
| -d, --debug    | Display more information about API responses|
| -k, --insecure | Disable SSL certificate check                 |

## Read a VMFS datastore.

```bash
maas $PROFILE vmfs-datastore read [--help] [-d] [-k] system_id id [data ...]
```

#### Positional arguments
- system_id
- id

Read a VMFS datastore with the given id on the machine with the given system_id.

#### Command-line options
| Option | Effect |
|-----|-----|
| --help, -h | Show this help message and exit|
| -d, --debug | Display more information about API responses|
| -k, --insecure | Disable SSL certificate check |

## Update a VMFS datastore.

```bash
maas $PROFILE vmfs-datastore update [--help] [-d] [-k] system_id id [data ...]
```

#### Positional arguments
- system_id
- id


Update a VMFS datastore with the given id on the machine with the given system_id.

#### Keyword "name"
Optional String. Name of the VMFS datastore.

#### Keyword "uuid"
Optional String. UUID of the VMFS datastore.

#### Keyword "add_block_devices"
Optional String. Block devices to add to the VMFS datastore.

#### Keyword "add_partitions"
Optional String. Partitions to add to the VMFS datastore.

#### Keyword "remove_partitions"
Optional String. Partitions to remove from the VMFS datastore.

#### Command-line options
| Option | Effect |
|-----|-----|
| --help, -h | Show this help message and exit|
| -d, --debug | Display more information about API responses|
| -k, --insecure | Disable SSL certificate check |

## Create a VMFS datastore.

```bash
maas $PROFILE vmfs-datastores create [--help] [-d] [-k] system_id [data ...]
```

#### Positional arguments
- system_id


Create a VMFS datastore belonging to a machine with the given system_id.

Note that at least one valid block device or partition is required.

#### Keyword "name"
Required String. Name of the VMFS datastore.

#### Keyword "uuid"
Optional String. (optional) UUID of the VMFS group.

#### Keyword "block_devices"
Optional String. Block devices to add to the VMFS datastore.

#### Keyword "partitions"
Optional String. Partitions to add to the VMFS datastore.

#### Command-line options
| Option | Effect |
|-----|-----|
| --help, -h | Show this help message and exit|
| -d, --debug | Display more information about API responses|
| -k, --insecure | Disable SSL certificate check |

## List all VMFS datastores.

```bash
maas $PROFILE vmfs-datastores read [--help] [-d] [-k] system_id [data ...]
```

#### Positional arguments
- system_id

List all VMFS datastores belonging to a machine with the given system_id.

#### Command-line options
| Option         | Effect                                       |
|----------------|----------------------------------------------|
| --help, -h     | Show this help message and exit              |
| -d, --debug    | Display more information about API responses |
| -k, --insecure | Disable SSL certificate check                |

