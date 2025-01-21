> *Errors or typos? Topics missing? Hard to read? <a href="https://docs.google.com/forms/d/e/1FAIpQLScIt3ffetkaKW3gDv6FDk7CfUTNYP_HGmqQotSTtj2htKkVBw/viewform?usp=pp_url&entry.1739714854=https://maas.io/docs/setting-up-power-drivers" target = "_blank">Let us know.</a>*

To manage a machine, MAAS must be able to power cycle it, usually through the machine's [BMC](https://en.wikipedia.org/wiki/Intelligent_Platform_Management_Interface#Baseboard_management_controller)**^** card. Until you configure the power type, a newly-added machine can't be enlisted and used by MAAS.  This page provides a number of detailed power driver procedures, accompanied by necessary explanation.

## Cipher suites (3.2++) 

Cipher suite selection is a manual task because different BMCs have varying orders, causing incorrect discovery. You can specify the cipher suite to use with a BMC during power configuration. The default suite is 3, known for its low security. It's your responsibility to choose a more secure suite if needed and supported.

## Redfish over IPMI (3.2++)

Redfish serves as an alternative to IPMI for interfacing with BMCs. Offering extended features compared to IPMI, Redfish is poised to replace it as the default.
MAAS 3.2 improved Redfish support, prioritising it over IPMI when:

- The BMC has an active Redfish Host Interface
- The MAAS host can access that interface

With version 3.2, MAAS brings auto-detection and preference for Redfish when enabled and available.

Unregistered machines on the MAAS PXE network can be manually booted. They enter an ephemeral environment to collect machine data. A script in this environment registers the machine in MAAS. As of v3.2, Redfish and IPMI are both supported for these BMC connections. MAAS can now automatically detect and configure either, given that a Redfish Host Interface is enabled and exposed.

## Verifying Redfish activation

You can check if a machine communicates via Redfish with the command:

```nohighlight
dmidecode -t 42
```

Additionally, you can review the `30-maas-01-bmc-config` commissioning script's output if the machine is already enlisted in MAAS.

## Cipher suites (3.1--)

In these versions, MAAS aims to automatically identify the most secure cipher suite. The preference hierarchy is 17, 3, 8, 12. Should auto-detection fail, MAAS reverts to freeipmi-tool's default setting, suite 3.

## Power management

In addition to detailed instructions, this article provides a [complete catalogue of power parameters, by type](#heading--power-catalogue).

You may also like to try [maaspower](https://gilesknap.github.io/maaspower/main/index.html)**^** which is a community project designed to be used with the MAAS webhook driver. It is a pluggable system that accepts MAAS webhooks and can translate them to other external systems. Note: it is not supported by Canonical.

## Set power type (UI)

To configure a machine's power type, click on the machine from the 'Machines' page of the web UI, then select its 'Configuration' tab. Scroll down until you find the Power configuration. If the power type is undefined, the following will be displayed:

![image](https://assets.ubuntu.com/v1/4fae5977-nodes-power-types__2.4_undefined.png)

Choose a type in the drop-down menu that corresponds to the machine's underlying machine's BMC card.

![image](https://assets.ubuntu.com/v1/b53c6613-nodes-power-types__2.4_selection.png)

Fill in the resulting form; the information required will depends on the power type:

| CLI power_type code | Description |
|:--------------------|:------------|
| amt |Intel AMT |
| apc PDU |
| dli | Digital Loggers, Inc. PDU |
| hmc |
| lxd | LXD VM |
| ipmi | IPMI |
| manual | Manual power configuration |
| moonshot |
| mscm | HP Moonshot - iLO Chassis Manager |
| msftocs | Microsoft OCS - Chassis Manager |
| nova | OpenStack Nova |
| openbmc | OpenBMC Power Driver |
| proxmox | ProxMox Power Driver |
| recs_box | Christmann RECS-Box Power Driver |
| redfish | Redfish |
| sm15k | SeaMicro 15000 |
| ucsm | Cisco UCS Manager |
| virsh | libvirt KVM |
| vmware | VMware |
| webhook | Webhook |
| wedge | Facebook's Wedge |

See the [power catalogue](/t/how-to-set-up-power-drivers/5146) for detailed parameters for each of these power types.

Click 'Save changes' to finish. Once that's done, MAAS performs a power check on the machine. A successful power check is a good indication that MAAS can properly communicate with the machine, that is, it should quickly result in a power status of "Power off". A failed attempt will show:

![image](https://assets.ubuntu.com/v1/3bd5e93b-nodes-power-types__2.4_power-error.png)

If you see this error, double-check your entered values by editing the power type, or  consider another power type altogether.

Another possible cause for this error may be the networking: traffic may be getting filtered between the rack controller and the BMC card.

## Set power type (CLI)
To (re)configure a machine's power type, first find the machine's $SYSTEM_ID with the following recipe:

```nohighlight
maas admin machines read | jq -r '(["HOSTNAME","SIS'S"] | (., map(length*"-"))),
(.[] | [.hostname, .system_id]) | @tsv' | column -t
```

Next, use the MAAS CLIset the machine's power type, like this:

    maas $PROFILE machine update $SYSTEM_ID power_type="$POWER_TYPE"

where $POWER_TYPE can have the following values:

| CLI power_type code | Description |
|:-----|:-----|
| amt |Intel AMT |
| apc PDU |
| dli | Digital Loggers, Inc. PDU |
| eaton | Eaton PDU |
| hmc |
| lxd | LXD VM |
| ipmi | IPMI |
| manual | Manual power configuration |
| moonshot |
| mscm | HP Moonshot - iLO Chassis Manager |
| msftocs | Microsoft OCS - Chassis Manager |
| nova | OpenStack Nova |
| openbmc | OpenBMC Power Driver |
| recs_box | Christmann RECS-Box Power Driver |
| redfish | Redfish |
| sm15k | SeaMicro 15000 |
| ucsm | Cisco UCS Manager |
| virsh | libvirt KVM |
| vmware | VMware |
| wedge | Facebook's Wedge |

See the [power catalogue](/t/how-to-set-up-power-drivers/5146) for detailed parameters for each of these power types.

Once you've successfully processed the command (as indicated by a stream of JSON, headed by "Success!"), MAAS performs a power check on the machine. A successful power check is a good indication that MAAS can properly communicate with the machine, that is, it should quickly result in a power status of "Power off". A failed attempt will return errors that should guide you to fix your `power_parameters`.
