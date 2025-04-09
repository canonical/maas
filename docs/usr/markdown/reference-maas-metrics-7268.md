This page provides a MAAS metrics reference, categorised into two sections: "Cluster metrics" and "Performance metrics."

## Cluster metrics

The following cluster metrics are available for MAAS.

### maas_machines

The number of machines known by MAAS, by status

* Type: Gauge
* Unit: Count of machines
* [details="Labels"]
   | Label | Description |
   | --- | --- |
   | maas_id | MAAS cluster UUID |
   | status | machine status |
   [/details]

### maas_nodes

Number of nodes known by MAAS per type (machine, device or controller)

* Type: Gauge
* Unit: Count of machines
* [details="Labels"]

   | Label | Description |
   | --- | --- |
   | maas_id | MAAS cluster UUID |
   | type | type of node (machine/device/controller) |
   [/details]

### maas_net_spaces

Number of network spaces

* Type: Gauge
* Unit: Count of spaces
* [details="Labels"]

   | Label | Description |
   | --- | --- |
   | maas_id | MAAS cluster UUID |
   [/details]

### maas_net_fabrics

Number of network fabrics

* Type: Gauge
* Unit: Count of fabrics
* [details="Labels"]

   | Label | Description |
   | --- | --- |
   | maas_id | MAAS cluster UUID |
   [/details]

### maas_net_vlans

Number of network VLANs

* Type: Gauge
* Unit: Count of vlans
* [details="Labels"]

   | Label | Description |
   | --- | --- |
   | maas_id | MAAS cluster UUID |
   [/details]

### maas_net_subnets_v4

Number of IPv4 subnets

* Type: Gauge
* Unit: Count ipv4 subnets
* [details="Labels"]

   | Label | Description |
   | --- | --- |
   | maas_id | MAAS cluster UUID |
   [/details]

### maas_net_subnets_v6

Number of IPv6 subnets

* Type: Gauge
* Unit: Count of ipv6 subnets
* [details="Labels"]

   | Label | Description |
   | --- | --- |
   | maas_id | MAAS cluster UUID |
   [/details]

### maas_net_subnet_ip_count

Number of IPs in a subnet by status

* Type: Gauge
* Unit: Count of ips
* [details="Labels"]

   | Label | Description |
   | --- | --- |
   | maas_id | MAAS cluster UUID |
   | status | available or used |
   [/details]

### maas_net_subnet_ip_dynamic

Number of used dynamic IPs in a subnet

* Type: Gauge
* Unit: Count of used dynamic ips
* [details="Labels"]

   | Label | Description |
   | --- | --- |
   | maas_id | MAAS cluster UUID |
   | status | available or used |
   | cidr | subnet address |
   [/details]

### maas_net_subnet_ip_reserved

Number of used reserved IPs in a subnet

* Type: Gauge
* Unit: Count of used reserved ips
* [details="Labels"]

   | Label | Description |
   | --- | --- |
   | maas_id | MAAS cluster UUID |
   | status | available or used |
   | cidr | subnet address |
   [/details]

### maas_net_subnet_ip_static

Number of used static IPs in a subnet

* Type: Gauge
* Unit: Count of used static ips
* [details="Labels"]

   | Label | Description |
   | --- | --- |
   | maas_id | MAAS cluster UUID |
   | status | available or used |
   | cidr | subnet address |
   [/details]

### maas_machines_total_mem

Amount of combined memory for all machines

* Type: Gauge
* Unit: Megabytes of memory
* [details="Labels"]

   | Label | Description |
   | --- | --- |
   | maas_id | MAAS cluster UUID |
   [/details]

### maas_machines_total_cpu

Amount of combined CPU counts for all machines

* Type: Gauge
* Unit: Count of cpus
* [details="Labels"]

   | Label | Description |
   | --- | --- |
   | maas_id | MAAS cluster UUID |
   [/details]

### maas_machines_total_storage

Amount of combined storage space for all machines

* Type: Gauge
* Unit: Bytes of storage
* [details="Labels"]

   | Label | Description |
   | --- | --- |
   | maas_id | MAAS cluster UUID |
   [/details]

### maas_kvm_pods

Number of KVM hosts

* Type: Gauge
* Unit: Count of kvm hosts
* [details="Labels"]

   | Label | Description |
   | --- | --- |
   | maas_id | MAAS cluster UUID |
   [/details]

### maas_kvm_machines

Number of virtual machines allocated in KVM hosts

* Type: Gauge
* Unit: Count of virtual machines
* [details="Labels"]

   | Label | Description |
   | --- | --- |
   | maas_id | MAAS cluster UUID |
   [/details]

### maas_kvm_cores

Total number of CPU cores present on KVM hosts

* Type: Gauge
* Unit: Count of kvm cores
* [details="Labels"]

   | Label | Description |
   | --- | --- |
   | maas_id | MAAS cluster UUID |
   | status | available or used |
   [/details]

### maas_kvm_memory

Total amount of RAM present on KVM hosts

* Type: Gauge
* Unit: Megabytes of memory
* [details="Labels"]

   | Label | Description |
   | --- | --- |
   | maas_id | MAAS cluster UUID |
   | status | available or used |
   [/details]

### maas_kvm_storage

Total amount of storage space present on KVM hosts

* Type: Gauge
* Unit: Bytes of storage
* [details="Labels"]

   | Label | Description |
   | --- | --- |
   | maas_id | MAAS cluster UUID |
   | status | available or used |
   [/details]

### maas_kvm_overcommit_cores

Total number of CPU cores present on KVM hosts adjusted by the overcommit setting

* Type: Gauge
* Unit: Overcommitted number of cores
* [details="Labels"]

   | Label | Description |
   | --- | --- |
   | maas_id | MAAS cluster UUID |
   [/details]

### maas_kvm_overcommit_memory

Total amount of RAM present on KVM hosts adjusted by the overcommit setting

* Type: Gauge
* Unit: Overcommitted megabytes of memory
* [details="Labels"]

   | Label | Description |
   | --- | --- |
   | maas_id | MAAS cluster UUID |
   [/details]

### maas_machine_arches

Total number of machines per architecture

* Type: Gauge
* Unit: Count of machines
* [details="Labels"]

   | Label | Description |
   | --- | --- |
   | maas_id | MAAS cluster UUID |
   | arch | machine architecture |
   [/details]

### maas_custom_static_images_uploaded

Number of custom OS images present in MAAS

* Type: Gauge
* Unit: Count of images
* [details="Labels"]

   | Label | Description |
   | --- | --- |
   | maas_id | MAAS cluster UUID |
   | base_image | custom image base OS |
   | file_type | image file type |
   [/details]

### maas_custom_static_images_deployed

Number deployed machines running custom OS images

* Type: Gauge
* Unit: Count of images
* [details="Labels"]

   | Label | Description |
   | --- | --- |
   | maas_id | MAAS cluster UUID |
   [/details]

### maas_vmcluster_projects

Number of KVM clusters

* Type: Gauge
* Unit: Count of projects
* [details="Labels"]

   | Label | Description |
   | --- | --- |
   | maas_id | MAAS cluster UUID |
   [/details]

### maas_vmcluster_hosts

Total number of KVM hosts in clusters

* Type: Gauge
* Unit: Count of vm hosts
* [details="Labels"]

   | Label | Description |
   | --- | --- |
   | maas_id | MAAS cluster UUID |
   [/details]

### maas_vmcluster_vms

Total number of virtual machines in KVM clusters

* Type: Gauge
* Unit: Count of virtual machines
* [details="Labels"]

   | Label | Description |
   | --- | --- |
   | maas_id | MAAS cluster UUID |
   [/details]

## Performance metrics

The following performance metrics are available for MAAS.

### maas_http_request_latency

The time MAAS takes to process a REST API call. It doesn't include any time associated with network, including proxy processing

* Type: Histogram
* Unit: Seconds
* [details="Labels"]

   | Label | Description |
   | --- | --- |
   | host | controller IP address |
   | maas_id | MAAS cluster UUID |
   | method | HTTP method |
   | op | REST API operation name |
   | path | REST API endpoint |
   | status | HTTP response status code |
   [/details]

### maas_http_response_size

The size of REST API responses

* Type: Histogram
* Unit: Bytes
* [details="Labels"]

   | Label | Description |
   | --- | --- |
   | host | controller IP address |
   | maas_id | MAAS cluster UUID |
   | method | HTTP method |
   | op | REST API operation name |
   | path | REST API endpoint |
   | status | HTTP response status code |
   [/details]

### maas_http_request_query_count

The number of database operations executed per REST API call

* Type: Histogram
* Unit: None
* [details="Labels"]

   | Label | Description |
   | --- | --- |
   | host | controller IP address |
   | maas_id | MAAS cluster UUID |
   | method | HTTP method |
   | op | REST API operation name |
   | path | REST API endpoint |
   | status | HTTP response status code |
   [/details]

### maas_http_request_query_latency

The time required to perform a single database operation during a REST API call. The database latency is measured from the moment MAAS starts a transaction until it gets the response

* Type: Histogram
* Unit: Seconds
* [details="Labels"]

   | Label | Description |
   | --- | --- |
   | host | controller IP address |
   | maas_id | MAAS cluster UUID |
   | method | HTTP method |
   | op | REST API operation name |
   | path | REST API endpoint |
   | status | HTTP response status code |
   [/details]

### maas_rack_region_rpc_call_latency

The time a Region controller takes to perform a RPC call to a Rack controller. The latency is measured from the request to the response.

* Type: Histogram
* Unit: Seconds
* [details="Labels"]

   | Label | Description |
   | --- | --- |
   | call | RPC operation |
   | host | controller IP address |
   | maas_id | MAAS cluster UUID |
   [/details]

### maas_region_rack_rpc_call_latency

The time a Rack controller takes to perform a RPC call to a Region controller. The latency is measured from the request to the response.

* Type: Histogram
* Unit: Seconds
* [details="Labels"]

   | Label | Description |
   | --- | --- |
   | call | RPC operation |
   | host | controller IP address |
   | maas_id | MAAS cluster UUID |
   [/details]

### maas_websocket_call_query_count

The number of database operations executed per WebSocket call

* Type: Histogram
* Unit: None
* [details="Labels"]

   | Label | Description |
   | --- | --- |
   | call | WS operation |
   | host | controller IP address |
   | maas_id | MAAS cluster UUID |
   [/details]

### maas_websocket_call_query_latency

The time required to perform a single database operation during a WebSocket call. The database latency is measured from the moment MAAS starts a transaction until it gets the response

* Type: Histogram
* Unit: Seconds
* [details="Labels"]

   | Label | Description |
   | --- | --- |
   | call | WS operation |
   | host | controller IP address |
   | maas_id | MAAS cluster UUID |
   [/details]

### maas_websocket_call_latency

The time MAAS takes to process a WebSocket call. It doesn't include any time associated with network, including proxy processing

* Type: Histogram
* Unit: Seconds
* [details="Labels"]

   | Label | Description |
   | --- | --- |
   | call | WS operation |
   | host | controller IP address |
   | maas_id | MAAS cluster UUID |
   [/details]

### maas_dns_update_latency

The time MAAS takes to setup all zones in the DNS service per update type, which can be 'reload' (cold-start) or 'dynamic' (RNDC operation)

* Type: Histogram
* Unit: Seconds
* [details="Labels"]

   | Label | Description |
   | --- | --- |
   | host | controller IP address |
   | maas_id | MAAS cluster UUID |
   | update_type | reload or dynamic |
   [/details]

### maas_dns_full_zonefile_write_count

Count of full DNS zone rewrite operations

* Type: Counter
* Unit: None
* [details="Labels"]

   | Label | Description |
   | --- | --- |
   | host | controller IP address |
   | maas_id | MAAS cluster UUID |
   | zone | DNS zone name |
   [/details]

### maas_dns_dynamic_update_count

Count of dynamic DNS zone update operations

* Type: Counter
* Unit: None
* [details="Labels"]

   | Label | Description |
   | --- | --- |
   | host | controller IP address |
   | maas_id | MAAS cluster UUID |
   | zone | DNS zone name |
   [/details]

### maas_rpc_pool_exhaustion_count

number of occurrences of the RPC connection pool allocate its maximum number of connections

* Type: Counter
* Unit: None
* [details="Labels"]

   | Label | Description |
   | --- | --- |
   | host | controller IP address |
   | maas_id | MAAS cluster UUID |
   [/details]

### maas_lxd_fetch_machine_failure

Total number of failures for fetching LXD machines

* Type: Counter
* Unit: None
* [details="Labels"]

   | Label | Description |
   | --- | --- |
   | host | controller IP address |
   | maas_id | MAAS cluster UUID |
   [/details]

### maas_lxd_disk_creation_failure

Total number of failures of LXD disk creation

* Type: Counter
* Unit: None
* [details="Labels"]

   | Label | Description |
   | --- | --- |
   | host | controller IP address |
   | maas_id | MAAS cluster UUID |
   [/details]

### maas_virsh_storage_pool_creation_failure

Total number of failures of virsh storage pool creation

* Type: Counter
* Unit: None
* [details="Labels"]

   | Label | Description |
   | --- | --- |
   | host | controller IP address |
   | maas_id | MAAS cluster UUID |
   [/details]

### maas_virsh_fetch_mac_failure

Total number of failures of virsh interfaces enumeration

* Type: Counter
* Unit: None
* [details="Labels"]

   | Label | Description |
   | --- | --- |
   | host | controller IP address |
   | maas_id | MAAS cluster UUID |
   [/details]

### maas_virsh_fetch_description_failure

Total number of failures of virsh domain description

* Type: Counter
* Unit: None
* [details="Labels"]

   | Label | Description |
   | --- | --- |
   | host | controller IP address |
   | maas_id | MAAS cluster UUID |
   [/details]

### maas_tftp_file_transfer_latency

Time required to transfer a file to a machine using TFTP

* Type: Histogram
* Unit: Seconds
* [details="Labels"]

   | Label | Description |
   | --- | --- |
   | host | controller IP address |
   | maas_id | MAAS cluster UUID |
   | filename | file requested |
   [/details]
