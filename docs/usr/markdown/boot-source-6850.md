Delete a boot source

```bash
maas $PROFILE boot-source delete [--help] [-d] [-k] id

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
Delete a boot source with the given id.





Read a boot source

```bash
maas $PROFILE boot-source read [--help] [-d] [-k] id

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
Read a boot source with the given id.





Update a boot source

```bash
maas $PROFILE boot-source update [--help] [-d] [-k] id [data ...]

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
Update a boot source with the given id.

##### Keyword "url"
Optional String. The URL of the BootSource.
##### Keyword "keyring_filename"
Optional String. The path to the<br>keyring file for this BootSource.
##### Keyword "keyring_data"
Optional String. The GPG keyring for<br>this BootSource, base64-encoded data.


Note: This command accepts JSON.


Create a boot source

```bash
maas $PROFILE boot-sources create [--help] [-d] [-k] [data ...]

```


#### **Command-line options**
| Option | Effect |
|---|---|
| --help, -h | Show this help message and exit. |
| -d, --debug | Display more information about API responses. |
| -k, --insecure | Disable SSL certificate check. |


#### **Keywords**
Create a new boot source. Note that in addition to<br>``url``, you must supply either ``keyring_data`` or<br>``keyring_filename``.

##### Keyword "url"
Optional String. The URL of the BootSource.
##### Keyword "keyring_filename"
Optional String. The path to the<br>keyring file for this BootSource.
##### Keyword "keyring_data"
Optional String. The GPG keyring for<br>this BootSource, base64-encoded.


Note: This command accepts JSON.


List boot sources

```bash
maas $PROFILE boot-sources read [--help] [-d] [-k]

```


#### **Command-line options**
| Option | Effect |
|---|---|
| --help, -h | Show this help message and exit. |
| -d, --debug | Display more information about API responses. |
| -k, --insecure | Disable SSL certificate check. |


#### **Keywords**
List all boot sources.
