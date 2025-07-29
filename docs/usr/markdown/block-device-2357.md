Enter keyword arguments in the form `key=value`.

## Add a tag

```bash
maas $PROFILE block-device add-tag [--help] [-d] [-k] system_id id [data ...]
```

#### Positional arguments
- system_id
- id


Add a tag to block device on a given machine.

#### Keyword "tag"
Required String. The tag being added.

#### Command-line options
| Option | Effect |
|-----|-----|
| --help, -h | Show this help message and exit. |
| -d, --debug | Display more information about API responses. |
| -k, --insecure | Disable SSL certificate check |

## Delete a block device

```bash
maas $PROFILE block-device delete [--help] [-d] [-k] system_id id [data ...]
```

#### Positional arguments
- system_id
- id

Delete block device on a given machine.

#### Command-line options
| Option | Effect |
|-----|-----|
| --help, -h | Show this help message and exit. |
| -d, --debug | Display more information about API responses. |
| -k, --insecure | Disable SSL certificate check |

## Format block device

```bash
maas $PROFILE block-device format [--help] [-d] [-k] system_id id [data ...]
```

#### Positional arguments
- system_id
- id


Format block device with filesystem.

#### Keyword "fstype"
Required String. Type of filesystem.

#### Keyword "uuid"
Optional String. UUID of the filesystem.

#### Command-line options
| Option | Effect |
|-----|-----|
| --help, -h | Show this help message and exit. |
| -d, --debug | Display more information about API responses. |
| -k, --insecure | Disable SSL certificate check |

## Mount a filesystem

```bash
maas $PROFILE block-device mount [--help] [-d] [-k] system_id id [data ...]
```

#### Positional arguments
- system_id
- id


Mount the filesystem on block device.

#### Keyword "mount_point"
Required String. Path on the filesystem to mount.

#### Keyword "mount_options"
Optional String. Options to pass to mount(8).

#### Command-line options
| Option | Effect |
|-----|-----|
| --help, -h | Show this help message and exit. |
| -d, --debug | Display more information about API responses. |
| -k, --insecure | Disable SSL certificate check |

## Read a block device

```bash
maas $PROFILE block-device read [--help] [-d] [-k] system_id id [data ...]
```

#### Positional arguments
- system_id
- id

Read a block device on a given machine.

#### Command-line options
| Option | Effect |
|-----|-----|
| --help, -h | Show this help message and exit. |
| -d, --debug | Display more information about API responses. |
| -k, --insecure | Disable SSL certificate check |

## Remove a tag

```bash
maas $PROFILE block-device remove-tag [--help] [-d] [-k] system_id id [data ...]
```

#### Positional arguments
- system_id
- id


Remove a tag from block device on a given machine.

#### Keyword "tag"
Optional String. The tag being removed.

#### Command-line options
| Option | Effect |
|-----|-----|
| --help, -h | Show this help message and exit. |
| -d, --debug | Display more information about API responses. |
| -k, --insecure | Disable SSL certificate check |

## Set boot disk

```bash
maas $PROFILE block-device set-boot-disk [--help] [-d] [-k] system_id id [data ...]
```

#### Positional arguments
- system_id
- id

Set a block device as the boot disk for the machine.

#### Command-line options
| Option | Effect |
|-----|-----|
| --help, -h | Show this help message and exit. |
| -d, --debug | Display more information about API responses. |
| -k, --insecure | Disable SSL certificate check |

## Unformat a block device

```bash
maas $PROFILE block-device unformat [--help] [-d] [-k] system_id id [data ...]
```

#### Positional arguments
- system_id
- id

Unformat a previously formatted block device.

#### Command-line options
| Option | Effect |
|-----|-----|
| --help, -h | Show this help message and exit. |
| -d, --debug | Display more information about API responses. |
| -k, --insecure | Disable SSL certificate check |

## Unmount a filesystem

```bash
maas $PROFILE block-device unmount [--help] [-d] [-k] system_id id [data ...]
```

#### Positional arguments
- system_id
- id

Unmount the filesystem on block device.

#### Command-line options
| Option | Effect |
|-----|-----|
| --help, -h | Show this help message and exit. |
| -d, --debug | Display more information about API responses. |
| -k, --insecure | Disable SSL certificate check |

## Update a block device

```bash
maas $PROFILE block-device update [--help] [-d] [-k] system_id id [data ...]
```

#### Positional arguments
- system_id
- id


Update block device on a given machine.

Machines must have a status of Ready to have access to all options. Machines with Deployed status can only have the name, model, serial, and/or id_path updated for a block device. This is intented to allow a bad block device to be replaced while the machine remains deployed.

#### Keyword "name"
Optional String. (Physical devices) Name of the block device.

#### Keyword "model"
Optional String. (Physical devices) Model of the block device.

#### Keyword "serial"
Optional String. (Physical devices) Serial number of the block device.

#### Keyword "id_path"
Optional String (physical device). Only used if model and serial cannot be provided. This should be a path that is fixed and doesn't change depending on the boot order or kernel version.

#### Keyword "size"
Optional String. (Physical devices) Size of the block device.

#### Keyword "block_size"
Optional String. (Physical devices) Block size of the block device.

#### Keyword "name"
Optional String. (Virtual devices) Name of the block device.

#### Keyword "uuid"
Optional String. (Virtual devices) UUID of the block device.

#### Keyword "size"
Optional String. (Virtual devices) Size of the block device. (Only allowed for logical volumes.)

#### Command-line options
| Option | Effect |
|-----|-----|
| --help, -h | Show this help message and exit. |
| -d, --debug | Display more information about API responses. |
| -k, --insecure | Disable SSL certificate check |

## Create a block device

```bash
maas $PROFILE block-devices create [--help] [-d] [-k] system_id [data ...]
```

#### Positional arguments
- system_id


Create a physical block device.

#### Keyword "name"
Required String. Name of the block device.

#### Keyword "model"
Optional String. Model of the block device.

#### Keyword "serial"
Optional String. Serial number of the block device.

#### Keyword "id_path"
Optional String.  Only used if model and serial cannot be provided. This should be a path that is fixed and doesn't change depending on the boot order or kernel version.

#### Keyword "size"
Required String. Size of the block device.

#### Keyword "block_size"
Required String. Block size of the block device.

#### Command-line options
| Option | Effect |
|-----|-----|
| --help, -h | Show this help message and exit. |
| -d, --debug | Display more information about API responses. |
| -k, --insecure | Disable SSL certificate check |

## List block devices

```bash
maas $PROFILE block-devices read [--help] [-d] [-k] system_id [data ...]
```

#### Positional arguments
- system_id

List all block devices belonging to a machine.

#### Command-line options
| Option | Effect |
|-----|-----|
| --help, -h | Show this help message and exit. |
| -d, --debug | Display more information about API responses. |
| -k, --insecure | Disable SSL certificate check |
