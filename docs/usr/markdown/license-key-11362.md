Delete license key

```bash
maas $PROFILE license-key delete [--help] [-d] [-k] osystem distro_series

```

#### **Positional arguments**
| Argument | Effect |
|---|---|
| osystem | The osystem parameter |
| distro_series | The distro_series parameter |


#### **Command-line options**
| Option | Effect |
|---|---|
| --help, -h | Show this help message and exit. |
| -d, --debug | Display more information about API responses. |
| -k, --insecure | Disable SSL certificate check. |


#### **Keywords**
Delete license key for the given operation system and<br>distro series.





Read license key

```bash
maas $PROFILE license-key read [--help] [-d] [-k] osystem distro_series

```

#### **Positional arguments**
| Argument | Effect |
|---|---|
| osystem | The osystem parameter |
| distro_series | The distro_series parameter |


#### **Command-line options**
| Option | Effect |
|---|---|
| --help, -h | Show this help message and exit. |
| -d, --debug | Display more information about API responses. |
| -k, --insecure | Disable SSL certificate check. |


#### **Keywords**
Read a license key for the given operating sytem and<br>distro series.





Update license key

```bash
maas $PROFILE license-key update [--help] [-d] [-k] osystem distro_series [data ...]

```

#### **Positional arguments**
| Argument | Effect |
|---|---|
| osystem | The osystem parameter |
| distro_series | The distro_series parameter |


#### **Command-line options**
| Option | Effect |
|---|---|
| --help, -h | Show this help message and exit. |
| -d, --debug | Display more information about API responses. |
| -k, --insecure | Disable SSL certificate check. |


#### **Keywords**
Update a license key for the given operating system and<br>distro series.

##### Keyword "license_key"
Optional String. License key for<br>osystem/distro_series combo.


Note: This command accepts JSON.


Define a license key

```bash
maas $PROFILE license-keys create [--help] [-d] [-k] [data ...]

```


#### **Command-line options**
| Option | Effect |
|---|---|
| --help, -h | Show this help message and exit. |
| -d, --debug | Display more information about API responses. |
| -k, --insecure | Disable SSL certificate check. |


#### **Keywords**
Define a license key.

##### Keyword "osystem"
Optional String. Operating system that the key<br>belongs to.
##### Keyword "distro_series"
Optional String. OS release that the key<br>belongs to.
##### Keyword "license_key"
Optional String. License key for<br>osystem/distro_series combo.


Note: This command accepts JSON.


List license keys

```bash
maas $PROFILE license-keys read [--help] [-d] [-k]

```


#### **Command-line options**
| Option | Effect |
|---|---|
| --help, -h | Show this help message and exit. |
| -d, --debug | Display more information about API responses. |
| -k, --insecure | Disable SSL certificate check. |


#### **Keywords**
List all available license keys.
