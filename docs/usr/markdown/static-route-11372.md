Delete static route

```bash
maas $PROFILE static-route delete [--help] [-d] [-k] id

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
Deletes the static route with the given ID.





Get a static route

```bash
maas $PROFILE static-route read [--help] [-d] [-k] id

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
Gets a static route with the given ID.





Update a static route

```bash
maas $PROFILE static-route update [--help] [-d] [-k] id [data ...]

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
Updates a static route with the given ID.

##### Keyword "source"
Optional String. Source subnet name for the<br>route.
##### Keyword "destination"
Optional String. Destination subnet name<br>for the route.
##### Keyword "gateway_ip"
Optional String. IP address of the<br>gateway on the source subnet.
##### Keyword "metric"
Optional Int. Weight of the route on a<br>deployed machine.


Note: This command accepts JSON.


Create a static route

```bash
maas $PROFILE static-routes create [--help] [-d] [-k] [data ...]

```


#### **Command-line options**
| Option | Effect |
|---|---|
| --help, -h | Show this help message and exit. |
| -d, --debug | Display more information about API responses. |
| -k, --insecure | Disable SSL certificate check. |


#### **Keywords**
Creates a static route.

##### Keyword "source"
Optional String. Source subnet name for the<br>route.
##### Keyword "destination"
Optional String. Destination subnet name<br>for the route.
##### Keyword "gateway_ip"
Optional String. IP address of the<br>gateway on the source subnet.
##### Keyword "metric"
Optional Int. Weight of the route on a<br>deployed machine.


Note: This command accepts JSON.


List static routes

```bash
maas $PROFILE static-routes read [--help] [-d] [-k]

```


#### **Command-line options**
| Option | Effect |
|---|---|
| --help, -h | Show this help message and exit. |
| -d, --debug | Display more information about API responses. |
| -k, --insecure | Disable SSL certificate check. |


#### **Keywords**
Lists all static routes.
