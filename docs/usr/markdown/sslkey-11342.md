Delete an SSL key

```bash
maas $PROFILE sslkey delete [--help] [-d] [-k] id [data ...]

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
Deletes the SSL key with the given ID.

##### Keyword "id"
Optional Int. An SSH key ID.


Note: This command accepts JSON.


Retrieve an SSL key

```bash
maas $PROFILE sslkey read [--help] [-d] [-k] id [data ...]

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
Retrieves an SSL key with the given ID.

##### Keyword "id"
Optional Int. An SSL key ID.


Note: This command accepts JSON.


Add a new SSL key

```bash
maas $PROFILE sslkeys create [--help] [-d] [-k] [data ...]

```


#### **Command-line options**
| Option | Effect |
|---|---|
| --help, -h | Show this help message and exit. |
| -d, --debug | Display more information about API responses. |
| -k, --insecure | Disable SSL certificate check. |


#### **Keywords**
Add a new SSL key to the requesting user's account.

##### Keyword "key"
Optional String. An SSL key<br>should be provided in the request payload as form data with the name<br>'key':<br><br>``key: "key data"``<br><br>- ``key data``: The contents of a pem file.


Note: This command accepts JSON.


List keys

```bash
maas $PROFILE sslkeys read [--help] [-d] [-k]

```


#### **Command-line options**
| Option | Effect |
|---|---|
| --help, -h | Show this help message and exit. |
| -d, --debug | Display more information about API responses. |
| -k, --insecure | Disable SSL certificate check. |


#### **Keywords**
List all keys belonging to the requesting user.
