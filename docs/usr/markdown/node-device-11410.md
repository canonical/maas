Enter keyword arguments in the form `key=value`.

## Return node devices

```bash
maas $PROFILE node-devices read [--help] [-d] [-k] system_id [data ...] 
```

#### Positional arguments
- system_id


Return a list of devices attached to the node given by a system_id.

#### Keyword "bus"
Optional String. Only return devices attached to the specified bus. Can be PCIE or USB. Defaults to all.

#### Keyword "hardware_type"
Optional String. Only return scripts for the given hardware type. Can be ``node``, ``cpu``, ``memory``, ``storage`` or ``gpu``. Defaults to all.

#### Keyword "vendor_id"
Optional String. Only return devices which have the specified vendor id.

#### Keyword "product_id"
Optional String. Only return devices which have the specified product id.

#### Keyword "vendor_name"
Optional String. Only return devices which have the specified vendor_name.

#### Keyword "product_name"
Optional String. Only return devices which have the specified product_name.

#### Keyword "commissioning_driver"
Optional String. Only return devices which use the specified driver when commissioning.

#### Command-line options
| Option | Effect |
|-----|-----|
| --help, -h | Show this help message and exit. |
| -d, --debug | Display more information about API responses. |
| -k, --insecure | Disable SSL certificate check |

