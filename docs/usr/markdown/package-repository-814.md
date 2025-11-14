Create a package repository

```bash
maas $PROFILE package-repositories create [--help] [-d] [-k] [data ...]

```


#### **Command-line options**
| Option | Effect |
|---|---|
| --help, -h | Show this help message and exit. |
| -d, --debug | Display more information about API responses. |
| -k, --insecure | Disable SSL certificate check. |


#### **Keywords**
Create a new package repository.

##### Keyword "name"
Optional String. The name of the package<br>repository.
##### Keyword "url"
Optional String. The url of the package<br>repository.
##### Keyword "distributions"
Optional String. Which package<br>distributions to include.
##### Keyword "disabled_pockets"
Optional String. The list of pockets<br>to disable.
##### Keyword "components"
Optional String. The list of components to<br>enable. Only applicable to custom repositories.
##### Keyword "arches"
Optional String. The list of supported<br>architectures.
##### Keyword "key"
Optional String. The authentication key to use<br>with the repository.
##### Keyword "disable_sources"
Optional Boolean. Disable deb-src<br>lines.
##### Keyword "enabled"
Optional Boolean. Whether or not the<br>repository is enabled.


Note: This command accepts JSON.


List package repositories

```bash
maas $PROFILE package-repositories read [--help] [-d] [-k]

```


#### **Command-line options**
| Option | Effect |
|---|---|
| --help, -h | Show this help message and exit. |
| -d, --debug | Display more information about API responses. |
| -k, --insecure | Disable SSL certificate check. |


#### **Keywords**
List all available package repositories.





Delete a package repository

```bash
maas $PROFILE package-repository delete [--help] [-d] [-k] id

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
Delete a package repository with the given id.





Read a package repository

```bash
maas $PROFILE package-repository read [--help] [-d] [-k] id

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
Read a package repository with the given id.





Update a package repository

```bash
maas $PROFILE package-repository update [--help] [-d] [-k] id [data ...]

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
Update the package repository with the given id.

##### Keyword "name"
Optional String. The name of the package<br>repository.
##### Keyword "url"
Optional String. The url of the package<br>repository.
##### Keyword "distributions"
Optional String. Which package<br>distributions to include.
##### Keyword "disabled_pockets"
Optional String. The list of pockets<br>to disable.
##### Keyword "disabled_components"
Optional String. The list of<br>components to disable. Only applicable to the default Ubuntu<br>repositories.
##### Keyword "components"
Optional String. The list of components to<br>enable. Only applicable to custom repositories.
##### Keyword "arches"
Optional String. The list of supported<br>architectures.
##### Keyword "key"
Optional String. The authentication key to use<br>with the repository.
##### Keyword "disable_sources"
Optional Boolean. Disable deb-src<br>lines.
##### Keyword "enabled"
Optional Boolean. Whether or not the<br>repository is enabled.


Note: This command accepts JSON.
