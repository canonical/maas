> *Errors or typos? Topics missing? Hard to read? <a href="https://docs.google.com/forms/d/e/1FAIpQLScIt3ffetkaKW3gDv6FDk7CfUTNYP_HGmqQotSTtj2htKkVBw/viewform?usp=pp_url&entry.1739714854=https://maas.io/docs/logging-and-auditing" target = "_blank">Let us know.</a>*

## Checking Logs in Systemd (MAAS 3.5 and Newer)

Starting with version 3.5, MAAS logs are saved in systemd. Use these commands to view the logs based on how you installed MAAS (snap or Debian packages):

### Region Controller Logs

 - Snap: `journalctl -u snap.maas.pebble -t maas-regiond`

 - Debian: `journalctl -u maas-regiond`

### Rack Controller Logs

 - `Snap: journalctl -u snap.maas.pebble -t maas-rackd`

 - `Debian: journalctl -u maas-rackd`

### Agent Logs

 - Snap: `journalctl -u snap.maas.pebble -t maas-agent`

 - Debian: `journalctl -u maas-agent`

### API Server Logs

 - Snap: `journalctl -u snap.maas.pebble -t maas-apiserver`

 - Debian: `journalctl -u maas-apiserver`

### Filtering Logs by Machine Name

To search for logs by machine name (hostname):

```
journalctl -u snap.maas.pebble -t maas-machine --since "-15m" MAAS_MACHINE_HOSTNAME=ace-cougar
```

## Checking Logs Before MAAS 3.5

Before version 3.5, MAAS saved logs in custom files. Here are some examples:

 - Region Controller: `/var/snap/maas/common/log/regiond.log` or `/var/log/maas/regiond.log`

 - Rack Controller: `/var/snap/maas/common/log/rackd.log` or `/var/log/maas/rackd.log`

 - Proxy: `/var/snap/maas/common/log/proxy/access.log`

### Using the less Command to Read Logs

```
less /var/snap/maas/common/log/regiond.log
```

## How to Read Event Logs

### Using the UI

 1. Go to the Machines list in the UI.

 2. Click on a machine and select the Events tab.

To see more details, click *View full history*.

### Using the Command Line

```
maas $PROFILE events query
```

### Formatting Event Logs with jq

To format the output neatly with jq:

```
maas admin events query | jq -r '(["HOSTNAME","TIMESTAMP","TYPE","DESCRIPTION"] | (., map(length*"-"))), (.events[] | [.hostname, .created, .type, .description // "-"]) | @tsv' | column -t -s $'\t'
```

## How to Read Commissioning Logs

### Using the UI

 1. Go to the Commissioning tab of a machine.

 2. Click the links to see the detailed logs.

### Using the Command Line

```
maas $PROFILE node-script-result read $SYSTEM_ID $RESULTS
```

## How to Read Testing Logs

Example Command:

```
maas $PROFILE node-script-result read $SYSTEM_ID type=smartctl-validate
```
