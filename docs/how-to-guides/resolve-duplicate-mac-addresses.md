# Resolve duplicate MAC addresses

Older versions of MAAS did not always normalize the MAC addresses of interfaces
before storing them. As a result, the same physical MAC address could be saved
more than once using a different case (for example `AA:BB:CC:DD:EE:FF` and
`aa:bb:cc:dd:ee:ff`), and MAAS treated those entries as distinct interfaces.

Newer versions normalize every MAC address on write, so no new duplicates of
this kind can be created. However, entries that already exist in the database
are not changed automatically. If MAAS detects such entries, it raises an admin
notification asking you to review and fix them manually. This page explains how
to find the affected interfaces and remove the duplicates.

> **Note:** Only *physical* interfaces are affected. Bonds, bridges, and VLAN
> interfaces legitimately reuse the MAC address of one of their child
> interfaces, so they are never reported as duplicates.

## Open a region shell

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

## Detect duplicate MAC addresses

Run the built-in report from the region shell:

```python
from maasserver.mac_normalization import print_duplicate_mac_report

print_duplicate_mac_report()
```

For each affected machine the output lists the interface `id`, `name`, and the
exact value stored in the database, so you can identify which entry to remove.
For example:

```
webserver-01 (abc123) -> aa:bb:cc:dd:ee:ff
    interface id=42 name=eth1 stored=AA:BB:CC:DD:EE:FF
    interface id=51 name=eth2 stored=aa:bb:cc:dd:ee:ff
```

If there is nothing to fix, the report prints `No duplicate MAC addresses
found.`.

Type `exit()` or press `Ctrl-D` to leave the shell.

## Decide which interface to keep

For each reported group, keep the interface that holds the correct
configuration (links, subnet, VLAN, IP assignments) and remove the redundant
one. You can review an interface's configuration in the web UI under
**Machine > Network**, or from the CLI:

```bash
maas $PROFILE interface read $SYSTEM_ID $INTERFACE_ID
```

Replace `$PROFILE` with your logged-in MAAS CLI profile name, and use the
`system_id` and interface `id` values from the detection step.

## Remove the duplicate

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

## Verify

Re-run the report from the region shell:

```python
from maasserver.mac_normalization import print_duplicate_mac_report

print_duplicate_mac_report()
```

When no duplicates remain it prints `No duplicate MAC addresses found.`. The
admin notification is re-evaluated when the region controller starts and clears
automatically once all duplicates are resolved.
