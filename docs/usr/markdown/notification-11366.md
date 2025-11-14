Delete a notification

```bash
maas $PROFILE notification delete [--help] [-d] [-k] id

```

#### **Positional arguments**
| Argument | Effect |
|---|---|
| id | The ID of the resource (e.g., `1`, `abc123`) |


#### **Command-line options**
| Option | Effect |
|---|---|
| --help, -h | Show this help message and exit. |
| -d, --debug | Display more information about API responses. |
| -k, --insecure | Disable SSL certificate check. |


#### **Keywords**
Delete a notification with a given id.





Dismiss a notification

```bash
maas $PROFILE notification dismiss [--help] [-d] [-k] id

```

#### **Positional arguments**
| Argument | Effect |
|---|---|
| id | The ID of the resource (e.g., `1`, `abc123`) |


#### **Command-line options**
| Option | Effect |
|---|---|
| --help, -h | Show this help message and exit. |
| -d, --debug | Display more information about API responses. |
| -k, --insecure | Disable SSL certificate check. |


#### **Keywords**
Dismiss a notification with the given id. It is safe to call multiple times for the same notification.





Read a notification

```bash
maas $PROFILE notification read [--help] [-d] [-k] id

```

#### **Positional arguments**
| Argument | Effect |
|---|---|
| id | The ID of the resource (e.g., `1`, `abc123`) |


#### **Command-line options**
| Option | Effect |
|---|---|
| --help, -h | Show this help message and exit. |
| -d, --debug | Display more information about API responses. |
| -k, --insecure | Disable SSL certificate check. |


#### **Keywords**
Read a notification with the given id.





Update a notification

```bash
maas $PROFILE notification update [--help] [-d] [-k] id [data ...]

```

#### **Positional arguments**
| Argument | Effect |
|---|---|
| id | The ID of the resource (e.g., `1`, `abc123`) |


#### **Command-line options**
| Option | Effect |
|---|---|
| --help, -h | Show this help message and exit. |
| -d, --debug | Display more information about API responses. |
| -k, --insecure | Disable SSL certificate check. |


#### **Keywords**
Update a notification with a given id. This is available to admins *only*. Note: One of the ``user``, ``users`` or ``admins`` parameters must be<br>set to True for the notification to be visible to anyone.

##### Keyword "message"
Optional String. The message for this<br>notification. May contain basic HTML, such as formatting. This string<br>will be sanitised before display so that it doesn't break MAAS HTML.
##### Keyword "context"
Optional String. JSON context. The<br>root object *must* be an object (i.e. a mapping). The values herein can<br>be referenced by ``message`` with Python's "format" (not %) codes.
##### Keyword "category"
Optional String. Choose from: ``error``,<br>``warning``, ``success``, or ``info``. Defaults to ``info``.
##### Keyword "ident"
Optional String. Unique identifier for this<br>notification.
##### Keyword "user"
Optional String. User ID this notification is<br>intended for. By default it will not be targeted to any individual<br>user.
##### Keyword "users"
Optional Boolean. True to notify all users,<br>defaults to false, i.e. not targeted to all users.
##### Keyword "admins"
Optional Boolean. True to notify all admins,<br>defaults to false, i.e. not targeted to all admins.
##### Keyword "dismissable"
Optional Boolean. True to allow users<br>dismissing the notification. Defaults to true.


Note: This command accepts JSON.


Create a notification

```bash
maas $PROFILE notifications create [--help] [-d] [-k] [data ...]

```


#### **Command-line options**
| Option | Effect |
|---|---|
| --help, -h | Show this help message and exit. |
| -d, --debug | Display more information about API responses. |
| -k, --insecure | Disable SSL certificate check. |


#### **Keywords**
Create a new notification. This is available to admins *only*. Note: One of the ``user``, ``users`` or ``admins`` parameters must be<br>set to True for the notification to be visible to anyone.

##### Keyword "message"
Optional String. The message for this<br>notification. May contain basic HTML, such as formatting. This string<br>will be sanitised before display so that it doesn't break MAAS HTML.
##### Keyword "context"
Optional String. JSON context. The<br>root object *must* be an object (i.e. a mapping). The values herein can<br>be referenced by ``message`` with Python's "format" (not %) codes.
##### Keyword "category"
Optional String. Choose from: ``error``,<br>``warning``, ``success``, or ``info``. Defaults to ``info``.
##### Keyword "ident"
Optional String. Unique identifier for this<br>notification.
##### Keyword "user"
Optional String. User ID this notification is<br>intended for. By default it will not be targeted to any individual<br>user.
##### Keyword "users"
Optional Boolean. True to notify all users,<br>defaults to false, i.e. not targeted to all users.
##### Keyword "admins"
Optional Boolean. True to notify all admins,<br>defaults to false, i.e. not targeted to all admins.


Note: This command accepts JSON.


List notifications

```bash
maas $PROFILE notifications read [--help] [-d] [-k]

```


#### **Command-line options**
| Option | Effect |
|---|---|
| --help, -h | Show this help message and exit. |
| -d, --debug | Display more information about API responses. |
| -k, --insecure | Disable SSL certificate check. |


#### **Keywords**
List notifications relevant to the invoking user. Notifications that have been dismissed are *not* returned.
