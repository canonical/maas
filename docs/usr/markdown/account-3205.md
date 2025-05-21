Enter keyword arguments in the form `key=value`.

## Create an authorisation token

```bash
maas $PROFILE account create-authorisation-token [--help] [-d] [-k] [data ...]
```

Create an authorisation OAuth token and OAuth consumer.

#### Keyword "name"
Optional String. Optional name of the token that will be generated.

#### Command-line options
| Option | Effect |
|-----|-----|
| --help, -h | Show this help message and exit. |
| -d, --debug | Display more information about API responses. |
| -k, --insecure | Disable SSL certificate check |

## Delete an authorisation token

```bash
maas $PROFILE account delete-authorisation-token [--help] [-d] [-k] [data ...]
```

Delete an authorisation OAuth token and the related OAuth consumer.

#### Keyword "token_key"
Required String. The key of the token to be deleted.

#### Command-line options
| Option | Effect |
|-----|-----|
| --help, -h | Show this help message and exit. |
| -d, --debug | Display more information about API responses. |
| -k, --insecure | Disable SSL certificate check |

## List authorisation tokens

```bash
maas $PROFILE account list-authorisation-tokens [--help] [-d] [-k] [data ...]
```

List authorisation tokens available to the currently logged-in user.

#### Command-line options
| Option | Effect |
|-----|-----|
| --help, -h | Show this help message and exit. |
| -d, --debug | Display more information about API responses. |
| -k, --insecure | Disable SSL certificate check |

## Modify authorisation token

```bash
maas $PROFILE account update-token-name [--help] [-d] [-k] [data ...]
```

Modify the consumer name of an authorisation OAuth token.

#### Keyword "token"
Required String. Can be the whole token or only the token key.

#### Keyword "name"
Required String. New name of the token.

#### Command-line options
| Option | Effect |
|-----|-----|
| --help, -h | Show this help message and exit. |
| -d, --debug | Display more information about API responses. |
| -k, --insecure | Disable SSL certificate check |

