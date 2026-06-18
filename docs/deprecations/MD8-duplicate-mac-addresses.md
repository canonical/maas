# MD8 Duplicate MAC addresses

| Since | Remove |
|:---:|:---:|
| 3.6.0 | 3.8.0 |

This notice is raised as a warning that some interfaces in your MAAS database
share a MAC address that is stored in more than one format, which MAAS
currently treats as distinct interfaces.

Older versions of MAAS did not always normalize the MAC addresses of interfaces
before storing them. As a result, the same physical MAC address could be saved
more than once using a different case (for example `AA:BB:CC:DD:EE:FF` and
`aa:bb:cc:dd:ee:ff`), and MAAS treated those entries as distinct interfaces.

These duplicates are not just cosmetic. They introduce nondeterminism in
MAC-based identity resolution, because one physical MAC can map to multiple
stored interface records. This can happen as duplicates on the same machine
(two physical interfaces within the same node configuration) and as duplicates
across different machines, which breaks the assumption that one hardware MAC
maps to one unique MAAS identity. Only *physical* interfaces are affected;
bonds, bridges, and VLAN interfaces legitimately reuse the MAC address of one
of their child interfaces and are never reported.

From MAAS 3.8, MAC addresses are normalized on every write path and their
uniqueness is enforced at the database level. As part of that upgrade, MAAS
normalizes every existing MAC address; if doing so would collapse two physical
interfaces into a duplicate, **the upgrade to 3.8 will fail until the
duplicates are resolved**. Resolving the interfaces flagged by this notice
before upgrading ensures a smooth transition.

## How to resolve duplicate MAC addresses

### Open a region shell

Detecting these duplicates requires a region controller shell, because the
comparison must be performed on the normalized form of each MAC address.

- **Debian/package install:**

  ```bash
  sudo maas-region shell
  ```

- **Snap install:**

  ```bash
  sudo snap run --shell maas -c "maas-region shell"
  ```

This opens an interactive Django shell connected to your MAAS database.

### Detect duplicate MAC addresses

Paste the following script into the region shell. It groups physical interfaces
by the normalized form of their MAC address and reports only the entries that
bypass MAAS's uniqueness rules (duplicates on the same `node_config`, or the
same MAC on different machines):

```python
from collections import defaultdict

from maascommon.fields import normalise_macaddress
from maasserver.enum import INTERFACE_TYPE
from maasserver.models.interface import Interface

rows = (
    Interface.objects.filter(type=INTERFACE_TYPE.PHYSICAL)
    .exclude(mac_address__isnull=True)
    .exclude(node_config_id__isnull=True)
    .values_list(
        "id",
        "name",
        "mac_address",
        "node_config_id",
        "node_config__node_id",
        "node_config__node__hostname",
        "node_config__node__system_id",
    )
)

by_mac = defaultdict(list)
for iface in rows:
    iface_id, name, mac, nc_id, node_id, hostname, system_id = iface
    if not mac:
        continue
    try:
        normalized = normalise_macaddress(mac)
    except (ValueError, AttributeError):
        continue
    by_mac[normalized].append(
        (iface_id, name, mac, nc_id, node_id, hostname, system_id)
    )

found = False
for normalized in sorted(by_mac):
    ifaces = by_mac[normalized]
    if len(ifaces) < 2:
        continue
    node_ids = {iface[4] for iface in ifaces}
    node_config_ids = [iface[3] for iface in ifaces]
    same_node = len(node_ids) == 1
    distinct_node_configs = len(set(node_config_ids)) == len(node_config_ids)
    if same_node and distinct_node_configs:
        # The same MAC across distinct node_configs of one node is allowed.
        continue
    found = True
    print(normalized)
    for iface_id, name, mac, nc_id, node_id, hostname, system_id in sorted(
        ifaces
    ):
        print(
            f"    {hostname} ({system_id}) "
            f"interface id={iface_id} name={name} stored={mac}"
        )

if not found:
    print("No duplicate MAC addresses found.")
```

For each affected machine the output lists the interface `id`, `name`, and the
exact value stored in the database, so you can identify which entry to remove.
For example:

```
aa:bb:cc:dd:ee:ff
    webserver-01 (abc123) interface id=42 name=eth1 stored=AA:BB:CC:DD:EE:FF
    webserver-01 (abc123) interface id=51 name=eth2 stored=aa:bb:cc:dd:ee:ff
```

If there is nothing to fix, the script prints `No duplicate MAC addresses
found.`.

Type `exit()` or press `Ctrl-D` to leave the shell.

### Decide which interface to keep

For each reported group, keep the interface that holds the correct
configuration (links, subnet, VLAN, IP assignments) and remove the redundant
one. You can review an interface's configuration in the web UI under
**Machine > Network**, or from the CLI:

```bash
maas $PROFILE interface read $SYSTEM_ID $INTERFACE_ID
```

Replace `$PROFILE` with your logged-in MAAS CLI profile name, and use the
`system_id` and interface `id` values from the detection step.

### Remove the duplicate

Remove the redundant interface through a supported path so that related cleanup
(IP address release, DHCP reconfiguration) is performed correctly. Do **not**
delete interfaces directly from the database shell.

- **Web UI:** open **Machine > Network**, select the duplicate interface, and
  choose **Delete**.

- **CLI:**

  ```bash
  maas $PROFILE interface delete $SYSTEM_ID $INTERFACE_ID
  ```

  If you are not logged in yet, first run
  `maas login $PROFILE $MAAS_URL $API_KEY`.

### Verify

Re-run the detection script from the region shell. When no duplicates remain it
prints `No duplicate MAC addresses found.`. The admin notification is
re-evaluated when the region controller starts and clears automatically once
all duplicates are resolved.
