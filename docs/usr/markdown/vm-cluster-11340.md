Deletes a VM cluster

```bash
maas $PROFILE vm-cluster delete [--help] [-d] [-k] id [data ...]

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
Deletes a VM cluster with the given ID.

##### Keyword "decompose"
Optional Boolean. Whether to also<br>decompose all machines in the VM cluster on removal. If not provided, machines<br>will not be removed.


Note: This command accepts JSON.



```bash
maas $PROFILE vm-cluster read [--help] [-d] [-k] id

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






Update VMCluster

```bash
maas $PROFILE vm-cluster update [--help] [-d] [-k] id [data ...]

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
Update a specific VMCluster by ID.

##### Keyword "name"
Optional String. The VMCluster's name.
##### Keyword "pool"
Optional String. The name of the resource pool<br>associated with this VM Cluster -- this change is propagated to VMHosts
##### Keyword "zone"
Optional String. The VMCluster's zone.


Note: This command accepts JSON.


List VM Clusters

```bash
maas $PROFILE vm-clusters read [--help] [-d] [-k]

```


#### **Command-line options**
| Option | Effect |
|---|---|
| --help, -h | Show this help message and exit. |
| -d, --debug | Display more information about API responses. |
| -k, --insecure | Disable SSL certificate check. |


#### **Keywords**
Get a listing of all VM Clusters
