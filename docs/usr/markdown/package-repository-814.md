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
