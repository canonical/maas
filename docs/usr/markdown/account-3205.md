Enter keyword arguments in the form `key=value`.

## Create an authorizations token

```bash
maas $PROFILE account create-authorizations-token [--help] [-d] [-k] [data ...]
```

Create an authorizations OAuth token and OAuth consumer.

#### Keyword "name"
Optional String. Optional name of the token that will be generated.

#### Command-line options
| Option | Effect |
|-----|-----|
| --help, -h | Show this help message and exit. |
| -d, --debug | Display more information about API responses. |
| -k, --insecure | Disable SSL certificate check |

## Delete an authorizations token

```bash
maas $PROFILE account delete-authorizations-token [--help] [-d] [-k] [data ...]
```

Delete an authorizations OAuth token and the related OAuth consumer.

#### Keyword "token_key"
Required String. The key of the token to be deleted.

#### Command-line options
| Option | Effect |
|-----|-----|
| --help, -h | Show this help message and exit. |
| -d, --debug | Display more information about API responses. |
| -k, --insecure | Disable SSL certificate check |

## List authorizations tokens

```bash
maas $PROFILE account list-authorizations-tokens [--help] [-d] [-k] [data ...]
```

List authorizations tokens available to the currently logged-in user.

#### Command-line options
| Option | Effect |
|-----|-----|
| --help, -h | Show this help message and exit. |
| -d, --debug | Display more information about API responses. |
| -k, --insecure | Disable SSL certificate check |

## Modify authorizations token

```bash
maas $PROFILE account update-token-name [--help] [-d] [-k] [data ...]
```

Modify the consumer name of an authorizations OAuth token.

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

