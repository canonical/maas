Pinpoint issues with four types of log files:

1. Firewall logs
2. Web server logs
3. MAAS log files
4. System log files

You can also account for user activities with audit logs.

> *See [How to use logging](https://maas.io/docs/how-to-use-logging) for usage instructions.*

## Firewall logs

Ubuntu's UncomplicatedFirewall ([UFW](https://wiki.ubuntu.com/UncomplicatedFirewall)) serves as a front-end for [iptables](https://help.ubuntu.com/community/IptablesHowTo). To secure your MAAS setup, regularly review logs located in `/var/log/ufw*`. 

Find red flags in UFW and iptables logs by looking for key patterns:

- Be wary of traffic probing unused ports, which may indicate an active port scanner:
  
```nohighlight
    blocked incoming tcp connection request from 96.39.208.43:8240 to 128.17.92.85:6002
```

- Cross-reference unusual port numbers against databases of [known hacker tools](http://www.relevanttechnologies.com/resources_4.asp).

- Look for repeated, failed access attempts from the same domain, IP, or subnet:

```nohighlight
    blocked incoming tcp connection request from 96.39.208.43:49343 to 64.242.119.18:31337
```
    
- Examine repeated, errant messages from within your network, which may indicate a Trojan horse:.

```nohighlight
    blocked outgoing tcp packet from 192.168.23.100:5240 to 96.38.231.18:443 as FIN:ACK received, but there is no active connection.
```

## Web server logs

Use a log analysis tool, or inspect raw logs stored in paths like `/var/log/httpd/` or `/var/log/apache2`, looking for:

- Multiple, rapid-fire requests
- Multiple failed login attempts
- Requests for non-existent pages
- Signs of SQL injection and Web shell attempts

## MAAS logs

| Pkg Fmt  | Look for failed logins in...           |
|----------|-----------------------------------------|
| Snap     | `/var/snap/maas/common/log/regiond.log` |
| Packages | `/var/log/maas/regiond.log`             |

For example, a legitimate login request might resemble:

```nohighlight
    2020-03-31 21:17:56 regiond: [info] 10.132.172.1 GET /MAAS/accounts/login/ HTTP/1.1 --> 200 OK
```

## System logs

### Systemd log commands (MAAS 3.5 and Newer)

|**Component**|**Snap Command**|**Debian Command**|
| --- | --- | --- |
|**Regiond**|`journalctl -u snap.maas.pebble -t maas-regiond`|`journalctl -u maas-regiond`|
|**Rackd**|`journalctl -u snap.maas.pebble -t maas-rackd`|`journalctl -u maas-rackd`|
|**API Server**|`journalctl -u snap.maas.pebble -t maas-apiserver`|`journalctl -u maas-apiserver`|
|**Proxy (squid)**|`journalctl -u snap.maas.pebble -t maas-proxy`|`journalctl -u maas-proxy`|
|**NTP (chrony)**|`journalctl -u snap.maas.pebble -t chronyd`|`journalctl -u chrony`|

### Log file locations (Before MAAS 3.5)

|**Component**|**Snap Location**|**Debian Location**|
| --- | --- | --- |
|**Regiond**|`/var/snap/maas/common/log/regiond.log`|`/var/log/maas/regiond.log`|
|**Rackd**|`/var/snap/maas/common/log/rackd.log`|`/var/log/maas/rackd.log`|
|**maas.log**|`/var/snap/maas/common/log/maas.log`|`/var/log/maas/maas.log`|

## Audit logs

Read the following information from MAAS audit logs.

| Event type    | Endpoint | Req'd params | Audited user event                                             |
|---------------|----------|--------------|----------------------------------------------------------------|
| AUTHORISATION | API      | None         | "Created token."                                               |
| AUTHORISATION | API      | None         | "Deleted token."                                               |
| NODE          | API      | `system_id`  | "Created bcache."                                              |
| NODE          | API      | `system_id`  | "Deleted bcache."                                              |
| NODE          | API      | `system_id`  | "Updated bcache."                                              |
| NODE          | API      | `system_id`  | "Created bcache cache set."                                    |
| NODE          | API      | `system_id`  | "Deleted bcache cache set."                                    |
| NODE          | API      | `system_id`  | "Updated bcache cache set."                                    |
|               | API      | None         | "Deleted script `script.name`."                                |
|               | API      | None         | "Deleted DHCP snippet `dhcp_snippet.name`."                    |
|               | API      | None         | "Deleted package repository `package_repository.name`."        |
| SETTINGS      | API      | None         | "Reverted script `script.name` to revision `revision_number`." |
|               | API      | None         | "Added tag `tag` to script `script.name`."                     |
|               | API      | None         | "Removed tag `tag` from script `script.name`."                 |
|               | API      | None         | "Imported SSH keys."                                           |
|               | API      | None         | "Deleted SSH key id=`id`."                                     |
|               | API      | None         | "Imported SSH keys."                                           |
|               | API      | None         | "Tag `name` {action}."                                         |
| TAG           | API      | None         | "Tag `tag.name` deleted."                                      |
|               | API      | None         | "Tag `tag.name` created."                                      |
|               | API      | None         | "Created SSH key."                                             |
|               | API      | None         | "Deleted SSH key."                                             |
| AUTHORISATION |          | None         | "Created SSL key."                                             |
|               |          | None         | "Updated `dhcp_snippet.name`."                                 |
|               |          | None         | "Updated `package_repository.name`."                           |
| SETTINGS      |          | None         | "Saved script `script.name`."                                  |
| SETTINGS      | CLI      | None         | "Updated configuration setting `key`."                         |

