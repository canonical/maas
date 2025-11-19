Delete an SSH key

```bash
maas $PROFILE sshkey delete [--help] [-d] [-k] id [data ...]

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
Deletes the SSH key with the given ID.

##### Keyword "id"
Optional Int. An SSH key ID.


Note: This command accepts JSON.


Retrieve an SSH key

```bash
maas $PROFILE sshkey read [--help] [-d] [-k] id [data ...]

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
Retrieves an SSH key with the given ID.

##### Keyword "id"
Optional Int. An SSH key ID.


Note: This command accepts JSON.


Add a new SSH key

```bash
maas $PROFILE sshkeys create [--help] [-d] [-k] [data ...]

```


#### **Command-line options**
| Option | Effect |
|---|---|
| --help, -h | Show this help message and exit. |
| -d, --debug | Display more information about API responses. |
| -k, --insecure | Disable SSL certificate check. |


#### **Keywords**
Add a new SSH key to the requesting or supplied user's<br>account.

##### Keyword "key"
Optional String. A public SSH key<br>should be provided in the request payload as form data with the name<br>'key':<br><br>``key: "key-type public-key-data"``<br><br>- ``key-type``: ecdsa-sha2-nistp256, ecdsa-sha2-nistp384,<br>ecdsa-sha2-nistp521, ssh-dss, ssh-ed25519, ssh-rsa<br>- ``public key data``: Base64-encoded key data.


Note: This command accepts JSON.


Import SSH keys

```bash
maas $PROFILE sshkeys import [--help] [-d] [-k] [data ...]

```


#### **Command-line options**
| Option | Effect |
|---|---|
| --help, -h | Show this help message and exit. |
| -d, --debug | Display more information about API responses. |
| -k, --insecure | Disable SSL certificate check. |


#### **Keywords**
Import the requesting user's SSH keys for a given protocol<br>and authorization ID in protocol:auth_id format.

##### Keyword "keysource"
Optional String. The source<br>of the keys to import should be provided in the request payload as form<br>data:<br><br>E.g. ``source:user``<br><br>- ``source``: lp (Launchpad), gh (GitHub)<br>- ``user``: User login


Note: This command accepts JSON.


List SSH keys

```bash
maas $PROFILE sshkeys read [--help] [-d] [-k]

```


#### **Command-line options**
| Option | Effect |
|---|---|
| --help, -h | Show this help message and exit. |
| -d, --debug | Display more information about API responses. |
| -k, --insecure | Disable SSL certificate check. |


#### **Keywords**
List all keys belonging to the requesting user.
