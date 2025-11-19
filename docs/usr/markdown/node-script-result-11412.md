Delete script results

```bash
maas $PROFILE node-script-result delete [--help] [-d] [-k] system_id id

```

#### **Positional arguments**
| Argument | Effect |
|---|---|
| system_id | The system ID of the machine/device (e.g., `abc123`) |
| id | The ID of the resource (e.g., `1`, `abc123`) |


#### **Command-line options**
| Option | Effect |
|---|---|
| --help, -h | Show this help message and exit. |
| -d, --debug | Display more information about API responses. |
| -k, --insecure | Disable SSL certificate check. |


#### **Keywords**
Delete script results from the given system_id with the<br>given id. "id" can either by the script set id, ``current-commissioning``,<br>``current-testing``, or ``current-installation``.





Download script results

```bash
maas $PROFILE node-script-result download [--help] [-d] [-k] system_id id [data ...]

```

#### **Positional arguments**
| Argument | Effect |
|---|---|
| system_id | The system ID of the machine/device (e.g., `abc123`) |
| id | The ID of the resource (e.g., `1`, `abc123`) |


#### **Command-line options**
| Option | Effect |
|---|---|
| --help, -h | Show this help message and exit. |
| -d, --debug | Display more information about API responses. |
| -k, --insecure | Disable SSL certificate check. |


#### **Keywords**
Download a compressed tar containing all results from the<br>given system_id with the given id. "id" can either by the script set id, ``current-commissioning``,<br>``current-testing``, or ``current-installation``.

##### Keyword "hardware_type"
Optional String. Only return scripts<br>for the given hardware type. Can be ``node``, ``cpu``, ``memory``, or<br>``storage``. Defaults to all.
##### Keyword "filters"
Optional String. A comma separated list to<br>show only results that ran with a script name or tag.
##### Keyword "output"
Optional String. Can be either ``combined``,<br>``stdout``, ``stderr``, or ``all``. By default only the combined output<br>is returned.
##### Keyword "filetype"
Optional String. Filetype to output, can be<br>``txt`` or ``tar.xz``.


Note: This command accepts JSON.


Get specific script result

```bash
maas $PROFILE node-script-result read [--help] [-d] [-k] system_id id [data ...]

```

#### **Positional arguments**
| Argument | Effect |
|---|---|
| system_id | The system ID of the machine/device (e.g., `abc123`) |
| id | The ID of the resource (e.g., `1`, `abc123`) |


#### **Command-line options**
| Option | Effect |
|---|---|
| --help, -h | Show this help message and exit. |
| -d, --debug | Display more information about API responses. |
| -k, --insecure | Disable SSL certificate check. |


#### **Keywords**
View a set of test results for a given system_id and<br>script id. "id" can either by the script set id, ``current-commissioning``,<br>``current-testing``, or ``current-installation``.

##### Keyword "hardware_type"
Optional String. Only return scripts<br>for the given hardware type. Can be ``node``, ``cpu``, ``memory``, or<br>``storage``. Defaults to all.
##### Keyword "include_output"
Optional String. Include the base64<br>encoded output from the script if any value for include_output is<br>given.
##### Keyword "filters"
Optional String. A comma separated list to<br>show only results that ran with a script name, tag, or id.


Note: This command accepts JSON.


Update specific script result

```bash
maas $PROFILE node-script-result update [--help] [-d] [-k] system_id id [data ...]

```

#### **Positional arguments**
| Argument | Effect |
|---|---|
| system_id | The system ID of the machine/device (e.g., `abc123`) |
| id | The ID of the resource (e.g., `1`, `abc123`) |


#### **Command-line options**
| Option | Effect |
|---|---|
| --help, -h | Show this help message and exit. |
| -d, --debug | Display more information about API responses. |
| -k, --insecure | Disable SSL certificate check. |


#### **Keywords**
Update a set of test results for a given system_id and<br>script id. "id" can either be the script set id, ``current-commissioning``,<br>``current-testing``, or ``current-installation``.

##### Keyword "hardware_type"
Optional String. Only return scripts<br>for the given hardware type. Can be ``node``, ``cpu``, ``memory``, or<br>``storage``. Defaults to all.
##### Keyword "filters"
Optional String. A comma separated list to<br>show only results that ran with a script name, tag, or id.
##### Keyword "include_output"
Optional String. Include the base64<br>encoded output from the script if any value for include_output is<br>given.
##### Keyword "suppressed"
Optional Boolean. Set whether or not<br>this script result should be suppressed using 'true' or 'false'.


Note: This command accepts JSON.


Return script results

```bash
maas $PROFILE node-script-results read [--help] [-d] [-k] system_id [data ...]

```

#### **Positional arguments**
| Argument | Effect |
|---|---|
| system_id | The system ID of the machine/device (e.g., `abc123`) |


#### **Command-line options**
| Option | Effect |
|---|---|
| --help, -h | Show this help message and exit. |
| -d, --debug | Display more information about API responses. |
| -k, --insecure | Disable SSL certificate check. |


#### **Keywords**
Return a list of script results grouped by run for the<br>given system_id.

##### Keyword "type"
Optional String. Only return scripts with the<br>given type. This can be ``commissioning``, ``testing``, ``installion``<br>or ``release``. Defaults to showing all.
##### Keyword "hardware_type"
Optional String. Only return scripts<br>for the given hardware type. Can be ``node``, ``cpu``, ``memory``, or<br>``storage``. Defaults to all.
##### Keyword "include_output"
Optional String. Include base64<br>encoded output from the script. Note that any value of include_output<br>will include the encoded output from the script.
##### Keyword "filters"
Optional String. A comma separated list to<br>show only results with a script name or tag.


Note: This command accepts JSON.
