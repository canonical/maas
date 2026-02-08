Add a tag

```bash
maas $PROFILE node-script add-tag [--help] [-d] [-k] name [data ...]

```

#### **Positional arguments**
| Argument | Effect |
|---|---|
| name | The name of the resource (e.g., `my-machine`, `my-zone`) |


#### **Command-line options**
| Option | Effect |
|---|---|
| --help, -h | Show this help message and exit. |
| -d, --debug | Display more information about API responses. |
| -k, --insecure | Disable SSL certificate check. |


#### **Keywords**
Add a single tag to a script with the given name.

##### Keyword "tag"
Optional String. The tag being added.


Note: This command accepts JSON.


Delete a script

```bash
maas $PROFILE node-script delete [--help] [-d] [-k] name

```

#### **Positional arguments**
| Argument | Effect |
|---|---|
| name | The name of the resource (e.g., `my-machine`, `my-zone`) |


#### **Command-line options**
| Option | Effect |
|---|---|
| --help, -h | Show this help message and exit. |
| -d, --debug | Display more information about API responses. |
| -k, --insecure | Disable SSL certificate check. |


#### **Keywords**
Deletes a script with the given name.





Download a script

```bash
maas $PROFILE node-script download [--help] [-d] [-k] name [data ...]

```

#### **Positional arguments**
| Argument | Effect |
|---|---|
| name | The name of the resource (e.g., `my-machine`, `my-zone`) |


#### **Command-line options**
| Option | Effect |
|---|---|
| --help, -h | Show this help message and exit. |
| -d, --debug | Display more information about API responses. |
| -k, --insecure | Disable SSL certificate check. |


#### **Keywords**
Download a script with the given name.

##### Keyword "revision"
Optional Int. What revision to download,<br>latest by default. Can use rev as a shortcut.


Note: This command accepts JSON.


Return script metadata

```bash
maas $PROFILE node-script read [--help] [-d] [-k] name [data ...]

```

#### **Positional arguments**
| Argument | Effect |
|---|---|
| name | The name of the resource (e.g., `my-machine`, `my-zone`) |


#### **Command-line options**
| Option | Effect |
|---|---|
| --help, -h | Show this help message and exit. |
| -d, --debug | Display more information about API responses. |
| -k, --insecure | Disable SSL certificate check. |


#### **Keywords**
Return metadata belonging to the script with the given<br>name.

##### Keyword "include_script"
Optional String. Include the base64<br>encoded script content if any value is given for include_script.


Note: This command accepts JSON.


Remove a tag

```bash
maas $PROFILE node-script remove-tag [--help] [-d] [-k] name [data ...]

```

#### **Positional arguments**
| Argument | Effect |
|---|---|
| name | The name of the resource (e.g., `my-machine`, `my-zone`) |


#### **Command-line options**
| Option | Effect |
|---|---|
| --help, -h | Show this help message and exit. |
| -d, --debug | Display more information about API responses. |
| -k, --insecure | Disable SSL certificate check. |


#### **Keywords**
Remove a tag from a script with the given name.

##### Keyword "tag"
Optional String. The tag being removed.


Note: This command accepts JSON.


Revert a script version

```bash
maas $PROFILE node-script revert [--help] [-d] [-k] name [data ...]

```

#### **Positional arguments**
| Argument | Effect |
|---|---|
| name | The name of the resource (e.g., `my-machine`, `my-zone`) |


#### **Command-line options**
| Option | Effect |
|---|---|
| --help, -h | Show this help message and exit. |
| -d, --debug | Display more information about API responses. |
| -k, --insecure | Disable SSL certificate check. |


#### **Keywords**
Revert a script with the given name to an earlier version.

##### Keyword "to"
Optional Int. What revision in the script's<br>history to revert to. This can either be an ID or a negative number<br>representing how far back to go.


Note: This command accepts JSON.


Update a script

```bash
maas $PROFILE node-script update [--help] [-d] [-k] name [data ...]

```

#### **Positional arguments**
| Argument | Effect |
|---|---|
| name | The name of the resource (e.g., `my-machine`, `my-zone`) |


#### **Command-line options**
| Option | Effect |
|---|---|
| --help, -h | Show this help message and exit. |
| -d, --debug | Display more information about API responses. |
| -k, --insecure | Disable SSL certificate check. |


#### **Keywords**
Update a script with the given name.

##### Keyword "title"
Optional String. The title of the script.
##### Keyword "description"
Optional String. A description of what<br>the script does.
##### Keyword "tags"
Optional String. A comma separated list of tags<br>for this script.
##### Keyword "type"
Optional String. The type defines when the<br>script should be used. Can be ``commissioing``, ``testing`` or<br>``release``. It defaults to ``testing``.
##### Keyword "hardware_type"
Optional String. The hardware_type<br>defines what type of hardware the script is associated with. May be<br>``cpu``, ``memory``, ``storage``, ``network``, or ``node``.
##### Keyword "parallel"
Optional Int. Whether the script may be<br>run in parallel with other scripts. May be disabled to run by itself,<br>instance to run along scripts with the same name, or any to run along<br>any script. ``1`` == True, ``0`` == False.
##### Keyword "timeout"
Optional Int. How long the script is allowed<br>to run before failing. 0 gives unlimited time, defaults to 0.
##### Keyword "destructive"
Optional Boolean. Whether or not the<br>script overwrites data on any drive on the running system. Destructive<br>scripts can not be run on deployed systems. Defaults to false.
##### Keyword "script"
Optional String. The content of the script to<br>be uploaded in binary form. Note: this is not a normal parameter, but<br>a file upload. Its filename is ignored; MAAS will know it by the name<br>you pass to the request. Optionally you can ignore the name and script<br>parameter in favor of uploading a single file as part of the request.
##### Keyword "comment"
Optional String. A comment about what this<br>change does.
##### Keyword "for_hardware"
Optional String. A list of modalias, PCI<br>IDs, and/or USB IDs the script will automatically run on. Must start<br>with ``modalias:``, ``pci:``, or ``usb:``.
##### Keyword "may_reboot"
Optional Boolean. Whether or not the<br>script may reboot the system while running.
##### Keyword "recommission"
Optional Boolean. Whether built-in<br>commissioning scripts should be rerun after successfully running this<br>scripts.
##### Keyword "apply_configured_networking"
Optional Boolean. Whether<br>to apply the provided network configuration before the script runs.


Note: This command accepts JSON.


Create a new script

```bash
maas $PROFILE node-scripts create [--help] [-d] [-k] [data ...]

```


#### **Command-line options**
| Option | Effect |
|---|---|
| --help, -h | Show this help message and exit. |
| -d, --debug | Display more information about API responses. |
| -k, --insecure | Disable SSL certificate check. |


#### **Keywords**
Create a new script.

##### Keyword "name"
Optional String. The name of the script.
##### Keyword "title"
Optional String. The title of the script.
##### Keyword "description"
Optional String. A description of what<br>the script does.
##### Keyword "tags"
Optional String. A comma separated list of tags<br>for this script.
##### Keyword "type"
Optional String. The script_type defines when<br>the script should be used: ``commissioning`` or ``testing`` or<br>``release` or ``deployment``. Defaults to ``testing``.
##### Keyword "hardware_type"
Optional String. The hardware_type<br>defines what type of hardware the script is associated with. May be<br>CPU, memory, storage, network, or node.
##### Keyword "parallel"
Optional Int. Whether the script may be<br>run in parallel with other scripts. May be disabled to run by itself,<br>instance to run along scripts with the same name, or any to run along<br>any script. 1 == True, 0 == False.
##### Keyword "timeout"
Optional Int. How long the script is allowed<br>to run before failing. 0 gives unlimited time, defaults to 0.
##### Keyword "destructive"
Optional Boolean. Whether or not the<br>script overwrites data on any drive on the running system. Destructive<br>scripts can not be run on deployed systems. Defaults to false.
##### Keyword "script"
Optional String. The content of the script to<br>be uploaded in binary form. Note: this is not a normal parameter, but<br>a file upload. Its filename is ignored; MAAS will know it by the name<br>you pass to the request. Optionally you can ignore the name and script<br>parameter in favor of uploading a single file as part of the request.
##### Keyword "comment"
Optional String. A comment about what this<br>change does.
##### Keyword "for_hardware"
Optional String. A list of modalias, PCI<br>IDs, and/or USB IDs the script will automatically run on. Must start<br>with ``modalias:``, ``pci:``, or ``usb:``.
##### Keyword "may_reboot"
Optional Boolean. Whether or not the<br>script may reboot the system while running.
##### Keyword "recommission"
Optional String. Whether builtin<br>commissioning scripts should be rerun after successfully running this<br>scripts.


Note: This command accepts JSON.


List stored scripts

```bash
maas $PROFILE node-scripts read [--help] [-d] [-k] [data ...]

```


#### **Command-line options**
| Option | Effect |
|---|---|
| --help, -h | Show this help message and exit. |
| -d, --debug | Display more information about API responses. |
| -k, --insecure | Disable SSL certificate check. |


#### **Keywords**
Return a list of stored scripts. Note that parameters should be passed in the URI. E.g.<br>``/script/?type=testing``.

##### Keyword "type"
Optional String. Only return scripts with the<br>given type. This can be ``commissioning``, ``testing`` or<br>``release``. Defaults to showing all.
##### Keyword "hardware_type"
Optional String. Only return scripts<br>for the given hardware type. Can be ``cpu``, ``memory``, ``storage``,<br>``network``, or ``node``. Defaults to all.
##### Keyword "include_script"
Optional String. Include the base64-<br>encoded script content.
##### Keyword "filters"
Optional String. A comma separated list to<br>show only results with a script name or tag.


Note: This command accepts JSON.
