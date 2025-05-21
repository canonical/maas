MAAS version 3.2 and higher provide the capability to customise deployed machines, in that you can update hardware for a running machine on-the-fly. Specifically, MAAS will update a deployed machine’s data when you do any of the following things:

- add or remove disks
- add or remove network interfaces
- add or remove PCI devices
- add or remove USB devices

While deploying a machine, you can configure that machine to periodically sync its [hardware configuration](https://maas.io/docs/about-deploying-running-machines#p-17466-hardware-sync). Deployed machines will als. passively update changes to the BMC and tags for that machine, as these changes are made.

## Hardware sync 

Updating hardware on a deployed machine works by installing a special binary on the deployed machine. This binary is configured at a given interval and push hardware info to the MAAS metadata endpoint. By setting “enable_hw_sync” to true on a machine prior to deployment, MAAS will add configuration to install a systemd service and timer that will download the hardware sync binary. This binary then authenticates the machine, reads the hardware info from the machine and pushes it to MAAS. The interval is set globally in the MAAS settings.

Any changes in hardware are written to the machine’s configuration. Physical hardware changes will be preserved upon release, while virtual changes, such as a SR-IOV interface, will be dropped.

When deploying a machine from the UI, there is a new “enable_hw_sync” flag available for each machine. This flag marks a machine to be configured with live hardware updates.

When deploying from the CLI, there is an additional `enable_hw_sync` flag on `maas $PROFILE machine deploy`. This flag also marks a machine to be configured with live hardware updates. 

When using the API, there are two additional fields in the request:

- enable_hw_sync: (Boolean) - indicating whether hardware sync should be enabled on the machine, 
- sync_interval: (Int) - indicating the interval, in seconds, that should be set at time of deployment

With respect to `machine.read`, both the RESTful API and Websocket API add the following fields to a response:

- enable_hw_sync: Bool indicating whether hardware sync is enabled on the machine, 
- last_sync: Timestamp of the last time MAAS received hardware sync data for the machine,
- next_sync: Timestamp of the computed estimation of when the next sync should happen,
- sync_interval. Int the interval, in seconds, that was set at time of deployment
- is_sync_healthy: Bool indicating the sync is working normally when true, false when a sync is late or missing,

With respect to `config.list`, there is a new WebSocket Response result (new “hardware_sync_interval” option):

```nohighlight
[{
. name: "hardware_sync_interval",
. value: String in systemd time span forma. e.g. “15m”
. . . (only hours, minutes and seconds are recognised)
},…]

 . hardware_sync_interval is set to `15m` by default
config.update
WebSocket Request params - new “hardware_sync_interval” param

params: {
  name: "hardware_sync_interval",
  value: String in systemd time span format, e.g. “15m”
 }
```


The API does not throw errors when an invalid string is provided for these parameters.

