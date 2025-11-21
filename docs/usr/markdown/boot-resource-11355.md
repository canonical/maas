Delete a boot resource

```bash
maas $PROFILE boot-resource delete [--help] [-d] [-k] id

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
Delete a boot resource by id.





Read a boot resource

```bash
maas $PROFILE boot-resource read [--help] [-d] [-k] id

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
Reads a boot resource by id





Create a new boot resource

```bash
maas $PROFILE boot-resources create [--help] [-d] [-k] [data ...]

```


#### **Command-line options**
| Option | Effect |
|---|---|
| --help, -h | Show this help message and exit. |
| -d, --debug | Display more information about API responses. |
| -k, --insecure | Disable SSL certificate check. |


#### **Keywords**
Creates a new boot resource. The file upload must be done<br>in chunk, see Boot resource file upload.

##### Keyword "name"
Optional String. Name of the boot resource.
##### Keyword "architecture"
Optional String. Architecture the boot<br>resource supports.
##### Keyword "sha256"
Optional String. The ``sha256`` hash of the<br>resource.
##### Keyword "size"
Optional String. The size of the resource in<br>bytes.
##### Keyword "title"
Optional String. Title for the boot resource.
##### Keyword "filetype"
Optional String. Filetype for uploaded<br>content. (Default: ``tgz``. Supported: ``tgz``, ``tbz``, ``txz``,<br>``ddtgz``, ``ddtbz``, ``ddtxz``, ``ddtar``, ``ddbz2``, ``ddgz``,<br>``ddxz``, ``ddraw``)
##### Keyword "base_image"
Optional String. The Base OS image a<br>custom image is built on top of. Only required for custom image.


Note: This command accepts JSON.


Import boot resources

```bash
maas $PROFILE boot-resources import [--help] [-d] [-k]

```


#### **Command-line options**
| Option | Effect |
|---|---|
| --help, -h | Show this help message and exit. |
| -d, --debug | Display more information about API responses. |
| -k, --insecure | Disable SSL certificate check. |


#### **Keywords**
Import the boot resources.





Importing status

```bash
maas $PROFILE boot-resources is-importing [--help] [-d] [-k]

```


#### **Command-line options**
| Option | Effect |
|---|---|
| --help, -h | Show this help message and exit. |
| -d, --debug | Display more information about API responses. |
| -k, --insecure | Disable SSL certificate check. |


#### **Keywords**
Get the status of importing resources.





List boot resources

```bash
maas $PROFILE boot-resources read [--help] [-d] [-k] [data ...]

```


#### **Command-line options**
| Option | Effect |
|---|---|
| --help, -h | Show this help message and exit. |
| -d, --debug | Display more information about API responses. |
| -k, --insecure | Disable SSL certificate check. |


#### **Keywords**
List all boot resources

##### Keyword "type"
Optional String. Type of boot resources to list.<br>If not provided, returns all types.


Note: This command accepts JSON.


Stop import boot resources

```bash
maas $PROFILE boot-resources stop-import [--help] [-d] [-k]

```


#### **Command-line options**
| Option | Effect |
|---|---|
| --help, -h | Show this help message and exit. |
| -d, --debug | Display more information about API responses. |
| -k, --insecure | Disable SSL certificate check. |


#### **Keywords**
Stop import the boot resources.
