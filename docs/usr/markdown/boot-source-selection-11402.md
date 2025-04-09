Enter keyword arguments in the form `key=value`.

## Delete a boot source

```bash
maas $PROFILE boot-source-selection delete [--help] [-d] [-k] boot_source_id id [data ...]
```

#### Positional arguments
- boot_source_id
- id

Delete a boot source with the given id.

#### Command-line options
| Option | Effect |
|-----|-----|
| --help, -h | Show this help message and exit. |
| -d, --debug | Display more information about API responses. |
| -k, --insecure | Disable SSL certificate check |

## Read a boot source selection

```bash
maas $PROFILE boot-source-selection read [--help] [-d] [-k] boot_source_id id [data ...]
```

#### Positional arguments
- boot_source_id
- id

Read a boot source selection with the given id.

#### Command-line options
| Option | Effect |
|-----|-----|
| --help, -h | Show this help message and exit. |
| -d, --debug | Display more information about API responses. |
| -k, --insecure | Disable SSL certificate check |

## Update a boot-source selection

```bash
maas $PROFILE boot-source-selection update [--help] [-d] [-k] boot_source_id id [data ...]
```

#### Positional arguments
- boot_source_id
- id


Update a boot source selection with the given id.

#### Keyword "os"
Optional String. The OS (e.g. ubuntu, centos) for which to import resources.

#### Keyword "release"
Optional String. The release for which to import resources.

#### Keyword "arches"
Optional String. The list of architectures for which to import resources.

#### Keyword "subarches"
Optional String. The list of sub-architectures for which to import resources.

#### Keyword "labels"
Optional String. The list of labels for which to import resources.

#### Command-line options
| Option | Effect |
|-----|-----|
| --help, -h | Show this help message and exit. |
| -d, --debug | Display more information about API responses. |
| -k, --insecure | Disable SSL certificate check |

## Create a boot-source selection

```bash
maas $PROFILE boot-source-selections create [--help] [-d] [-k] boot_source_id [data ...]
```

#### Positional arguments
- boot_source_id


Create a new boot source selection.

#### Keyword "os"
Optional String. The OS (e.g. ubuntu, centos) for which to import resources.

#### Keyword "release"
Optional String. The release for which to import resources.

#### Keyword "arches"
Optional String. The architecture list for which to import resources.

#### Keyword "subarches"
Optional String. The subarchitecture list for which to import resources.

#### Keyword "labels"
Optional String. The label lists for which to import resources.

#### Command-line options
| Option | Effect |
|-----|-----|
| --help, -h | Show this help message and exit. |
| -d, --debug | Display more information about API responses. |
| -k, --insecure | Disable SSL certificate check |

## Read a boot source selection

```bash
maas $PROFILE boot-source-selection read [--help] [-d] [-k] boot_source_id id [data ...]
```

#### Positional arguments
- boot_source_id
- id

Read a boot source selection with the given id.

#### Command-line options
| Option | Effect |
|-----|-----|
| --help, -h | Show this help message and exit. |
| -d, --debug | Display more information about API responses. |
| -k, --insecure | Disable SSL certificate check |
