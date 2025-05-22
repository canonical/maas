Enter keyword arguments in the form `key=value`.

## Delete a commissioning script

*This operation has been deprecated in favor of `node-script delete`.*

```bash
maas $PROFILE commissioning-script delete [--help] [-d] [-k] name [data ...]
```

#### Positional arguments
- name

#### Command-line options
| Option | Effect |
|-----|-----|
| --help, -h | Show this help message and exit. |
| -d, --debug | Display more information about API responses. |
| -k, --insecure | Disable SSL certificate check |

## Read a commissioning script

*This operation has been deprecated in favor of `node-script read`.*

```bash
maas $PROFILE commissioning-script read [--help] [-d] [-k] name [data ...]
```

#### Positional arguments
- name

#### Command-line options
| Option | Effect |
|-----|-----|
| --help, -h | Show this help message and exit. |
| -d, --debug | Display more information about API responses. |
| -k, --insecure | Disable SSL certificate check |

## Update a commissioning script

*This operation has been deprecated in favor of `node-script update`.*

```bash
maas $PROFILE commissioning-script update [--help] [-d] [-k] name [data ...]
```

#### Positional arguments
- name

#### Command-line options
| Option | Effect |
|-----|-----|
| --help, -h | Show this help message and exit. |
| -d, --debug | Display more information about API responses. |
| -k, --insecure | Disable SSL certificate check |

## Create a new commissioning script.

*This operation has been deprecated in favor of `node-scripts create`.*

```bash
maas $PROFILE commissioning-scripts create [--help] [-d] [-k] [data ...]
```

Each commissioning script is identified by a unique name. By convention the name should consist of a two-digit number, a dash, and a brief descriptive identifier consisting only of ASCII characters.  You don't need to follow this convention, but not doing so opens you up to risks w.r.t. encoding and ordering.  The name must not contain any whitespace, quotes, or apostrophes. 

A commissioning machine will run each of the scripts in lexicographical order.  There are no promises about how non-ASCII characters are sorted, or even how upper-case letters are sorted relative to lower-case letters.  So where ordering matters, use unique numbers. 

Scripts built into MAAS will have names starting with "00-maas" or "99-maas" to ensure that they run first or last, respectively. 

Usually a commissioning script will be just that, a script.  Ideally a script should be ASCII text to avoid any confusion over encoding.  But in some cases a commissioning script might consist of a binary tool provided by a hardware vendor.  Either way, the script gets passed to the commissioning machine in the exact form in which it was uploaded. 

#### Keyword "name"
Unique identifying name for the script.  Names should follow the pattern of "25-burn-in-hard-disk" (all ASCII, and with numbers greater than zero, and generally no "weird" characters). 

#### Keyword "content"
A script file, to be uploaded in binary form.  Note: this is not a normal parameter, but a file upload.  Its filename is ignored; MAAS will know it by the name you pass to the request. 

#### Command-line options
| Option | Effect |
|-----|-----|
| --help, -h | Show this help message and exit. |
| -d, --debug | Display more information about API responses. |
| -k, --insecure | Disable SSL certificate check |

## List commissioning scripts

*This operation has been deprecated in favor of `node-scripts read`.*

```bash
maas $PROFILE commissioning-scripts read [--help] [-d] [-k] [data ...] 
```

#### Command-line options 
| Option | Effect |
|-----|-----|
| --help, -h | Show this help message and exit. |
| -d, --debug | Display more information about API responses. |
| -k, --insecure | Disable SSL certificate check |

