Delete a boot source

```bash
maas $PROFILE boot-source-selection delete [--help] [-d] [-k] boot_source_id id

```

#### **Positional arguments**
| Argument | Effect |
|---|---|
| boot_source_id | The boot_source_id parameter |
| id | The ID of the resource (e.g., `1`, `abc123`) |


#### **Command-line options**
| Option | Effect |
|---|---|
| --help, -h | Show this help message and exit. |
| -d, --debug | Display more information about API responses. |
| -k, --insecure | Disable SSL certificate check. |


#### **Keywords**
Delete a boot source with the given id.





Read a boot source selection

```bash
maas $PROFILE boot-source-selection read [--help] [-d] [-k] boot_source_id id

```

#### **Positional arguments**
| Argument | Effect |
|---|---|
| boot_source_id | The boot_source_id parameter |
| id | The ID of the resource (e.g., `1`, `abc123`) |


#### **Command-line options**
| Option | Effect |
|---|---|
| --help, -h | Show this help message and exit. |
| -d, --debug | Display more information about API responses. |
| -k, --insecure | Disable SSL certificate check. |


#### **Keywords**
Read a boot source selection with the given id.





Create a boot-source selection

```bash
maas $PROFILE boot-source-selections create [--help] [-d] [-k] boot_source_id [data ...]

```

#### **Positional arguments**
| Argument | Effect |
|---|---|
| boot_source_id | The boot_source_id parameter |


#### **Command-line options**
| Option | Effect |
|---|---|
| --help, -h | Show this help message and exit. |
| -d, --debug | Display more information about API responses. |
| -k, --insecure | Disable SSL certificate check. |


#### **Keywords**
Create a new boot source selection.

##### Keyword "os"
Optional String. The OS (e.g. ubuntu, centos) for<br>which to import resources.
##### Keyword "release"
Optional String. The release for which to<br>import resources.
##### Keyword "arch"
Optional String. The architecture for which to<br>import resources.


Note: This command accepts JSON.


List boot-source selections

```bash
maas $PROFILE boot-source-selections read [--help] [-d] [-k] boot_source_id

```

#### **Positional arguments**
| Argument | Effect |
|---|---|
| boot_source_id | The boot_source_id parameter |


#### **Command-line options**
| Option | Effect |
|---|---|
| --help, -h | Show this help message and exit. |
| -d, --debug | Display more information about API responses. |
| -k, --insecure | Disable SSL certificate check. |


#### **Keywords**
List all available boot-source selections.
