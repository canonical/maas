This page describes basic MAAS logging operations.

## Logging overview

From MAAS 3.5 logs are collected by the `journal` and for the snap installation `systemd` was replaced by `pebble`. The 
following sections explain how to access the logs for every service depending on the MAAS version and the installation type. 

### Services logs in MAAS 3.5 and above

For MAAS 3.5 and above, logs are collected by the `journal`. MAAS is composed by many services and the way to access logs 
depends by the installation type.

| Service                                                                                                                                 | snap                                                | deb                                                                 | notes                                                                                                                     |
|-----------------------------------------------------------------------------------------------------------------------------------------|-----------------------------------------------------|---------------------------------------------------------------------|---------------------------------------------------------------------------------------------------------------------------|
| regiond                                                                                                                                 | `journalctl -t maas-regiond`                        | `journalctl -t regiond`                                             |                                                                                                                           |
| maas-log                                                                                                                                | `journalctl -t maas-log`                            | `journalctl -t maas-log`                                            |                                                                                                                           |
| http (nginx)                                                                                                                            | `journalctl -t maas-http`                           | `less /var/log/maas/http/access.log # (or error.log)`               |                                                                                                                           |
| apiserver                                                                                                                               | `journalctl -t maas-apiserver`                      | `journalctl -t maas-apiserver`                                      |                                                                                                                           |
| DNS (named)                                                                                                                             | `journalctl -t named -u snap.maas.pebble.service`   | `journalctl -t named`                                               |                                                                                                                           |
| temporal                                                                                                                                | `journalctl -t maas-temporal`                       | `journalctl -t temporal-server`                                     |                                                                                                                           |
| proxy (squid)                                                                                                                           | `journalctl -t maas-proxy`                          | `less /var/log/maas/proxy/access.log # (or error.log or store.log)` |                                                                                                                           |
| NTP (chrony)                                                                                                                            | `journalctl -t chronyd -u snap.maas.pebble.service` | `journalctl -u chronyd`                                             |                                                                                                                           |
| Syslog (rsyslog)                                                                                                                        | `journalctl -t maas-machine`                        | `journalctl -t maas-machine`                                        |                                                                                                                           |
| rackd                                                                                                                                   | `journalctl -t maas-rackd`                          | `journalctl -t rackd`                                               |                                                                                                                           |
| agent                                                                                                                                   | `journalctl -t maas-agent`                          | `journalctl -t maas-agent`                                          |                                                                                                                           |
| DHCP (dhcpd)                                                                                                                            | `journalctl -t dhcpd -u snap.maas.pebble.service`   | `journalctl -t dhcpd`                                               | There is no particularly easy way to differentiate between `dhcpd` and `dhcpd6`, although you can `grep` for a “PID file: /var/snap/maas/common/maas/dhcp/dhcpd6?\.pid ” message, and then use the PID to filter logs in journal appending `SYSLOG_PID=<the pid>` |

### Services logs in MAAS 3.4 and below

For MAAS 3.4 and below, logs are collected in dedicated files under MAAS control.

| Service                                                                                                                                 | snap                                                                            | deb                                                                 |
|-----------------------------------------------------------------------------------------------------------------------------------------|---------------------------------------------------------------------------------|---------------------------------------------------------------------|
| regiond                                                                                                                                 | `less /var/snap/maas/common/log/regiond.log`                                    | `less /var/log/maas/regiond.log`                                    |
| maas-log                                                                                                                                | `less /var/snap/maas/common/log/maas.log`                                       | `less /var/log/maas/maas.log`                                       |
| http (nginx)                                                                                                                            | `less /var/snap/maas/common/log/access.log # (or error.log)`                    | `less /var/log/maas/http/access.log # (or error.log)`               |
| DNS (named)                                                                                                                             | `less /var/snap/maas/common/log/named.log`                                      | `less /var/log/maas/named.log`                                      |
| proxy (squid)                                                                                                                           | `less /var/snap/maas/common/log/proxy/access.log # (or cache.log or store.log)` | `less /var/log/maas/proxy/access.log # (or error.log or store.log)` |
| NTP (chrony)                                                                                                                            | `less /var/snap/maas/common/log/chrony.log`                                     | `less /var/log/maas/chrony.log`                                     |
| Syslog (rsyslog)                                                                                                                        | `/var/snap/maas/common/log/rsyslog/$MACHINE_NAME/$RELEVANT_DATE/messages`       | `/var/log/maas/rsyslog/$MACHINE_NAME/$RELEVANT_DATE/messages`       |
| rackd                                                                                                                                   | `less /var/snap/maas/common/log/rackd.log`                                      | `less /var/log/maas/rackd.log`                                      |
| DHCP (dhcpd)                                                                                                                            | `less /var/snap/maas/common/log/dhcpd.log`                                      | `less /var/log/maas/dhcpd.log`                                      |

## Remote syslog (3.4 UI)

To enable remote logging, choose *Settings* > *Network* > *Syslog*, and enter your syslog server's IP/URL under *Remote syslog server to forward machine logs*.

## Remote syslog (3.3-- UI)

To enable remote logging, choose *Settings* > *Network services* > *Syslog*; add your syslog server's IP/UL; and click *Save*.

## Remote syslog (CLI)

```nohighlight
maas $PROFILE maas set-config name="remote_syslog" value="$SYSLOG_FQDN"
# Example for setting syslog server to 192.168.100.11:
maas $PROFILE maas set-config name="remote_syslog" value=192.168.100.11
# To reset to default (sending syslog to MAAS region controllers):
maas $PROFILE maas set-config name="remote_syslog" value="
```

Note**: Only machine syslog information is forwarded, not MAAS controllers syslog files.

## Events query (CLI)

The most efficient way to review events is using the `events query` CLI sub-command. This command allows filtering and summarizing events. Use `jq` and various filters to simplify output interpretation.

## Basic queries

```nohighlight
maas $PROFILE events query
```

This command returns a lengthy JSON output, which can be simplified using `jq` and various filters, making it more readable.

To list the available filters, execute

```nohighlight
maas $PROFILE events query -h
```

## Using jq with events

A `jq` command example for readable output:

```nohighlight
maas $PROFILE events query limit=20 | jq -r '(["USERNAME","NODE","HOSTNAME","LEVEL","DATE","TYPE","EVENT"] | (., map(length*"-"))), (.events[] | [.username,.node,.hostname,.level,.created,.type,.description]) | @tsv' | column -t -s$'\t'
```

## Auditing finesse

Audit events, tagged with `AUDIT`, record MAAS configuration changes and machine state transitions. They're essential for tracking user actions and system updates, especially in multi-user environments.

Use audit events alongside `jq` and command-line text tools to analyze actions like machine deletions, configuration changes, and user activities. This can provide insights into system changes and help identify areas for attention or improvement.

