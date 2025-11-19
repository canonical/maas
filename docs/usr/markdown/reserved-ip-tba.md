Delete a reserved IP

```bash
maas $PROFILE reserved-ip delete [--help] [-d] [-k] id

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
Delete a reserved IP given its ID.





Read a Reserved IP

```bash
maas $PROFILE reserved-ip read [--help] [-d] [-k] id

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
Read a reserved IP given its ID.





Update a reserved IP

```bash
maas $PROFILE reserved-ip update [--help] [-d] [-k] id [data ...]

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
Update a reserved IP given its ID.

##### Keyword "comment"
Optional String. A description of this<br>reserved IP.


Note: This command accepts JSON.


Create a Reserved IP

```bash
maas $PROFILE reserved-ips create [--help] [-d] [-k] [data ...]

```


#### **Command-line options**
| Option | Effect |
|---|---|
| --help, -h | Show this help message and exit. |
| -d, --debug | Display more information about API responses. |
| -k, --insecure | Disable SSL certificate check. |


#### **Keywords**
Create a new Reserved IP.

##### Keyword "ip"
Optional String. The IP to be reserved.
##### Keyword "subnet"
Optional Int. ID of the subnet associated with<br>the IP to be reserved.
##### Keyword "mac_address"
Optional String. The MAC address that<br>should be linked to the reserved IP.
##### Keyword "comment"
Optional String. A description of this<br>reserved IP.


Note: This command accepts JSON.


List all available Reserved IPs

```bash
maas $PROFILE reserved-ips read [--help] [-d] [-k]

```


#### **Command-line options**
| Option | Effect |
|---|---|
| --help, -h | Show this help message and exit. |
| -d, --debug | Display more information about API responses. |
| -k, --insecure | Disable SSL certificate check. |


#### **Keywords**
List all IPs that have been reserved in MAAS.
