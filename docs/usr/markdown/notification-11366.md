Enter keyword arguments in the form `key=value`.

## Delete a notification

```bash
maas $PROFILE notification delete [--help] [-d] [-k] id [data ...] 
```

#### Positional arguments
- id

Delete a notification with a given id.

#### Command-line options
| Option | Effect |
|-----|-----|
| --help, -h | Show this help message and exit. |
| -d, --debug | Display more information about API responses. |
| -k, --insecure | Disable SSL certificate check |

## Dismiss a notification

```bash
maas $PROFILE notification dismiss [--help] [-d] [-k] id [data ...] 
```

#### Positional arguments
- id

Dismiss a notification with the given id. It is safe to call multiple times for the same notification.

#### Command-line options
| Option | Effect |
|-----|-----|
| --help, -h | Show this help message and exit. |
| -d, --debug | Display more information about API responses. |
| -k, --insecure | Disable SSL certificate check |

## Read a notification

```bash
maas $PROFILE notification read [--help] [-d] [-k] id [data ...] 
```

#### Positional arguments
- id

Read a notification with the given id.

#### Command-line options
| Option | Effect |
|-----|-----|
| --help, -h | Show this help message and exit. |
| -d, --debug | Display more information about API responses. |
| -k, --insecure | Disable SSL certificate check |

## Update a notification

```bash
maas $PROFILE notification update [--help] [-d] [-k] id [data ...] 
```

#### Positional arguments
- id


Update a notification with a given id. This is available to admins *only*. One of the ``user``, ``users`` or ``admins`` parameters must be set to True for the notification to be visible to anyone.

#### Keyword "message"
Required String.  The message for this notification. May contain basic HTML, such as formatting. This string will be sanitised before display so that it doesn't break MAAS HTML.

#### Keyword "context"
Optional String.  Optional JSON context. The root object *must* be an object (i.e. a mapping). The values herein can be referenced by ``message`` with Python's "format" (not %) codes.

#### Keyword "category"
Optional String. Choose from: ``error``, ``warning``, ``success``, or ``info``. Defaults to ``info``.

#### Keyword "ident"
Optional String. Unique identifier for this notification.

#### Keyword "user"
Optional String.  User ID this notification is intended for. By default it will not be targeted to any individual user.

#### Keyword "users"
Optional Boolean. True to notify all users, defaults to false, i.e. not targeted to all users.

#### Keyword "admins"
Optional Boolean. True to notify all admins, defaults to false, i.e. not targeted to all admins.

#### Keyword "dismissable"
Optional Boolean. True to allow users dimissing the notification. Defaults to true.

#### Command-line options
| Option | Effect |
|-----|-----|
| --help, -h | Show this help message and exit. |
| -d, --debug | Display more information about API responses. |
| -k, --insecure | Disable SSL certificate check |

## Create a notification

```bash
maas $PROFILE notifications create [--help] [-d] [-k] [data ...] 
```

Create a new notification.  This is available to admins *only*. One of the ``user``, ``users`` or ``admins`` parameters must be set to True for the notification to be visible to anyone.

#### Keyword "message"
Required String.  The message for this notification. May contain basic HTML, such as formatting. This string will be sanitised before display so that it doesn't break MAAS HTML.

#### Keyword "context"
Optional String.  Optional JSON context. The root object *must* be an object (i.e. a mapping). The values herein can be referenced by ``message`` with Python's "format" (not %) codes.

#### Keyword "category"
Optional String. Choose from: ``error``, ``warning``, ``success``, or ``info``. Defaults to ``info``.

#### Keyword "ident"
Optional String. Unique identifier for this notification.

#### Keyword "user"
Optional.  User ID this notification is intended for. By default it will not be targeted to any individual user.

#### Keyword "users"
Optional Boolean. True to notify all users, defaults to false, i.e. not targeted to all users.

#### Keyword "admins"
Optional Boolean. True to notify all admins, defaults to false, i.e. not targeted to all admins.

#### Command-line options
| Option | Effect |
|-----|-----|
| --help, -h | Show this help message and exit. |
| -d, --debug | Display more information about API responses. |
| -k, --insecure | Disable SSL certificate check |

## List notifications

```bash
maas $PROFILE notifications read [--help] [-d] [-k] [data ...] 
```

List notifications relevant to the invoking user.  Notifications that have been dismissed are *not* returned.

#### Command-line options
| Option | Effect |
|-----|-----|
| --help, -h | Show this help message and exit. |
| -d, --debug | Display more information about API responses. |
| -k, --insecure | Disable SSL certificate check |

