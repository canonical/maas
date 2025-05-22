Enter keyword arguments in the form `key=value`.

## Delete license key

```bash
maas $PROFILE license-key delete [--help] [-d] [-k] osystem distro_series [data ...]
```

#### Positional arguments
- osystem
- distro_series

Delete license key for the given operation system and distro series.

#### Command-line options
| Option | Effect |
|-----|-----|
| --help, -h | Show this help message and exit. |
| -d, --debug | Display more information about API responses. |
| -k, --insecure | Disable SSL certificate check |

## Read license key

```bash
maas $PROFILE license-key read [--help] [-d] [-k] osystem distro_series [data ...]
```

#### Positional arguments
- osystem
- distro_series

Read a license key for the given operating system and distro series.

#### Command-line options
| Option | Effect |
|-----|-----|
| --help, -h | Show this help message and exit. |
| -d, --debug | Display more information about API responses. |
| -k, --insecure | Disable SSL certificate check |

## Update license key

```bash
maas $PROFILE license-key update [--help] [-d] [-k] osystem distro_series [data ...]
```

#### Positional arguments
- osystem
- distro_series


Update a license key for the given operating system and distro series.

#### Keyword "license_key"
Optional String. License key for osystem/distro_series combo.

#### Command-line options
| Option | Effect |
|-----|-----|
| --help, -h | Show this help message and exit. |
| -d, --debug | Display more information about API responses. |
| -k, --insecure | Disable SSL certificate check |

## Define a license key

```bash
maas $PROFILE license-keys create [--help] [-d] [-k] [data ...] 
```

Define a license key.

#### Keyword "osystem"
Required String. Operating system that the key belongs to.

#### Keyword "distro_series"
Required String. OS release that the key belongs to.

#### Keyword "license_key"
Required String. License key for osystem/distro_series combo.

#### Command-line options
| Option | Effect |
|-----|-----|
| --help, -h | Show this help message and exit. |
| -d, --debug | Display more information about API responses. |
| -k, --insecure | Disable SSL certificate check |

## List license keys

```bash
maas $PROFILE license-keys read [--help] [-d] [-k] [data ...] 
```

List all available license keys. 

#### Command-line options
| Option | Effect |
|-----|-----|
| --help, -h | Show this help message and exit. |
| -d, --debug | Display more information about API responses. |
| -k, --insecure | Disable SSL certificate check |

