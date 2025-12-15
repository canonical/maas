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





Update a boot-source selection

```bash
maas $PROFILE boot-source-selection update [--help] [-d] [-k] boot_source_id id [data ...]

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
Update a boot source selection with the given id.

##### Keyword "os"
Optional String. The OS (e.g. ubuntu, centos) for<br>which to import resources.
##### Keyword "release"
Optional String. The release for which to<br>import resources.
##### Keyword "arches"
Optional String. The list of architectures for<br>which to import resources.
##### Keyword "subarches"
Optional String. The list of<br>sub-architectures for which to import resources.
##### Keyword "labels"
Optional String. The list of labels for which<br>to import resources.


Note: This command accepts JSON.


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
##### Keyword "arches"
Optional String. The architecture list for<br>which to import resources.
##### Keyword "subarches"
Optional String. The subarchitecture list<br>for which to import resources.
##### Keyword "labels"
Optional String. The label lists for which to<br>import resources.


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
