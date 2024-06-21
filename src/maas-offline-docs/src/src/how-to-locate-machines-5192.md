> *Errors or typos? Topics missing? Hard to read? <a href="https://docs.google.com/forms/d/e/1FAIpQLScIt3ffetkaKW3gDv6FDk7CfUTNYP_HGmqQotSTtj2htKkVBw/viewform?usp=pp_url&entry.1739714854=https://maas.io/docs/locating-and-searching-for-machines" target = "_blank">Let us know.</a>*

This page explains how to use the search bar filter your view of machines and devices.

## Search parameters

Here's how a typical MAAS search parameter looks:

![MAAS Search Parameter](https://discourse-maas-io-uploads.s3.us-east-1.amazonaws.com/original/2X/d/dcf5037cdd886eb85a2d305fd3df111b38865cea.png)

Search attributes go into the Search box, separated by spaces for 'AND' logic, or enclosed in parentheses and divided by commas for 'OR' logic. They generally follow the format `parameter-name:`. You can fine-tune matches using '=' for exact and '!' for negations. The UI filter drop-downs also help you understand how these work.

## Simple searches

To perform a simple search, go to *Machines* and type your search term in the *Search* box. MAAS updates results as you type, and you can search across many parameters.

## Filtered searches

If you prefer a filtered search, go to *Machines* > *Filters*, pick a parameter group, and select your desired values. MAAS updates the results immediately.

## Creating manual filters

You can enter manual filters in the search bar:

```no-highlight
filter-name:([=]val1,...,[=]val2)
```

>**Note:** Enclose terms in parentheses for group searches, like `status:(failed testing)`.

## Exact and partial matching

For exact matches, prefix the search value with '='. For partial matches, omit it. For example:

```no-highlight
Exact: pod:=able-cattle
Partial: pod:able,cattle
```

## Using multiple search terms

MAAS uses 'AND' logic by default for multiple terms. For instance, `pod:able,cattle cpu:=5` will show machines in pods named `able` or `cattle` with 5 CPU cores.

## Filter reference

Here's a comprehensive table of filter properties you can use. 'Dyn' means dynamic, 'Grp' for groupable, and 'Man' for manually entered.

| Parameter (bold) w/example           | Shows nodes...                  | Dyn | Grp | Man |
|--------------------------------------|----------------------------------|-----|-----|-----|
| **arch**:(=architecture)             | with "architecture"              |     | Grp |     |
| arch:(!=architecture)                | NOT with "architecture"          | Dyn |     |     |
| **zone**:(=zone-name)                | in "zone-name"                   | Dyn | Grp |     |
| zone:(!=zone-name)                   | NOT in "zone-name"               | Dyn |     |     |
| **pool**:(=resource-pool)            | in "resource-pool"               | Dyn | Grp |     |
| pool:(!=resource-pool)               | NOT in "resource-pool"           | Dyn |     |     |
| **pod**:(=pod-name)                  | with "pod-name"                  | Dyn | Grp |     |
| pod:(!=pod-name)                     | NOT with "pod-name"              | Dyn |     |     |
| **pod_type**:(=pod-type)             | with power type "pod-type"       | Dyn | Grp | Man |
| pod_type:(!=pod-type)                | NOT with power type "pod-type"   | Dyn |     | Man |
| **domain**:(=domain-name)            | with "domain-name"               | Dyn | Grp | Man |
| domain:(!=domain-name)               | NOT with "domain-name"           | Dyn |     | Man |
| **status**:(=op-status)              | having "op-status"               |     | Grp |     |
| status:(!=op-status)                 | NOT having "op-status"           | Dyn |     |     |
| **owner**:(=user)                    | owned by "user"                  | Dyn | Grp |     |
| owner:(!=user)                       | NOT owned by "user"              | Dyn |     |     |
| **power_state**:(=power-state)       | having "power-state"             |     | Grp | Man |
| power_state:(!=power-state)          | NOT having "power-state"         | Dyn |     | Man |
| **tags**:(=tag-name)                 | with tag "tag-name"              | Dyn |     |     |
| tags:(!=tag-name)                    | NOT with tag "tag-name"          | Dyn |     |     |
| **fabrics**:(=fabric-name)           | in "fabric-name"                 | Dyn |     |     |
| fabrics:(!=fabric-name)              | NOT in "fabric-name"             | Dyn |     |     |
| **fabric_classes**:(=fabric-class)   | in "fabric-class"                | Dyn |     | Man |
| fabric_classes:(!=fabric-class)      | NOT in "fabric-class"            | Dyn |     | Man |
| **fabric_name**:(=fabric-name)       | in "boot-interface-fabric"       | Dyn |     | Man |
| fabric_name:(!=fabric-name)          | NOT in "boot-interface-fabric"   | Dyn |     | Man |
| **subnets**:(=subnet-name)           | attached to "subnet-name"        | Dyn |     |     |
| subnets:(!=subnet-name)              | Not attached to "subnet-name"    | Dyn |     |     |
| **link_speed**:(link-speed)          | having "link-speed"              | Dyn |     | Man |
| link_speed:(!link-speed)             | NOT having "link-speed"          | Dyn |     | Man |
| **vlans**:(=vlan-name)               | attached to "vlan-name"          | Dyn |     |     |
| vlans:(!=vlan-name)                  | NOT attached to "vlan-name"      | Dyn |     |     |
| **storage**:(storage-MB)             | having "storage-MB"              | Dyn |     | Man |
| **total_storage**:(total-stg-MB)     | having "total-stg-MB"            | Dyn |     | Man |
| total_storage:(!total-stg-MB)        | NOT having "total-stg-MB"        | Dyn |     | Man |
| **cpu_count**:(cpu-count)            | having "cpu-count"               | Dyn |     | Man |
| cpu_count:(!cpu-count)               | NOT having "cpu-count"           | Dyn |     | Man |
| **mem**:(ram-in-MB)                  | having "ram-in-MB"               | Dyn |     | Man |
| mem:(!ram-in-MB)                     | NOT having "ram-in-MB"           | Dyn |     | Man |
| **mac_address**:(=MAC)               | having MAC address "MAC"         | Dyn |     | Man |
| mac_address:(!=MAC)                  | NOT having                       | Dyn |     | Man |
| **agent_name**:(=agent-name)         | Include nodes with agent-name    | Dyn |     | Man |
| agent_name:(!=agent-name)            | Exclude nodes with agent-name    | Dyn |     | Man |
| **cpu_speed**:(cpu-speed-GHz)        | CPU speed                        | Dyn |     | Man |
| cpu_speed:(!cpu-speed-GHz)           | CPU speed                        | Dyn |     | Man |
| **osystem**:(=os-name)               | The OS of the desired node       | Dyn |     | Man |
| osystem:(!=os-name)                  | OS to ignore                     | Dyn |     | Man |
| **distro_series**:(=distro-name)     | Include nodes using distro       | Dyn |     | Man |
| distro_series:(!=distro-name)        | Exclude nodes using distro       | Dyn |     | Man |
| **ip_addresses**:(=ip-address)       | Node's IP address                | Dyn |     | Man |
| ip_addresses:(!=ip-address)          | IP address to ignore             | Dyn |     | Man |
| **spaces**:(=space-name)             | Node's spaces                    | Dyn |     |     |
| spaces:(!=space-name)                | Node's spaces                    | Dyn |     |     |
| **workloads**:(=annotation-text)     | Node's workload annotations      | Dyn |     |     |
| workloads:(!=annotation-text)        | Node's workload annotations      | Dyn |     |     |
| **physical_disk_count**:(disk-count) | Physical disk Count              | Dyn |     | Man |
| physical_disk_count:(!disk-count)    | Physical disk Count              | Dyn |     | Man |
| **pxe_mac**:(=PXE-MAC)               | Boot interface MAC address       | Dyn |     | Man |
| pxe_mac:(!=PXE-MAC)                  | Boot interface MAC address       | Dyn |     | Man |
| **fqdn**:(=fqdn-value)               | Node FQDN                        | Dyn |     | Man |
| fqdn:(!=fqdn-value)                  | Node FQDN                        | Dyn |     | Man |
| **simple_status**:(=status-val)      | Include nodes with simple-status | Dyn |     | Man |
| simple_status:(!=status-val)         | Exclude nodes with simple-status | Dyn |     | Man |
| **devices**:(=)                      | Devices                          | Dyn |     | Man |
| **interfaces**:(=)                   | Interfaces                       | Dyn |     | Man |
| **parent**:(=)                       | Parent node                      | Dyn | Grp | Man |