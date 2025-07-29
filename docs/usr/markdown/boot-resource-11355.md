Enter keyword arguments in the form `key=value`.

## Delete a boot resource

```bash
maas $PROFILE boot-resource delete [--help] [-d] [-k] id [data ...] 
```

#### Positional arguments
- id

Delete a boot resource by id.

#### Command-line options
| Option | Effect |
|-----|-----|
| --help, -h | Show this help message and exit. |
| -d, --debug | Display more information about API responses. |
| -k, --insecure | Disable SSL certificate check |

## Read a boot resource

```bash
maas $PROFILE boot-resource read [--help] [-d] [-k] id [data ...] 
```

#### Positional arguments
- id

Reads a boot resource by id

#### Command-line options
| Option | Effect |
|-----|-----|
| --help, -h | Show this help message and exit. |
| -d, --debug | Display more information about API responses. |
| -k, --insecure | Disable SSL certificate check |

## Upload a new boot resource

```bash
maas $PROFILE boot-resources create [--help] [-d] [-k] [data ...] 
```

Uploads a new boot resource.

#### Keyword "name"
Required String. Name of the boot resource.

#### Keyword "architecture"
Required String. Architecture the boot resource supports.

#### Keyword "sha256"
Required String.  The ``sha256`` hash of the resource.

#### Keyword "size"
Required String. The size of the resource in bytes.

#### Keyword "title"
Optional String. Title for the boot resource.

#### Keyword "filetype"
Optional String..  Filetype for uploaded content. (Default: ``tgz``. Supported: ``tgz``, ``tbz``, ``txz``, ``ddtgz``, ``ddtbz``, ``ddtxz``, ``ddtar``, ``ddbz2``, ``ddgz``, ``ddxz``, ``ddraw``)

#### Keyword "base_image"
Optional String. The Base OS image a custom image is built on top of. Only required for custom image.

#### Keyword "content"
Optional String..  Image content. Note: this is not a normal parameter, but an ``application/octet-stream`` file upload.

#### Command-line options
| Option | Effect |
|-----|-----|
| --help, -h | Show this help message and exit. |
| -d, --debug | Display more information about API responses. |
| -k, --insecure | Disable SSL certificate check |

## Import boot resources

```bash
maas $PROFILE boot-resources import [--help] [-d] [-k] [data ...] 
```

Import the boot resources. 

#### Command-line options
| Option | Effect |
|-----|-----|
| --help, -h | Show this help message and exit. |
| -d, --debug | Display more information about API responses. |
| -k, --insecure | Disable SSL certificate check |

## Importing status

```bash
maas $PROFILE boot-resources is-importing [--help] [-d] [-k] [data ...] 
```

Get the status of importing resources. 

#### Command-line options
| Option | Effect |
|-----|-----|
| --help, -h | Show this help message and exit. |
| -d, --debug | Display more information about API responses. |
| -k, --insecure | Disable SSL certificate check |

## List boot resources

```bash
maas $PROFILE boot-resources read [--help] [-d] [-k] [data ...] 
```

List all boot resources

#### Keyword "type"
Optional String. Type of boot resources to list. If not provided, returns all types.

#### Command-line options
| Option | Effect |
|-----|-----|
| --help, -h | Show this help message and exit. |
| -d, --debug | Display more information about API responses. |
| -k, --insecure | Disable SSL certificate check |

## Stop import boot resources

```bash
maas $PROFILE boot-resources stop-import [--help] [-d] [-k] [data ...] 
```

Stop import the boot resources. 

#### Command-line options
| Option | Effect |
|-----|-----|
| --help, -h | Show this help message and exit. |
| -d, --debug | Display more information about API responses. |
| -k, --insecure | Disable SSL certificate check |
