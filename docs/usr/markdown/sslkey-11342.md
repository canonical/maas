Enter keyword arguments in the form `key=value`.

## Delete an SSL key

```bash
maas $PROFILE sslkey delete [--help] [-d] [-k] id [data ...] 
```

#### Positional arguments
- id


Deletes the SSL key with the given ID.

#### Keyword "id"
Required Int. An SSH key ID.

#### Command-line options
| Option         | Effect                                        |
|----------------|-----------------------------------------------|
| --help, -h     | Show this help message and exit              |
| -d, --debug    | Display more information about API responses |
| -k, --insecure | Disable SSL certificate check                 |

## Retrieve an SSL key

```bash
maas $PROFILE sslkey read [--help] [-d] [-k] id [data ...] 
```

#### Positional arguments
- id


Retrieves an SSL key with the given ID.

#### Keyword "id"
Required Int. An SSL key ID.

#### Command-line options
| Option         | Effect                                        |
|----------------|-----------------------------------------------|
| --help, -h     | Show this help message and exit              |
| -d, --debug    | Display more information about API responses |
| -k, --insecure | Disable SSL certificate check                 |

