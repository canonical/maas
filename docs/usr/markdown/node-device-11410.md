Delete a node device

```bash
maas $PROFILE node-device delete [--help] [-d] [-k] system_id id

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
Delete a node device with the given system_id and id.<br>If the device is still present in the system it will be recreated<br>when the node is commissioned.





Return a specific node device

```bash
maas $PROFILE node-device read [--help] [-d] [-k] system_id id

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
Return a node device with the given system_id and node<br>device id.





Return node devices

```bash
maas $PROFILE node-devices read [--help] [-d] [-k] system_id [data ...]

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
Return a list of devices attached to the node given by<br>a system_id.

##### Keyword "bus"
Optional String. Only return devices attached to<br>the specified bus. Can be PCIE or USB. Defaults to all.
##### Keyword "hardware_type"
Optional String. Only return scripts<br>for the given hardware type. Can be ``node``, ``cpu``, ``memory``,<br>``storage`` or ``gpu``. Defaults to all.
##### Keyword "vendor_id"
Optional String. Only return devices which<br>have the specified vendor id.
##### Keyword "product_id"
Optional String. Only return devices which<br>have the specified product id.
##### Keyword "vendor_name"
Optional String. Only return devices<br>which have the specified vendor_name.
##### Keyword "product_name"
Optional String. Only return devices<br>which have the specified product_name.
##### Keyword "commissioning_driver"
Optional String. Only return<br>devices which use the specified driver when commissioning.


Note: This command accepts JSON.
