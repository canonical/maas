Enter keyword arguments in the form `key=value`.

## Delete script results

```bash
maas $PROFILE node-script-result delete [--help] [-d] [-k] system_id id [data ...]
```

#### Positional arguments
- system_id
- id

Delete script results from the given system_id with the given id.

"id" can either by the script set id, ``current-commissioning``, ``current-testing``, or ``current-installation``.

#### Command-line options
| Option         | Effect                                        |
|----------------|-----------------------------------------------|
| --help, -h     | Show this help message and exit.              |
| -d, --debug    | Display more information about API responses. |
| -k, --insecure | Disable SSL certificate check                 |

## Download script results

```bash
maas $PROFILE node-script-result download [--help] [-d] [-k] system_id id [data ...]
```

#### Positional arguments
- system_id
- id


Download a compressed tar containing all results from the given system_id with the given id.

"id" can either by the script set id, ``current-commissioning``, ``current-testing``, or ``current-installation``.

#### Keyword "hardware_type"
Optional String.  Only return scripts for the given hardware type.  Can be ``node``, ``cpu``, ``memory``, or ``storage``.  Defaults to all.

#### Keyword "filters"
Optional String. A comma seperated list to show only results that ran with a script name or tag.

#### Keyword "output"
Optional String.  Can be either ``combined``, ``stdout``, ``stderr``, or ``all``. By default only the combined output is returned.

#### Keyword "filetype"
Optional String. Filetype to output, can be ``txt`` or ``tar.xz``.

#### Command-line options
| Option         | Effect                                        |
|----------------|-----------------------------------------------|
| --help, -h     | Show this help message and exit.              |
| -d, --debug    | Display more information about API responses. |
| -k, --insecure | Disable SSL certificate check                 |

## Get specific script result

```bash
maas $PROFILE node-script-result read [--help] [-d] [-k] system_id id [data ...]
```

#### Positional arguments
- system_id
- id


View a set of test results for a given system_id and script id.

"id" can either by the script set id, ``current-commissioning``, ``current-testing``, or ``current-installation``.

#### Keyword "hardware_type"
Optional String.  Only return scripts for the given hardware type.  Can be ``node``, ``cpu``, ``memory``, or ``storage``.  Defaults to all.

#### Keyword "include_output"
Optional.  Include the base64 encoded output from the script if any value for include_output is given.

#### Keyword "filters"
Optional String. A comma seperated list to show only results that ran with a script name, tag, or id.

#### Command-line options
| Option         | Effect                                        |
|----------------|-----------------------------------------------|
| --help, -h     | Show this help message and exit.              |
| -d, --debug    | Display more information about API responses. |
| -k, --insecure | Disable SSL certificate check                 |

## Update specific script result

```bash
maas $PROFILE node-script-result update [--help] [-d] [-k] system_id id [data ...]
```

#### Positional arguments
- system_id
- id

Update a set of test results for a given system_id and script id.

"id" can either be the script set id, ``current-commissioning``, ``current-testing``, or ``current-installation``.

#### Keyword "hardware_type"
Optional String.  Only return scripts for the given hardware type.  Can be ``node``, ``cpu``, ``memory``, or ``storage``.  Defaults to all.

#### Keyword "filters"
Optional String. A comma seperated list to show only results that ran with a script name, tag, or id.

#### Keyword "include_output"
Optional String.  Include the base64 encoded output from the script if any value for include_output is given.

#### Keyword "suppressed"
Optional Boolean. Set whether or not this script result should be suppressed using 'true' or 'false'.

#### Command-line options
| Option         | Effect                                        |
|----------------|-----------------------------------------------|
| --help, -h     | Show this help message and exit.              |
| -d, --debug    | Display more information about API responses. |
| -k, --insecure | Disable SSL certificate check                 |

## Return script results

```bash
maas $PROFILE node-script-results read [--help] [-d] [-k] system_id [data ...]
```

#### Positional arguments
- system_id

Return a list of script results grouped by run for the given system_id.

#### Keyword "type"
Optional String.  Only return scripts with the given type. This can be ``commissioning``, ``testing``, ``installion`` or ``release``. Defaults to showing all.

#### Keyword "hardware_type"
Optional String.  Only return scripts for the given hardware type.  Can be ``node``, ``cpu``, ``memory``, or ``storage``.  Defaults to all.

#### Keyword "include_output"
Optional String.  Include base64 encoded output from the script. Note that any value of include_output will include the encoded output from the script.

#### Keyword "filters"
Optional String. A comma seperated list to show only results with a script name or tag.

#### Command-line options
| Option         | Effect                                        |
|----------------|-----------------------------------------------|
| --help, -h     | Show this help message and exit.              |
| -d, --debug    | Display more information about API responses. |
| -k, --insecure | Disable SSL certificate check                 |
