Delete an IP range

```bash
maas $PROFILE iprange delete [--help] [-d] [-k] id

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
Delete an IP range with the given id.





Read an IP range

```bash
maas $PROFILE iprange read [--help] [-d] [-k] id

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
Read an IP range with the given id.





Update an IP range

```bash
maas $PROFILE iprange update [--help] [-d] [-k] id [data ...]

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
Update an IP range with the given id.

##### Keyword "start_ip"
Optional String. Start IP address of this<br>range (inclusive).
##### Keyword "end_ip"
Optional String. End IP address of this range<br>(inclusive).
##### Keyword "comment"
Optional String. A description of this range.<br>(optional)


Note: This command accepts JSON.


Create an IP range

```bash
maas $PROFILE ipranges create [--help] [-d] [-k] [data ...]

```


#### **Command-line options**
| Option | Effect |
|---|---|
| --help, -h | Show this help message and exit. |
| -d, --debug | Display more information about API responses. |
| -k, --insecure | Disable SSL certificate check. |


#### **Keywords**
Create a new IP range.

##### Keyword "type"
Optional String. Type of this range. (``dynamic``<br>or ``reserved``)
##### Keyword "start_ip"
Optional String. Start IP address of this<br>range (inclusive).
##### Keyword "end_ip"
Optional String. End IP address of this range<br>(inclusive).
##### Keyword "subnet"
Optional Int. Subnet associated with this<br>range.
##### Keyword "comment"
Optional String. A description of this range.


Note: This command accepts JSON.


List all IP ranges

```bash
maas $PROFILE ipranges read [--help] [-d] [-k]

```


#### **Command-line options**
| Option | Effect |
|---|---|
| --help, -h | Show this help message and exit. |
| -d, --debug | Display more information about API responses. |
| -k, --insecure | Disable SSL certificate check. |


#### **Keywords**
List all available IP ranges.
