Enter keyword arguments in the form `key=value`.

## Add a tag

```bash
maas $PROFILE node-script add-tag [--help] [-d] [-k] name [data ...] 
```

#### Positional arguments
- name


Add a single tag to a script with the given name.

#### Keyword "tag"
Optional String. The tag being added.

#### Command-line options
| Option | Effect |
|-----|-----|
| --help, -h | Show this help message and exit. |
| -d, --debug | Display more information about API responses. |
| -k, --insecure | Disable SSL certificate check |

## Delete a script

```bash
maas $PROFILE node-script delete [--help] [-d] [-k] name [data ...] 
```

#### Positional arguments
- name

Deletes a script with the given name.

#### Command-line options
| Option | Effect |
|-----|-----|
| --help, -h | Show this help message and exit. |
| -d, --debug | Display more information about API responses. |
| -k, --insecure | Disable SSL certificate check |

## Download a script

```bash
maas $PROFILE node-script download [--help] [-d] [-k] name [data ...] 
```

#### Positional arguments
- name


Download a script with the given name.

#### Keyword "revision"
Optional Int. What revision to download, latest by default. Can use rev as a shortcut.

#### Command-line options
| Option | Effect |
|-----|-----|
| --help, -h | Show this help message and exit. |
| -d, --debug | Display more information about API responses. |
| -k, --insecure | Disable SSL certificate check |

## Return script metadata

```bash
maas $PROFILE node-script read [--help] [-d] [-k] name [data ...] 
```

#### Positional arguments
- name


Return metadata belonging to the script with the given name.

#### Keyword "include_script"
Optional String. Include the base64 encoded script content if any value is given for include_script.

#### Command-line options
| Option | Effect |
|-----|-----|
| --help, -h | Show this help message and exit. |
| -d, --debug | Display more information about API responses. |
| -k, --insecure | Disable SSL certificate check |

## Remove a tag

```bash
maas $PROFILE node-script remove-tag [--help] [-d] [-k] name [data ...] 
```

#### Positional arguments
- name


Remove a tag from a script with the given name.

#### Keyword "tag"
Optional String. The tag being removed.

#### Command-line options
| Option | Effect |
|-----|-----|
| --help, -h | Show this help message and exit. |
| -d, --debug | Display more information about API responses. |
| -k, --insecure | Disable SSL certificate check |

## Revert a script version

```bash
maas $PROFILE node-script revert [--help] [-d] [-k] name [data ...] 
```

#### Positional arguments
- name


Revert a script with the given name to an earlier version.

#### Keyword "to"
Optional Int.  What revision in the script's history to revert to. This can either be an ID or a negative number representing how far back to go.

#### Command-line options
| Option | Effect |
|-----|-----|
| --help, -h | Show this help message and exit. |
| -d, --debug | Display more information about API responses. |
| -k, --insecure | Disable SSL certificate check |

## Update a script

```bash
maas $PROFILE node-script update [--help] [-d] [-k] name [data ...] 
```

#### Positional arguments
- name


Update a script with the given name.

#### Keyword "title"
Optional String. The title of the script.

#### Keyword "description"
Optional String. A description of what the script does.

#### Keyword "tags"
Optional String. A comma separated list of tags for this script.

#### Keyword "type"
Optional String.  The type defines when the script should be used. Can be ``commissioning``, ``testing`` or ``release``.  It defaults to ``testing``.

#### Keyword "hardware_type"
Optional String.  The hardware_type defines what type of hardware the script is associated with. May be ``cpu``, ``memory``, ``storage``, ``network``, or ``node``.

#### Keyword "parallel"
Optional Int.  Whether the script may be run in parallel with other scripts. May be disabled to run by itself, instance to run along scripts with the same name, or any to run along any script. ``1`` == True, ``0`` == False.

#### Keyword "timeout"
Optional Int. How long the script is allowed to run before failing.  0 gives unlimited time, defaults to 0.

#### Keyword "destructive"
Optional Boolean.  Whether or not the script overwrites data on any drive on the running system. Destructive scripts can not be run on deployed systems. Defaults to false.

#### Keyword "script"
Optional String.  The content of the script to be uploaded in binary form. Note: this is not a normal parameter, but a file upload. Its filename is ignored; MAAS will know it by the name you pass to the request. Optionally you can ignore the name and script parameter in favor of uploading a single file as part of the request. 

#### Keyword "comment"
Optional String. A comment about what this change does.

#### Keyword "for_hardware"
Optional String.  A list of modalias, PCI IDs, and/or USB IDs the script will automatically run on. Must start with ``modalias:``, ``pci:``, or ``usb:``.

#### Keyword "may_reboot"
Optional Boolean. Whether or not the script may reboot the system while running.

#### Keyword "recommission"
Optional Boolean.  Whether built-in commissioning scripts should be rerun after successfully running this scripts.

#### Keyword "apply_configured_networking"
Optional Boolean. Whether to apply the provided network configuration before the script runs.

#### Command-line options
| Option | Effect |
|-----|-----|
| --help, -h | Show this help message and exit. |
| -d, --debug | Display more information about API responses. |
| -k, --insecure | Disable SSL certificate check |

## Create a new script

```bash
maas $PROFILE node-scripts create [--help] [-d] [-k] [data ...] 
```

Create a new script.

#### Keyword "name"
Required String. The name of the script.

#### Keyword "title"
Optional String. The title of the script.

#### Keyword "description"
Optional String. A description of what the script does.

#### Keyword "tags"
Optional String. A comma separated list of tags for this script.

#### Keyword "type"
Optional String.  The script_type defines when the script should be used: ``commissioning`` or ``testing`` or ``release``.  Defaults to ``testing``.

#### Keyword "hardware_type"
Optional String.  The hardware_type defines what type of hardware the script is associated with. May be CPU, memory, storage, network, or node.

#### Keyword "parallel"
Optional Int.  Whether the script may be run in parallel with other scripts. May be disabled to run by itself, instance to run along scripts with the same name, or any to run along any script. 1 == True, 0 == False.

#### Keyword "timeout"
Optional Int. How long the script is allowed to run before failing.  0 gives unlimited time, defaults to 0.

#### Keyword "destructive"
Optional Boolean.  Whether or not the script overwrites data on any drive on the running system. Destructive scripts can not be run on deployed systems. Defaults to false.

#### Keyword "script"
Optional String.  The content of the script to be uploaded in binary form. Note: this is not a normal parameter, but a file upload. Its filename is ignored; MAAS will know it by the name you pass to the request. Optionally you can ignore the name and script parameter in favor of uploading a single file as part of the request.

#### Keyword "comment"
Optional String. A comment about what this change does.

#### Keyword "for_hardware"
Optional String.  A list of modalias, PCI IDs, and/or USB IDs the script will automatically run on. Must start with ``modalias:``, ``pci:``, or ``usb:``. 

#### Keyword "may_reboot"
Optional Boolean. Whether or not the script may reboot the system while running.

#### Keyword "recommission"
Optional String.  Whether builtin commissioning scripts should be rerun after successfully running this scripts.

#### Command-line options
| Option | Effect |
|-----|-----|
| --help, -h | Show this help message and exit. |
| -d, --debug | Display more information about API responses. |
| -k, --insecure | Disable SSL certificate check |

## List stored scripts

```bash
maas $PROFILE node-scripts read [--help] [-d] [-k] [data ...] 
```

Return a list of stored scripts. Note that parameters should be passed in the URI, e.g.``/script/?type=testing``.

#### Keyword "type"
Optional String.  Only return scripts with the given type. This can be ``commissioning``, ``testing`` or ``release``. Defaults to showing all.

#### Keyword "hardware_type"
Optional String.  Only return scripts for the given hardware type.  Can be ``cpu``, ``memory``, ``storage``, ``network``, or ``node``.  Defaults to all.

#### Keyword "include_script"
Optional String. Include the base64- encoded script content.

#### Keyword "filters"
Optional String. A comma separated list to show only results with a script name or tag.

#### Command-line options
| Option | Effect |
|-----|-----|
| --help, -h | Show this help message and exit. |
| -d, --debug | Display more information about API responses. |
| -k, --insecure | Disable SSL certificate check |

