Enter keyword arguments in the form `key=value`.

## Create a package repository

```bash
maas $PROFILE package-repositories create [--help] [-d] [-k] [data ...] 
```

Create a new package repository.

#### Keyword "name"
Required String. The name of the package repository.

#### Keyword "url"
Required String. The url of the package repository.

#### Keyword "distributions"
Optional String. Which package distributions to include.

#### Keyword "disabled_pockets"
Optional String. The list of pockets to disable.

#### Keyword "disabled_components"
Optional String.  The list of components to disable. Only applicable to the default Ubuntu repositories.

#### Keyword "components"
Optional String. The list of components to enable. Only applicable to custom repositories.

#### Keyword "arches"
Optional String. The list of supported architectures.

#### Keyword "key"
Optional String. The authentication key to use with the repository.

#### Keyword "disable_sources"
Optional Boolean. Disable deb-src lines.

#### Keyword "enabled"
Optional Boolean. Whether or not the repository is enabled.

#### Command-line options
| Option         | Effect                                        |
|----------------|-----------------------------------------------|
| --help, -h     | Show this help message and exit.              |
| -d, --debug    | Display more information about API responses. |
| -k, --insecure | Disable SSL certificate check                 |

## List package repositories

```bash
maas $PROFILE package-repositories read [--help] [-d] [-k] [data ...] 
```

List all available package repositories. 

#### Command-line options
| Option         | Effect                                        |
|----------------|-----------------------------------------------|
| --help, -h     | Show this help message and exit.              |
| -d, --debug    | Display more information about API responses. |
| -k, --insecure | Disable SSL certificate check                 |

## Delete a package repository

```bash
maas $PROFILE package-repository delete [--help] [-d] [-k] id [data ...]
```

#### Positional arguments
- id

Delete a package repository with the given id.

#### Command-line options
| Option         | Effect                                        |
|----------------|-----------------------------------------------|
| --help, -h     | Show this help message and exit.              |
| -d, --debug    | Display more information about API responses. |
| -k, --insecure | Disable SSL certificate check                 |

## Read a package repository

```bash
maas $PROFILE package-repository read [--help] [-d] [-k] id [data ...] 
```

#### Positional arguments
- id

Read a package repository with the given id.

#### Command-line options
| Option         | Effect                                        |
|----------------|-----------------------------------------------|
| --help, -h     | Show this help message and exit.              |
| -d, --debug    | Display more information about API responses. |
| -k, --insecure | Disable SSL certificate check                 |

## Update a package repository

```bash
maas $PROFILE package-repository update [--help] [-d] [-k] id [data ...]
```

#### Positional arguments
- id


Update the package repository with the given id.

#### Keyword "name"
Optional String. The name of the package repository.

#### Keyword "url"
Optional String. The url of the package repository.

#### Keyword "distributions"
Optional String. Which package distributions to include.

#### Keyword "disabled_pockets"
Optional String. The list of pockets to disable.

#### Keyword "disabled_components"
Optional String.  The list of components to disable. Only applicable to the default Ubuntu repositories.

#### Keyword "components"
Optional String. The list of components to enable. Only applicable to custom repositories.

#### Keyword "arches"
Optional String. The list of supported architectures.

#### Keyword "key"
Optional String. The authentication key to use with the repository.

#### Keyword "disable_sources"
Optional Boolean. Disable deb-src lines.

#### Keyword "enabled"
Optional Boolean. Whether or not the repository is enabled.

#### Command-line options
| Option         | Effect                                        |
|----------------|-----------------------------------------------|
| --help, -h     | Show this help message and exit.              |
| -d, --debug    | Display more information about API responses. |
| -k, --insecure | Disable SSL certificate check                 |

## Delete a package repository

```bash
maas $PROFILE package-repository delete [--help] [-d] [-k] id [data ...]
```

#### Positional arguments
- id

Delete a package repository with the given id.

#### Command-line options
| Option         | Effect                                        |
|----------------|-----------------------------------------------|
| --help, -h     | Show this help message and exit.              |
| -d, --debug    | Display more information about API responses. |
| -k, --insecure | Disable SSL certificate check                 |

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

