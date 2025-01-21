This article gives detailed commands and locations for MAAS logs.

## Systemd Log Commands (MAAS 3.5 and Newer)

|**Component**|**Snap Command**|**Debian Command**|
| --- | --- | --- |
|**Regiond**|`journalctl -u snap.maas.pebble -t maas-regiond`|`journalctl -u maas-regiond`|
|**Rackd**|`journalctl -u snap.maas.pebble -t maas-rackd`|`journalctl -u maas-rackd`|
|**API Server**|`journalctl -u snap.maas.pebble -t maas-apiserver`|`journalctl -u maas-apiserver`|
|**Proxy (squid)**|`journalctl -u snap.maas.pebble -t maas-proxy`|`journalctl -u maas-proxy`|
|**NTP (chrony)**|`journalctl -u snap.maas.pebble -t chronyd`|`journalctl -u chrony`|

## Log File Locations (Before MAAS 3.5)

|**Component**|**Snap Location**|**Debian Location**|
| --- | --- | --- |
|**Regiond**|`/var/snap/maas/common/log/regiond.log`|`/var/log/maas/regiond.log`|
|**Rackd**|`/var/snap/maas/common/log/rackd.log`|`/var/log/maas/rackd.log`|
|**maas.log**|`/var/snap/maas/common/log/maas.log`|`/var/log/maas/maas.log`|
