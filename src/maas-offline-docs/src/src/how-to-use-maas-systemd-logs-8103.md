MAAS logs considerable runtime information to standard log files, useful when things don't work as expected.  Prior to version 3.5, MAAS used custom log files for different components of the MAAS architecture.  In version 3.5, all [logging has been transferred](/t/about-system-logging/????) to the standard `systemd` logs.   This page gives a summary of how to access runtime logging for both version groups.

## MAAS 3.5 log commands

### Pebble (snap-only)

```nohighlight
journalctl -u snap.maas.pebble -t maas.pebble
```

### Regiond (ex-regiond.log)

For the snap, use:

```nohighlight
journalctl -u snap.maas.pebble -t maas-regiond
```

For the debian packages, use: 

```nohighlight
journalctl -u maas-regiond
```

### Rackd (ex-rackd.log)

For the snap, use:: 

```nohighlight
journalctl -u snap.maas.pebble -t maas-rackd
```

For the debian packages, use: 

```nohighlight
journalctl -u maas-rackd
```

### MAAS Agent

For the snap, use:: 

```nohighlight
journalctl -u snap.maas.pebble -t maas-agent
```

For the debian packages, use: 

```nohighlight
journalctl -u maas-agent
```

### maas.log

For the snap, use:: 

```nohighlight
journalctl -u snap.maas.pebble -t maas-log
```

For the debian packages, use: 

```nohighlight
journalctl -u maas-syslog -t maas-log
```

### API server

For the snap, use:: 

```nohighlight
journalctl -u snap.maas.pebble -t maas-apiserver
```

For the debian packages, use: 

```nohighlight
journalctl -u maas-apiserver
```

### Temporal

For the snap, use:: 

```nohighlight
journalctl -u snap.maas.pebble -t maas-temporal
```

For the debian packages, use: 

```nohighlight
journalctl -u maas-temporal
```

### HTTP (nginx)

For the snap, use:: 

```nohighlight
journalctl -u snap.maas.pebble -t maas-http
```

For the debian packages, use: 

```nohighlight
journalctl -u maas-http
```

### Proxy (squid)

For the snap, use:: 

```nohighlight
journalctl -u snap.maas.pebble -t maas-proxy
```

For the debian packages, use: 

```nohighlight
journalctl -u maas-proxy
```

### NTP (chrony)

For the snap, use:: 

```nohighlight
journalctl -u snap.maas.pebble -t chronyd
```

For the debian packages, use: 

```nohighlight
journalctl -u chrony
```

### DNS (bind9)

For the snap, use:: 

```nohighlight
journalctl -u snap.maas.pebble -t named
```

For the debian packages, use: 

```nohighlight
journalctl -u named
```

### Syslog (rsyslog)

For the snap, use:: 

```nohighlight
journalctl -u snap.maas.pebble -t maas-machine
```

For the debian packages, use: 

```nohighlight
journalctl -u maas-syslog
```

* Fields to filter over:
  * MAAS_MACHINE_IP
  * MAAS_MACHINE_HOSTNAME
  * MAAS_MACHINE_SYSLOG_TAG
  * MAAS_MACHINE_PID (to filter over remote machine process IDs)
  * MAAS_MACHINE_TIMESTAMP (to troubleshoot possible time sync issues)

For example, if using the snap, use a command like this:

```nohighlight
journalctl -u snap.maas.pebble -t maas-machine --since "-15m" MAAS_MACHINE_HOSTNAME=ace-cougar MAAS_MACHINE_SYSLOG_TAG=systemd
```

On the other hand, if using debian packages, use a command similar to:

```nohighlight
journalctl -u maas-syslog -t maas-machine --since "-15m" MAAS_MACHINE_HOSTNAME=ace-cougar MAAS_MACHINE_SYSLOG_TAG=systemd
```

### DHCP (dhcpd, dhcpd6)

For the snap, use:: 

```nohighlight
journalctl -u snap.maas.pebble -t dhcpd
```

For the debian packages, use: 

```nohighlight
journalctl -u maas-dhcpd
```

## Pre-3.5 log commands

### Supervisor (snap-only)

For the snap, use:

```nohighlight
less /var/snap/maas/common/log/supervisor-run.log
```

```nohighlight
journalctl -u snap.maas.supervisor
```

### Regiond

For the snap, use:

```nohighlight
less /var/snap/maas/common/log/regiond.log
```

For the debian packages, use: 

```nohighlight
less /var/log/maas/regiond.log
```

### Rackd

For the snap, use:: 

```nohighlight
less /var/snap/maas/common/log/rackd.log
```

For the debian packages, use: 

```nohighlight
less /var/log/maas/rackd.log
```

### maas.log

For the snap, use:: 

```nohighlight
less /var/snap/maas/common/log/maas.log
```

For the debian packages, use: 

```nohighlight
less /var/log/maas/maas.log
```

### HTTP (nginx)

For the snap, use::

```nohighlight
less /var/snap/maas/common/log/http/access.log (or error.log)
```

```nohighlight
less /var/snap/maas/common/log/nginx.log
```

For the debian packages, use:

```nohighlight
less /var/log/maas/http/access.log (or error.log)
```

```nohighlight
journalctl -u maas-http
```

### Proxy (squid)

For the snap, use:: 

```nohighlight
less /var/snap/maas/common/log/proxy/access.log (or cache.log or storage.log)
```

For the debian packages, use: 

```nohighlight
less /var/log/maas/proxy/access.log (or cache.log or storage.log)
```

### NTP (chrony)

For the debian packages, use: 

```nohighlight
journalctl -u chrony
```

### DNS (bind9)

For the snap, use:: 

```nohighlight
less /var/snap/maas/common/log/named.log
```

For the debian packages, use: 

```nohighlight
journalctl -u named
```

### Syslog (rsyslog)

For the snap, use::

```nohighlight
less /var/snap/maas/common/log/rsyslog.log
```

```nohighlight
less /var/snap/maas/common/log/rsyslog/MACHINE_HOSTNAME/DATE/messages
```

For the debian packages, use:

```nohighlight
journalctl -u maas-syslog
```
```nohighlight
less /var/log/maas/rsyslog/MACHINE_HOSTNAME/DATE/messages
```

### DHCP (dhcpd, dhcpd6)

For the snap, use:: 

```nohighlight
less /var/snap/maas/common/log/dhcpd.log
```

For the debian packages, use: 

```nohighlight
journalctl -u dhcpd
```