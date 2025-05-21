Enter keyword arguments in the form `key=value`.

## Delete a boot source

```bash
maas $PROFILE boot-source delete [--help] [-d] [-k] id [data ...] 
```

#### Positional arguments
- id

Delete a boot source with the given id.

#### Command-line options
| Option | Effect |
|-----|-----|
| --help, -h | Show this help message and exit. |
| -d, --debug | Display more information about API responses. |
| -k, --insecure | Disable SSL certificate check |

## Read a boot source

```bash
maas $PROFILE boot-source read [--help] [-d] [-k] id [data ...] 
```

#### Positional arguments
- id

Read a boot source with the given id.

#### Command-line options
| Option | Effect |
|-----|-----|
| --help, -h | Show this help message and exit. |
| -d, --debug | Display more information about API responses. |
| -k, --insecure | Disable SSL certificate check |

## Update a boot source

```bash
maas $PROFILE boot-source update [--help] [-d] [-k] id [data ...] 
```

#### Positional arguments
- id


Update a boot source with the given id.

#### Keyword "url"
Optional String. The URL of the BootSource.

#### Keyword "keyring_filename"
Optional String. The path to the keyring file for this BootSource.

#### Keyword "keyring_data"
Optional String. The GPG keyring for this BootSource, base64-encoded data.

#### Command-line options
| Option | Effect |
|-----|-----|
| --help, -h | Show this help message and exit. |
| -d, --debug | Display more information about API responses. |
| -k, --insecure | Disable SSL certificate check |

## Create a boot source

```bash
maas $PROFILE boot-sources create [--help] [-d] [-k] [data ...] 
```

Create a new boot source. 

Note that in addition to ``url``, you must supply either ``keyring_data`` or ``keyring_filename``.

#### Keyword "url"
Required String. The URL of the BootSource.

#### Keyword "keyring_filename"
Optional String. The path to the keyring file for this BootSource.

#### Keyword "keyring_data"
Optional String. The GPG keyring for this BootSource, base64-encoded.

#### Command-line options
| Option | Effect |
|-----|-----|
| --help, -h | Show this help message and exit. |
| -d, --debug | Display more information about API responses. |
| -k, --insecure | Disable SSL certificate check |

## List boot sources

```bash
maas $PROFILE boot-sources read [--help] [-d] [-k] [data ...] 
```

List all boot sources. 

#### Command-line options
| Option | Effect |
|-----|-----|
| --help, -h | Show this help message and exit. |
| -d, --debug | Display more information about API responses. |
| -k, --insecure | Disable SSL certificate check |

