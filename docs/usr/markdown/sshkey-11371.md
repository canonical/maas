Enter keyword arguments in the form `key=value`.

## Delete an SSH key

```bash
maas $PROFILE sshkey delete [--help] [-d] [-k] id [data ...] 
```

#### Positional arguments
- id


Deletes the SSH key with the given ID.

#### Keyword "id"
Required Int. An SSH key ID.

#### Command-line options
| Option | Effect |
|-----|-----|
| --help, -h | Show this help message and exit |
| -d, --debug | Display more information about API responses |
| -k, --insecure | Disable SSL certificate check |

## Retrieve an SSH key

```bash
maas $PROFILE sshkey read [--help] [-d] [-k] id [data ...] 
```

#### Positional arguments
- id


Retrieves an SSH key with the given ID.

#### Keyword "id"
Required Int. An SSH key ID.

#### Command-line options
| Option | Effect |
|-----|-----|
| --help, -h | Show this help message and exit |
| -d, --debug | Display more information about API responses |
| -k, --insecure | Disable SSL certificate check |

## Import SSH keys

```bash
maas $PROFILE sshkeys import [--help] [-d] [-k] [data ...] 
```

Import the requesting user's SSH keys for a given protocol and authorization ID in `protocol:auth_id` format.

#### Keyword "keysource"
Required String. The source of the keys to import should be provided in the request payload as form data, for example:


``source:user``

- ``source``: lp (Launchpad), gh (GitHub)
- ``user``: User login

#### Command-line options
| Option         | Effect                                        |
|----------------|-----------------------------------------------|
| --help, -h     | Show this help message and exit              |
| -d, --debug    | Display more information about API responses |
| -k, --insecure | Disable SSL certificate check                 |

## List SSH keys

```bash
maas $PROFILE sshkeys read [--help] [-d] [-k] [data ...] 
```

List all keys belonging to the requesting user. 

#### Command-line options
| Option         | Effect                                        |
|----------------|-----------------------------------------------|
| --help, -h     | Show this help message and exit              |
| -d, --debug    | Display more information about API responses |
| -k, --insecure | Disable SSL certificate check                 |

