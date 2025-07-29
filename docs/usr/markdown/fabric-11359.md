Enter keyword arguments in the form `key=value`.

## Delete a fabric

```bash
maas $PROFILE fabric delete [--help] [-d] [-k] id [data ...] 
```

#### Positional arguments
- id

Delete a fabric with the given id.

#### Command-line options
| Option | Effect |
|-----|-----|
| --help, -h | Show this help message and exit. |
| -d, --debug | Display more information about API responses. |
| -k, --insecure | Disable SSL certificate check |

## Read a fabric

```bash
maas $PROFILE fabric read [--help] [-d] [-k] id [data ...] 
```

#### Positional arguments
- id

Read a fabric with the given id.

#### Command-line options
| Option | Effect |
|-----|-----|
| --help, -h | Show this help message and exit. |
| -d, --debug | Display more information about API responses. |
| -k, --insecure | Disable SSL certificate check |

## Update fabric

```bash
maas $PROFILE fabric update [--help] [-d] [-k] id [data ...] 
```

#### Positional arguments
- id


Update a fabric with the given id.

#### Keyword "name"
Optional String. Name of the fabric.

#### Keyword "description"
Optional String. Description of the fabric.

#### Keyword "class_type"
Optional String. Class type of the fabric.

#### Command-line options
| Option | Effect |
|-----|-----|
| --help, -h | Show this help message and exit. |
| -d, --debug | Display more information about API responses. |
| -k, --insecure | Disable SSL certificate check |

## Create a fabric

```bash
maas $PROFILE fabrics create [--help] [-d] [-k] [data ...] 
```

Create a fabric.

#### Keyword "name"
Optional String. Name of the fabric.

#### Keyword "description"
Optional String. Description of the fabric.

#### Keyword "class_type"
Optional String. Class type of the fabric.

#### Command-line options
| Option | Effect |
|-----|-----|
| --help, -h | Show this help message and exit. |
| -d, --debug | Display more information about API responses. |
| -k, --insecure | Disable SSL certificate check |

## List fabrics

```bash
maas $PROFILE fabrics read [--help] [-d] [-k] [data ...] 
```

List all fabrics. 

#### Command-line options
| Option | Effect |
|-----|-----|
| --help, -h | Show this help message and exit. |
| -d, --debug | Display more information about API responses. |
| -k, --insecure | Disable SSL certificate check |
