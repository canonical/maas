# Release notes

## Releases

- [Version 3.7](#version-37-release-notes)
- [Version 3.6](#version-36-release-notes)

### Older releases

- [MAAS 3.5 release notes](/older-releases/maas-3-5-release-notes.md)
- [MAAS 3.4 release notes](/older-releases/maas-3-4-release-notes.md)
- [MAAS 3.3 release notes](/older-releases/maas-3-3-release-notes.md)
- [MAAS 3.2 release notes](/older-releases/maas-3-2-release-notes.md)
- [MAAS 3.1 release notes](/older-releases/maas-3-1-release-notes.md)
- [MAAS 3.0 release notes](/older-releases/maas-3-0-release-notes.md)
- [MAAS 2.9 release notes](/older-releases/maas-2-9-release-notes.md)
- [MAAS 2.8 release notes](/older-releases/maas-2-8-release-notes.md)
- [MAAS 2.7 release notes](/older-releases/maas-2-7-release-notes.md)

<!--
## Release policy and schedule

Our release cadence is roughly two versions per calendar year, depending upon when we reach feature-complete.

## Version support

We support two releases of MAAS plus one Beta release (when available).  The two previous releases are supported by Canonical Systems Engineering Group.  At any given time, support is available for four releases plus one Beta release (when available).
-->

## Version 3.7 release notes

### MAAS 3.7.3 has been released

We are happy to announce that MAAS 3.7.3 has been released, with the following bug fixes:

- [2141600](https://launchpad.net/maas/+bug/2141600): Redfish power driver may set node_id to manager_id rather than system_id
- [2137492](https://launchpad.net/maas/+bug/2137492): Problematic MAC address normalization
- [2138223](https://launchpad.net/maas/+bug/2138223): MAAS allows subnet deletion even when it has IPs in use by nodes
- [2074122](https://launchpad.net/maas/+bug/2074122): MAAS rack is scaling up the number of connections without limit due to a race condition
- [2146799](https://launchpad.net/maas/+bug/2146799): maas-agent: HTTP response body leak in queueFlush causes unbounded goroutine growth
- [2146882](https://launchpad.net/maas/+bug/2146882): Redfish URLs might redirect and this is breaking MAAS power commands
- [2147037](https://launchpad.net/maas/+bug/2147037): Deploy workflow power-on activity times out after 1hr but the machine status remains in Deploying for infinite amount
- [2147445](https://launchpad.net/maas/+bug/2147445): hmcz deployment fails since maas.power is missing set-boot-order
- [2148224](https://launchpad.net/maas/+bug/2148224): Can't configure DHCP on MAAS 3.7 if TLS is enabled
- [2148485](https://launchpad.net/maas/+bug/2148485): User unable to see their information in the UI
- [2147570](https://launchpad.net/maas/+bug/2147570): Errors creating non-authoritative domain with DNS forwarding
- [2148598](https://launchpad.net/maas/+bug/2148598): Deployment of custom image for DPU by Juju fails because hwe_kernel used is lower than min required
- [2148683](https://launchpad.net/maas/+bug/2148683): MAAS fails to perform machine operations that involve cancelling the Temporal deploy workflow
- [2093303](https://launchpad.net/maas/+bug/2093303): Repositories are configured multiple times
- [2150892](https://launchpad.net/maas/+bug/2150892): Power Address no longer accepts DNS names
- [2153152](https://launchpad.net/maas/+bug/2153152): The temporal deploy workflow is trying to make power calls to BMC with power type manual
- [2152681](https://launchpad.net/maas/+bug/2152681): MAAS discovery of IP address prevents its assignment to the same machine
- [2155055](https://launchpad.net/maas/+bug/2155055): current_installation_result_id is cleared (null)
- [2156012](https://launchpad.net/maas/+bug/2156012): Transaction retry after dropped connection executes without re-acquiring advisory lock, causing race conditions in critical section.
- [2109694](https://launchpad.net/maas/+bug/2109694): MAAS 3.6 snap still uses default Ubuntu archive repositories despite configuring custom repositories
- [2161952](https://launchpad.net/maas/+bug/2161952): Several MAAS code paths perform N+1 node queries on large deployments
- [2147514](https://launchpad.net/maas/+bug/2147514): Power state not refreshed when a node transitions from COMMISSIONING to NEW (enlistment commissioning)
- [2156073](https://launchpad.net/maas/+bug/2156073): DHCP configuration files created with incorrect permissions (-r----xrw-) due to octal/decimal formatting bug in Go agent

### MAAS 3.7.2 has been released

We are happy to announce that MAAS 3.7.2 has been released, with the following bug fixes:

- [2136694](https://launchpad.net/maas/+bug/2136694): Ephemeral deployments lack control over the amount of RAM allocated for the rootfs
- [2138910](https://launchpad.net/maas/+bug/2138910): Alias interfaces duplicate the gateway4/6 config in netplan
- [2141388](https://launchpad.net/maas/+bug/2141388): Introductory warning for non available images contains an absolute URL with internal IP when MAAS is accessed via a Load Balancer
- [2141598](https://launchpad.net/maas/+bug/2141598): Custom images stuck in "Loading Queued for download" after upgrade to 3.5
- [2142793](https://launchpad.net/maas/+bug/2142793): maasagent memory leak on DHCP expiry failure due to constraint violation
- [2142861](https://launchpad.net/maas/+bug/2142861): Rapid requests to MAAS get_config API reaches database race condition
- [2143730](https://launchpad.net/maas/+bug/2143730): Lease processing returns 404 and causes the agent to memory leak
- [2143919](https://launchpad.net/maas/+bug/2143919): 30-maas-01-bmc-config configures wrong power_address on Lenovo XCC BMC

### MAAS 3.7.1 has been released

We are happy to announce that MAAS 3.7.1 has been released, with the following bug fixes:

- [2132663](https://launchpad.net/maas/+bug/2132663): Custom images fail to deploy in memory
- [2134059](https://launchpad.net/maas/+bug/2134059): In-memory deployments cause incorrect netplan
- [2134484](https://launchpad.net/maas/+bug/2134484): DHCP fails to start due to dhcpd.conf not formatted correctly for multi-homed clients
- [2134485](https://launchpad.net/maas/+bug/2134485): MAAS 3.7.0: DHCP Fails on Split Region/Rack with VLANs (Initial Crash, Duplicate Host, and Event Trigger Failure)
- [2127672](https://launchpad.net/maas/+bug/2127672): \_gen_reverse_zones takes a lot of time in environments with lots of subnets
- [2110046](https://launchpad.net/maas/+bug/2110046): MAAS allows AXFR from all sources
- [2129772](https://launchpad.net/maas/+bug/2129772): TFTP server reports intermittent "Error code 1: File not found"
- [2130621](https://launchpad.net/maas/+bug/2130621): DGX H200 commissioning failed randomly due to a password policy mismatch
- [2132282](https://launchpad.net/maas/+bug/2132282): 20-maas-03-machine-resources fails for uint64 counters
- [2137254](https://launchpad.net/maas/+bug/2137254): "Add Hardware" fails with 500 error when Candid is enabled and RBAC is disabled (UI calls service-layer endpoint that does not exist)
- [2137017](https://launchpad.net/maas/+bug/2137017): maas-run-scripts failing with 'NoneType' object is not iterable
- [2137724](https://launchpad.net/maas/+bug/2137724): Temporal worker pool configuration failure on NULL IP
- [2135830](https://launchpad.net/maas/+bug/2135830): Virsh VM cannot use storage type ZFS
- [2138301](https://launchpad.net/maas/+bug/2138301): The images page of a MAAS with many boot resources is slow
- [2138312](https://launchpad.net/maas/+bug/2138312): ARM64 custom image deploy fails if AMD64 custom image exists with the same name
- [2138738](https://launchpad.net/maas/+bug/2138738): MAAS 3.7.0 does not allow to change the hostname
- [2080646](https://launchpad.net/maas/+bug/2080646): MAAS_PATH env variable missing from snap env, causes maas not to be able to connect to virsh
- [2107706](https://launchpad.net/maas/+bug/2107706): Power error for intel AMT when using HTTPS: Unsupported protocol
- [2135117](https://launchpad.net/maas/+bug/2135117): MAAS is trying to remove lost+found for filesystem mounted on /var/lib/maas/image-storage

### 3.7.0

#### BlueField-3 DPU provisioning

Support for NVIDIA BlueField-3 DPUs, enabling MAAS users to manage and configure them just like any other machine. Thanks to the addition of a BMC to this generation of DPUs, MAAS can interact with BlueField-3 DPUs for commissioning, deployment, and release operations. While BlueField-3 introduces new complexity compared to previous generations, MAAS handles these differences behind the scenes, making it easier for data center operators to integrate DPUs into their workflows.

#### Speedup MAAS CLI

Refactored MAAS CLI initialization to defer loading Django and other heavy dependencies during CLI parser setup. This change significantly improves startup performance and responsiveness for most commands, yielding a 55% reduction in CLI startup time. Previously, every command took over 2 seconds to initialize the CLI; with this refactor, commands now complete in under 1 second.

Note: These improvements only affect CLI startup time, not the execution time of commands that involve server communication or data retrieval.

#### DNS Recursive Resolver

In rack-only mode, we no longer run a BIND instance to forward queries to the region. We instead run our own resolver that will recursively resolve out to the internet or region. It relies on the rack host’s resolv.conf to determine where to send external queries. It caches all valid responses for the lifetime of their TTLs.

#### Deprecation notices

- OpenStack Compute (nova) power driver was removed

#### Bug fixes

- [LP#1995070](https://bugs.launchpad.net/bugs/1995070) - MAAS TLS offers CBC ciphers
- [LP#2063458](https://bugs.launchpad.net/bugs/2063458) - "Node has no address family in common with server" when deploying a LXD VM on an IPv6-only bridge
- [LP#2085160](https://bugs.launchpad.net/bugs/2085160) - Temporal workflow deadlock
- [LP#2091271](https://bugs.launchpad.net/bugs/2091271) - HW sync is not able to detect a bridge interface configured with OVS
- [LP#2092188](https://bugs.launchpad.net/bugs/2092188) - Redfish detection causes bmc_config script to fail despite it seems to succeed
- [LP#2095085](https://bugs.launchpad.net/bugs/2095085) - maas-agent fails to start: Workflow execution already started
- [LP#2095476](https://bugs.launchpad.net/bugs/2095476) - Store last deploy time of images more directly in the database
- [LP#2095477](https://bugs.launchpad.net/bugs/2095477) - boot-resources read is slow when there are a lot of images that have been deployed a lot of times
- [LP#2097079](https://bugs.launchpad.net/bugs/2097079) - Failed to initialize MAAS on PostgreSQL with pgaudit plugin enabled
- [LP#2097242](https://bugs.launchpad.net/bugs/2097242) - MAAS is not auditing changes in OS images
- [LP#2098446](https://bugs.launchpad.net/bugs/2098446) - Maas prometheus wrong Content-Type
- [LP#2098472](https://bugs.launchpad.net/bugs/2098472) - Wrong message when trying to delete the commissioning OS image
- [LP#2099949](https://bugs.launchpad.net/bugs/2099949) - Redfish power driver requests fails with 412 status code
- [LP#2100477](https://bugs.launchpad.net/bugs/2100477) - Lease update is broken
- [LP#2100790](https://bugs.launchpad.net/bugs/2100790) - MAAS KVM Host option disabled for 24.04 noble
- [LP#2102126](https://bugs.launchpad.net/bugs/2102126) - MAAS 3.6 can't power control AMT BMCs after upgrade from 3.5
- [LP#2103654](https://bugs.launchpad.net/bugs/2103654) - Lease expiry removes all IP addresses of a machine
- [LP#2103733](https://bugs.launchpad.net/bugs/2103733) - Machine in Deploying status after `deploy` workflow timed out
- [LP#2103903](https://bugs.launchpad.net/bugs/2103903) - Deployment fails when using interface with OVS bridge
- [LP#2104260](https://bugs.launchpad.net/bugs/2104260) - Cloud-init 24.04.1 requires OVS bridge interface not to be optional in the netplan preseed network
- [LP#2104278](https://bugs.launchpad.net/bugs/2104278) - MAAS KVM deploy with 24.04 fails sshd.service not found
- [LP#2104530](https://bugs.launchpad.net/bugs/2104530) - plucky deployments fail after reboot to disk due to no network
- [LP#2104838](https://bugs.launchpad.net/bugs/2104838) - MAAS snap incorrectly calculates cache_size
- [LP#2104907](https://bugs.launchpad.net/bugs/2104907) - Enabling 'Verify SSL connections with system CA certificates' for Proxmox power type fails
- [LP#2105901](https://bugs.launchpad.net/bugs/2105901) - MAAS UI cannot compose a VM using LXD as KVM host
- [LP#2106211](https://bugs.launchpad.net/bugs/2106211) - configure-dns keeps failing
- [LP#2106398](https://bugs.launchpad.net/bugs/2106398) - Multiple results were returned by get_one
- [LP#2106542](https://bugs.launchpad.net/bugs/2106542) - When MAAS receives a DHCP lease it should remove all the old discovered IPs linked to the interface
- [LP#2106671](https://bugs.launchpad.net/bugs/2106671) - Deployments using a bonded interface on the "MAAS" management network are broken
- [LP#2107537](https://bugs.launchpad.net/bugs/2107537) - sshkeys import command not working
- [LP#2107967](https://bugs.launchpad.net/bugs/2107967) - MAAS 3.6.0 - Splitted upgrade doesn't work with snap
- [LP#2109360](https://bugs.launchpad.net/bugs/2109360) - MAAS incorrectly calculates cache_size for SNAP
- [LP#2109681](https://bugs.launchpad.net/bugs/2109681) - Proxmox power driver is broken
- [LP#2109864](https://bugs.launchpad.net/bugs/2109864) - No rack controller can access BMC of node [MAAS 3.5.5]
- [LP#2110021](https://bugs.launchpad.net/bugs/2110021) - Reserving IPs in MAAS 3.6 causes duplicate host entries in dhcpd.conf after deploying machines
- [LP#2110023](https://bugs.launchpad.net/bugs/2110023) - [3.6] external DHCP on rack controller appears to break data model
- [LP#2112206](https://bugs.launchpad.net/bugs/2112206) - Powerloop on HPE ProLiant DL385 and DL360
- [LP#2112460](https://bugs.launchpad.net/bugs/2112460) - DHCP Commissioning script fails on nodes with multiple unused interfaces
- [LP#2112637](https://bugs.launchpad.net/bugs/2112637) - MAAS does not set BOOTIF mac address for IBM s390x LPARs during PXE boot
- [LP#2113894](https://bugs.launchpad.net/bugs/2113894) - AMT power driver (amttool) is broken - builtins.TypeError: AMTPowerDriver.\_issue_amttool_command() takes from 4 to 5 positional arguments but 6 were given. amttool perl not found
- [LP#2115176](https://bugs.launchpad.net/bugs/2115176) - Power management picks offline Rack Controller for VLAN
- [LP#1964644](https://bugs.launchpad.net/bugs/1964644) - Adding overlapping subnets in fabric breaks deployments and squid
- [LP#2034940](https://bugs.launchpad.net/bugs/2034940) - /api/docs/ does not show correct documentation
- [LP#2084719](https://bugs.launchpad.net/bugs/2084719) - MAAS Snaps Cannot Manage OpenStack Nova Power
- [LP#2097505](https://bugs.launchpad.net/bugs/2097505) - dhcpd.conf write race condition
- [LP#2098129](https://bugs.launchpad.net/bugs/2098129) - chown config files - operation not permitted
- [LP#2098967](https://bugs.launchpad.net/bugs/2098967) - domain read is slow when there are a lot of dns records
- [LP#2111335](https://bugs.launchpad.net/bugs/2111335) - MOK enrollment flow is disrupted on (at least) DUTs which enabled secure boot post-deployment
- [LP#2111831](https://bugs.launchpad.net/bugs/2111831) - MAAS snap uses setuptools from pip - UserWarning: pkg_resources is deprecated as an API.
- [LP#2111932](https://bugs.launchpad.net/bugs/2111932) - MAAS UI and CLI do not show older events in the event log or event query
- [LP#2115797](https://bugs.launchpad.net/bugs/2115797) - LXD VM host not always deploys in 3.6
- [LP#2117200](https://bugs.launchpad.net/bugs/2117200) - Machines added using Redfish power driver get into inconsistent power state
- [LP#2117401](https://bugs.launchpad.net/bugs/2117401) - "zone already frozen" error when updating MAAS
- [LP#2118408](https://bugs.launchpad.net/bugs/2118408) - MAAS TFTP is not compatible in some networking environments that are using tunneling adding extra padding in the datagram
- [LP#2118761](https://bugs.launchpad.net/bugs/2118761) - apiserver is not restarted properly when vault is configured
- [LP#2118833](https://bugs.launchpad.net/bugs/2118833) - Named still forwards DNS request from authoritative zone to upstream nameservers
- [LP#2119630](https://bugs.launchpad.net/bugs/2119630) - Unable to deploy rocky with secure boot
- [LP#2120556](https://bugs.launchpad.net/bugs/2120556) - Deleting a DNS A record deletes all records targeting the same ip address
- [LP#2121474](https://bugs.launchpad.net/bugs/2121474) - Image download on MAAS 3.6.1 is slow
- [LP#2121860](https://bugs.launchpad.net/bugs/2121860) - MAAS DHCP is not deactivated when I turn it off with the UI
- [LP#2095354](https://bugs.launchpad.net/bugs/2095354) - Upgrading a single instance to a minor release may hang and break the deployment temporarily
- [LP#2130269](https://bugs.launchpad.net/bugs/2130269) - Build is failing to download pre-built UI assets

## Version 3.6 release notes

### MAAS 3.6.5 has been released

We are happy to announce that MAAS 3.6.5 has been released, with the following bug fixes:

- [2141600](https://launchpad.net/maas/+bug/2141600): Redfish power driver may set node_id to manager_id rather than system_id
- [2074122](https://launchpad.net/maas/+bug/2074122): MAAS rack is scaling up the number of connections without limit due to a race condition
- [2146882](https://launchpad.net/maas/+bug/2146882): Redfish URLs might redirect and this is breaking MAAS power commands
- [2147037](https://launchpad.net/maas/+bug/2147037): Deploy workflow power-on activity times out after 1hr but the machine status remains in Deploying for infinite amount
- [2147445](https://launchpad.net/maas/+bug/2147445): hmcz deployment fails since maas.power is missing set-boot-order
- [2148683](https://launchpad.net/maas/+bug/2148683): MAAS fails to perform machine operations that involve cancelling the Temporal deploy workflow
- [2147570](https://launchpad.net/maas/+bug/2147570): Errors creating non-authoritative domain with DNS forwarding
- [2093303](https://launchpad.net/maas/+bug/2093303): Repositories are configured multiple times
- [2150892](https://launchpad.net/maas/+bug/2150892): Power Address no longer accepts DNS names
- [2153152](https://launchpad.net/maas/+bug/2153152): The temporal deploy workflow is trying to make power calls to BMC with power type manual
- [2155055](https://launchpad.net/maas/+bug/2155055): current_installation_result_id is cleared (null)
- [2109694](https://launchpad.net/maas/+bug/2109694): MAAS 3.6 snap still uses default Ubuntu archive repositories despite configuring custom repositories
- [2147514](https://launchpad.net/maas/+bug/2147514): Power state not refreshed when a node transitions from COMMISSIONING to NEW (enlistment commissioning)
- [2156073](https://launchpad.net/maas/+bug/2156073): DHCP configuration files created with incorrect permissions (-r----xrw-) due to octal/decimal formatting bug in Go agent

### MAAS 3.6.4 has been released

We are happy to announce that MAAS 3.6.4 has been released, with the following bug fixes:

- [2142793](https://bugs.launchpad.net/maas/+bug/2142793): maasagent memory leak on DHCP expiry failure due to constraint violation
- [2143730](https://bugs.launchpad.net/maas/+bug/2143730): Lease processing returns 404 and causes the agent to memory leak
- [2141598](https://bugs.launchpad.net/maas/+bug/2141598): Custom images stuck in “Loading Queued for download” after upgrade to 3.5
- [2143919](https://bugs.launchpad.net/maas/+bug/2143919): 30-maas-01-bmc-config configures wrong power_address on Lenovo XCC BMC

### MAAS 3.6.3 has been released

We are happy to announce that MAAS 3.6.3 has been released, with the following bug fixes:

- [2080646](https://bugs.launchpad.net/maas/+bug/2080646): MAAS_PATH env variable missing from snap env, causes maas not to be able to connect to virsh
- [2107706](https://bugs.launchpad.net/maas/+bug/2107706): Power error for intel AMT when using HTTPS: Unsupported protocol
- [2110046](https://bugs.launchpad.net/maas/+bug/2110046): MAAS allows AXFR from all sources
- [2122720](https://bugs.launchpad.net/maas/+bug/2122720): Cilium and MAAS routing rule priorities conflict in some cases
- [2129772](https://bugs.launchpad.net/maas/+bug/2129772): TFTP server reports intermittent "Error code 1: File not found"
- [2130037](https://bugs.launchpad.net/maas/+bug/2130037): MAAS boot_images_no_proxy configuration ignored, MAAS cannot download images from mirror in the same network
- [2130237](https://bugs.launchpad.net/maas/+bug/2130237): RPC RegisterRackController can saturate all the database threads, causing region controllers to become unresponsive for minutes
- [2130269](https://bugs.launchpad.net/maas/+bug/2130269): Build is failing to download pre-built UI assets
- [2130621](https://bugs.launchpad.net/maas/+bug/2130621): DGX H200 commissioning failed randomly due to a password policy mismatch
- [2132282](https://bugs.launchpad.net/maas/+bug/2132282): 20-maas-03-machine-resources fails for uint64 counters
- [2132663](https://bugs.launchpad.net/maas/+bug/2132663): Custom images fail to deploy in memory
- [2134059](https://bugs.launchpad.net/maas/+bug/2134059): In-memory deployments cause incorrect netplan
- [2134484](https://bugs.launchpad.net/maas/+bug/2134484): DHCP fails to start due to dhcpd.conf not formatted correctly for multi-homed clients
- [2134485](https://bugs.launchpad.net/maas/+bug/2134485): MAAS 3.7.0: DHCP Fails on Split Region/Rack with VLANs (Initial Crash, Duplicate Host, and Event Trigger Failure)
- [2135117](https://bugs.launchpad.net/maas/+bug/2135117): MAAS is trying to remove lost+found for filesystem mounted on /var/lib/maas/image-storage
- [2135830](https://bugs.launchpad.net/maas/+bug/2135830): Virsh VM cannot use storage type ZFS
- [2136694](https://bugs.launchpad.net/maas/+bug/2136694): Ephemeral deployments lack control over the amount of RAM allocated for the rootfs
- [2137017](https://bugs.launchpad.net/maas/+bug/2137017): maas-run-scripts failing with 'NoneType' object is not iterable
- [2137724](https://bugs.launchpad.net/maas/+bug/2137724): Temporal worker pool configuration failure on NULL IP
- [2138312](https://bugs.launchpad.net/maas/+bug/2138312): ARM64 custom image deploy fails if AMD64 custom image exists with the same name
- [2138910](https://bugs.launchpad.net/maas/+bug/2138910): Alias interfaces duplicate the gateway4/6 config in netplan

### MAAS 3.6.2 has been released

We are happy to announce that MAAS 3.6.2 has been released, with the following bug fixes:

- [2083076](https://launchpad.net/maas/+bug/2083076): MAAS nodes that fail commissioning continue to use stale commissioning scripts
- [2115797](https://launchpad.net/maas/+bug/2115797): LXD VM host not always deploys in 3.6
- [2117200](https://launchpad.net/maas/+bug/2117200): Machines added using Redfish power driver get into inconsistent power state
- [2098967](https://launchpad.net/maas/+bug/2098967): domain read is slow when there are a lot of dns records
- [2120556](https://launchpad.net/maas/+bug/2120556): Deleting a DNS A record deletes all records targeting the same ip address
- [2118833](https://launchpad.net/maas/+bug/2118833): Named still forwards DNS request from authoritative zone to upstream nameservers
- [2125396](https://launchpad.net/maas/+bug/2125396): StaticIPAddress auto IP allocation fails because of unhandled exception
- [2026181](https://launchpad.net/maas/+bug/2026181): MAAS power-on timeout is too low for LXD
- [2114846](https://launchpad.net/maas/+bug/2114846): maas_wipe.py fails to run upon releasing a machine
- [2119630](https://launchpad.net/maas/+bug/2119630): Unable to deploy rocky with secure boot

### MAAS 3.6.1 has been released

We are happy to announce that MAAS 3.6.1 has been released, with the following bug fixes

- [2109681](https://bugs.launchpad.net/maas/+bug/2109681): Proxmox power driver is broken
- [2109864](https://bugs.launchpad.net/maas/+bug/2109864): No rack controller can access BMC of node [MAAS 3.5.5]
- [2040324](https://bugs.launchpad.net/maas/+bug/2040324): Power configuration change fails with <image> is not a valid distro series error
- [2063457](https://bugs.launchpad.net/maas/+bug/2063457): dhcpd6.conf can contain IPv4 nameserver options
- [2091370](https://bugs.launchpad.net/maas/+bug/2091370): MAAS snap build pulls python modules from outside Ubuntu Archive / MAAS PPAs
- [2097242](https://bugs.launchpad.net/maas/+bug/2097242): MAAS is not auditing changes in OS images
- [2103733](https://bugs.launchpad.net/maas/+bug/2103733): Machine in Deploying status after `deploy` workflow timed out
- [2103903](https://bugs.launchpad.net/maas/+bug/2103903): Deployment fails when using interface with OVS bridge
- [2104260](https://bugs.launchpad.net/maas/+bug/2104260): Cloud-init 24.04.1 requires OVS bridge interface not to be optional in the netplan preseed network
- [2104838](https://bugs.launchpad.net/maas/+bug/2104838): MAAS snap incorrectly calculates cache_size
- [2104530](https://bugs.launchpad.net/maas/+bug/2104530): plucky deployments fail after reboot to disk due to no network
- [2107967](https://bugs.launchpad.net/maas/+bug/2107967): MAAS 3.6.0 - Splitted upgrade doesn't work with snap
- [2109360](https://bugs.launchpad.net/maas/+bug/2109360): MAAS incorrectly calculates cache_size for SNAP
- [2063458](https://bugs.launchpad.net/maas/+bug/2063458): "Node has no address family in common with server" when deploying a LXD VM on an IPv6-only bridge
- [2110023](https://bugs.launchpad.net/maas/+bug/2110023): [3.6] external DHCP on rack controller appears to break data model
- [2110021](https://bugs.launchpad.net/maas/+bug/2110021): Reserving IPs in MAAS 3.6 causes duplicate host entries in dhcpd.conf after deploying machines
- [2091271](https://bugs.launchpad.net/maas/+bug/2091271): HW sync is not able to detect a bridge interface configured with OVS
- [2111831](https://bugs.launchpad.net/maas/+bug/2111831): MAAS snap uses setuptools from pip - UserWarning: pkg_resources is deprecated as an API.
- [2112460](https://bugs.launchpad.net/maas/+bug/2112460): DHCP Commissioning script fails on nodes with multiple unused interfaces
- [2115176](https://bugs.launchpad.net/maas/+bug/2115176): Power management picks offline Rack Controller for VLAN
- [2112637](https://bugs.launchpad.net/maas/+bug/2112637): MAAS does not set BOOTIF mac address for IBM s390x LPARs during PXE boot
- [2112206](https://bugs.launchpad.net/maas/+bug/2112206): Powerloop on HPE ProLiant DL385 and DL360
- [2097079](https://bugs.launchpad.net/maas/+bug/2097079): Failed to initialize MAAS on PostgreSQL with pgaudit plugin enabled
- [2118408](https://bugs.launchpad.net/maas/+bug/2118408): MAAS TFTP is not compatible in some networking environments that are using tunneling adding extra padding in the datagram
- [1901905](https://bugs.launchpad.net/maas/+bug/1901905): Updating DNS records yields unexpected results
- [1990871](https://bugs.launchpad.net/maas/+bug/1990871): TestPostgresListenerService - test_handles_missing_system_handler_onnotification
- [2054312](https://bugs.launchpad.net/maas/+bug/2054312): Documentation is broken is so many ways
- [2054836](https://bugs.launchpad.net/maas/+bug/2054836): Redfish in bmc-config commissioning script is hard-coded for a particular Manager and EthernetInterface
- [2057782](https://bugs.launchpad.net/maas/+bug/2057782): Quick erasing disks doesn't clean properly some special filesystem
- [1901905](https://bugs.launchpad.net/maas/+bug/1901905): Updating DNS records yields unexpected results
- [1990871](https://bugs.launchpad.net/maas/+bug/1990871): TestPostgresListenerService - test_handles_missing_system_handler_onnotification
- [2054312](https://bugs.launchpad.net/maas/+bug/2054312): Documentation is broken is so many ways
- [2054836](https://bugs.launchpad.net/maas/+bug/2054836): Redfish in bmc-config commissioning script is hard-coded for a particular Manager and EthernetInterface
- [2092299](https://bugs.launchpad.net/maas/+bug/2092299): MAAS 3.5.2 does not sort machines by DISKS or STORAGE
- [2104907](https://bugs.launchpad.net/maas/+bug/2104907): Enabling 'Verify SSL connections with system CA certificates' for Proxmox power type fails
- [2106398](https://bugs.launchpad.net/maas/+bug/2106398): Multiple results were returned by get_one
- [2107537](https://bugs.launchpad.net/maas/+bug/2107537): sshkeys import command not working
- [2113894](https://bugs.launchpad.net/maas/+bug/2113894): AMT power driver (amttool) is broken - builtins.TypeError: AMTPowerDriver.\_issue_amttool_command() takes from 4 to 5 positional arguments but 6 were given. amttool perl not found
- [2118761](https://bugs.launchpad.net/maas/+bug/2118761): apiserver is not restarted properly when vault is configured
- [2058063](https://bugs.launchpad.net/maas/+bug/2058063): Controllers show different versions when installed with debs
- [2098446](https://bugs.launchpad.net/maas/+bug/2098446): Maas prometheus wrong Content-Type

### MAAS 3.6.0 has been released

#### MAAS 3.6 based on Ubuntu 24.04 LTS

MAAS 3.6 is the first release to run natively on Ubuntu 24.04 LTS. This comes with refreshed dependencies and lots of improvements and bug fixes. It's available in both deb (PPA) and snap formats.

Previous releases will continue to be supported on their current Ubuntu distribution for the duration of their normal lifecycle, but moving forward, upgrading to 24.04 LTS will be mandatory.

You should upgrade the node Ubuntu distribution to 24.04 LTS before attempting to upgrade MAAS, so plan your maintenance window appropriately. Note that you might be required to upgrade PostgreSQL to version 16 before continuing with the MAAS upgrade (see below).

#### MAAS 3.6 recommends PostgreSQL 16 maintaining support for 14

Ubuntu 24.04 LTS comes with PostgreSQL version 16, and this is the new recommended version for use with MAAS. The minimum supported version continues to be version 14 for the time being, but it's regarded as deprecated and you should expect its support to be removed in the upcoming MAAS releases.

#### Reserved IPs

MAAS 3.6 introduces a powerful new feature allowing users to reserve an IP address for a specific MAC address within a subnet managed by MAAS. This capability ensures consistent network configuration and simplifies IP management in dynamic environments.

Previously, implementing this scenario required the use of custom DHCPd snippets, which added complexity and required manual configuration. With this release, we strongly recommend migrating to the new built-in mechanism for a streamlined, reliable, and fully integrated solution to manage reserved IP scenarios.

DHCP snippets have been deprecated in MAAS 3.6 and will be removed in the next major version.

##### How to reserve IP addresses

UI: navigate to subnets -> select a subnet -> Address reservation -> Reserve static DHCP lease

CLI: maas <username> reserved-ips -h to get started.

##### Expected behavior

When an IP/MAC reservation is configured, the following applies:

The reserved IP/MAC pair will be included in the DHCP configuration generated by MAAS. This ensures that any device with the specified MAC address requesting an IP via DHCP will always receive the reserved IP.

Upon machine deployment, the behavior varies depending on the network interface mode:

- AUTO: The reserved IP is assigned as a static IP on the deployed machine.
- DHCP: The machine will request an IP through DHCP and will receive the reserved IP.
- Static: Only the reserved IP can be configured.
- Unconfigured: The interface will remain unconfigured

##### Key constraints and rules

Observe the following constraints when reserving addresses:

- The IP must be outside any dynamic range.
- A single MAC address can only have one reserved IP within a subnet.
- A single IP cannot be reserved for multiple MAC addresses.
- Reserved IPs are immutable: to modify a reserved IP or MAC address, you must delete the existing reservation and create a new one.

#### Kernel crash dumps

We introduce the ability to enable kernel crash dumps for Ubuntu deployments.

You can configure this feature for individual deployments or enable it globally by default. Even if kernel crash dumps are enabled by default, they can be disabled on a per-machine basis during deployment.

##### Requirements

The target machine for the deployment must have:

- CPU: Minimum of 4 threads.
- RAM: Between 6 GB and 2 TB (2 TB is the current tested maximum).
- Disk Space: At least five times the RAM size as free disk space in /var

##### Enabling kernel crash dumps during deployment

For single machines:

- UI: navigate to machines -> select a machine -> Deploy -> Enable kernel crash dump
- CLI: maas <username> machine deploy <system_id> enable_kernel_crash_dump=True

For all deployments by default:

- UI: navigate to settings -> configuration/kernel parameters -> enable kernel crash dump by default
- CLI: maas <username> maas set-config name=enable_kernel_crash_dump value=True

##### Overriding default settings

If kernel crash dumps are enabled globally, you can disable them for specific machines:

- UI: Uncheck the kernel crash dump flag during deployment.
- CLI: maas <username> machine deploy <system_id> enable_kernel_crash_dump=False

#### O11y - dashboards for MAAS

With MAAS 3.6 comes the initial version of a Grafana dashboard, designed to provide a high-level overview of your current MAAS deployment. This first iteration provides insights into:

- MAAS architecture (number of region and rack controllers)
- Health of internal MAAS services
- Status of machines, networks and KVM hosts
- RPC and API call performance metrics

You can access the dashboard at <https://github.com/canonical/maas-grafana-dashboards>. As it’s a first iteration, feedback is always welcome.

### UI

#### Features

- Forms to create or edit VLANs are now side panels as most of the other forms in MAAS (#5404)
- The subnet details page was always very long and hard to understand. We added tabs for Static Routes, Address reservation, DHCP snippers and IP Address usage to make information easier to find
- Added the ability to create, update, and delete IP address reservations (see Reserved IPs above)
- Added smarter IP address validation to "Add device", "Reserve range", and "Edit interface" forms. IP addresses are now validated with respect to the subnet and the address range.
- Forms will now automatically scroll to the top if there is an error notification so that the notification is visible
- Enabled support for kernel crash dumps when deploying machines (see Kernel Crash dumps above)
- We reworked the image list to be more concise and easier to use. The image list was always using radio buttons that worked similar to tabs. We created a new user experience using side panels that is consistent with the other views in MAAS.

#### UI bug fixes

- Network discovery date truncation MAASENG-2991 (#5403)
- Html error formatting MAASENG-2935 (#5405)
- (machines) Tab link highlighting on machine summary MAASENG-3035 (#5407)
- Reserved ips treeshaking (#5418)
- Ssh key display lp#2064920 (#5426)
- DHCPTable, TagForm, VLANDetails selectors (#5448)
- (settings) Fix list spacing #5464 (#5470)
- Last commissioned time in the status bar (#5471)
- Limit WebSocket message backlog on reconnection (#5487)
- Remove length limit for MAC address fields MAASENG-3518 (#5500)
- (machines) Increase width of bond and bridge forms in Network tab (#5504)
- (zones) Unnecessary query invalidations and API calls (#5518)
- (machines) Allow deselection of machines in a selected group MAASENG-3720 (#5537)
- Enable noble as kvm host (#5557)
- (machines) Allow ports at the end of IPMI addresses LP#2087965 (#5560)
- (machines) Allow sorting by disks and storage MAASENG-4257 (#5573)
- (images) Fallback as custom image when splitting OS from resource name (#5581)

### Bug fixes

- [2060288](https://bugs.launchpad.net/maas/+bug/2060288) : maas 3.5 is returning bootx64.efi file with size 0
- [2063220](https://bugs.launchpad.net/maas/+bug/2063220) : MAAS 3.5 fails to boot machines because the rack is timing out retrieving the images
- [2063835](https://bugs.launchpad.net/maas/+bug/2063835) : in 3.5 MAAS fails to restart due to Database error during start-up
- [2069094](https://bugs.launchpad.net/maas/+bug/2069094) : Unauthenticated remote RPC command execution
- [2073731](https://bugs.launchpad.net/maas/+bug/2073731) : BMC commissioning error on HPE Gen 10 with ILO 5
- [2073731](https://bugs.launchpad.net/maas/3.6/+bug/2073731) : BMC commissioning error on HPE Gen 10 with ILO 5
- [2076910](https://bugs.launchpad.net/maas/+bug/2076910) : [3.5] \\\"crypto/rsa: verification error\\\" while trying to verify candidate authority certificate \\\"maas-ca\\\")\""
- [2097505](https://bugs.launchpad.net/maas/3.6/+bug/2097505) : dhcpd.conf write race condition
- [2098129](https://bugs.launchpad.net/maas/3.6/+bug/2098129) : chown config files - operation not permitted
- [2100477](https://bugs.launchpad.net/maas/3.6/+bug/2100477) : Lease update is broken
- [1839189](https://bugs.launchpad.net/maas/+bug/1839189) : Malformed input in the IP addr field in "power parameters" causes part of SQL error to be shown
- [1953049](https://bugs.launchpad.net/maas/+bug/1953049) : Error while calling ScanNetworks: Unable to get RPC connection for rack controller
- [1980000](https://bugs.launchpad.net/maas/+bug/1980000) : dhcpd.conf not written due to byte size of hosts value in rpc
- [2004661](https://bugs.launchpad.net/maas/+bug/2004661) : MAAS deployment failures on server with Redfish
- [2012596](https://bugs.launchpad.net/maas/+bug/2012596) : MAAS 3.2 deb package memory leak after upgrading
- [2017667](https://bugs.launchpad.net/maas/+bug/2017667) : Websocket API exposes sensitive power parameters to non-root users
- [2018590](https://bugs.launchpad.net/maas/+bug/2018590) : hardware sync partially updates new machine specs (cpu and ram)
- [2027975](https://bugs.launchpad.net/maas/+bug/2027975) : Add check on network interface name's length
- [2028000](https://bugs.launchpad.net/maas/+bug/2028000) : MAAS Redfish doesn't reboot Cisco UCS C-series appliance
- [2031482](https://bugs.launchpad.net/maas/+bug/2031482) : Subnet changed to wrong fabric, impacting DHCP
- [2033632](https://bugs.launchpad.net/maas/+bug/2033632) : New deployments do not take into account the new configurations (ephemeral_deployments, hw_sync etc..))
- [2043970](https://bugs.launchpad.net/maas/+bug/2043970) : MAAS 3.2.9 creates for Calico Interfaces 80.000 fabrics
- [2051988](https://bugs.launchpad.net/maas/+bug/2051988) : Unexpected hardware sync state change
- [2054709](https://bugs.launchpad.net/maas/+bug/2054709) : Workflow execution errors are not propagated
- [2054808](https://bugs.launchpad.net/maas/+bug/2054808) : Tag evaluation over RPC on rack fails when TLS is enabled
- [2054915](https://bugs.launchpad.net/maas/+bug/2054915) : Failed configuring DHCP on rack controller - too many values to unpack (expected 5)
- [2055347](https://bugs.launchpad.net/maas/+bug/2055347) : MAAS IPMI k_g validation error
- [2056222](https://bugs.launchpad.net/maas/+bug/2056222) : Failed configuring DHCP on rack controller
- [2056223](https://bugs.launchpad.net/maas/+bug/2056223) : Importing boot resources failed
- [2056225](https://bugs.launchpad.net/maas/+bug/2056225) : configure-agent failed (httpproxy)
- [2056330](https://bugs.launchpad.net/maas/+bug/2056330) : Ready machines with owner
- [2056740](https://bugs.launchpad.net/maas/+bug/2056740) : Can't commission/deploy AMT machines
- [2056777](https://bugs.launchpad.net/maas/+bug/2056777) : DEB packaging is broken
- [2056781](https://bugs.launchpad.net/maas/+bug/2056781) : The import of images stops if there is an exception in the workflow
- [2056792](https://bugs.launchpad.net/maas/+bug/2056792) : MAAS passes a commissioning script parameter type instead of its name as a command-line argument name
- [2057459](https://bugs.launchpad.net/maas/+bug/2057459) : when multiple images are requested for download all the temporal activities fail due to heartbeat timeout
- [2057748](https://bugs.launchpad.net/maas/+bug/2057748) : Cannot switch streams in the UI
- [2057750](https://bugs.launchpad.net/maas/+bug/2057750) : Can't pxe boot legacy non-uefi machines
- [2057767](https://bugs.launchpad.net/maas/+bug/2057767) : When machines reboot after deployment the tftp paths are wrong
- [2057917](https://bugs.launchpad.net/maas/+bug/2057917) : temporal keeps running after maas is uninstalled and collects GB of logs every day
- [2057939](https://bugs.launchpad.net/maas/+bug/2057939) : Can't find kernel when deploying a non-Ubuntu image to memory
- [2057979](https://bugs.launchpad.net/maas/+bug/2057979) : Can't download images in Maas 3.5.0 in HA mode with 3 nodes
- [2058007](https://bugs.launchpad.net/maas/+bug/2058007) : In 3.5.0 last image sync in the controller page is wrong
- [2058037](https://bugs.launchpad.net/maas/+bug/2058037) : In 3.5.0 image sync download-bootresourcefile activity fails with "integer division or modulo by zero"
- [2058273](https://bugs.launchpad.net/maas/+bug/2058273) : sync-bootresources workflow must be deterministic
- [2058332](https://bugs.launchpad.net/maas/+bug/2058332) : Temporal server can be accessed without authentication and it's possible to cancel workflows and perform other operations
- [2058377](https://bugs.launchpad.net/maas/+bug/2058377) : In 3.5.0 HA a new MAAS installation has no available architecture for deployments after the images are in synch
- [2058496](https://bugs.launchpad.net/maas/+bug/2058496) : Commissioning failed during 1st pxe install 24.04
- [2058625](https://bugs.launchpad.net/maas/+bug/2058625) : In 3.5.0 "machines create" with the cli takes several minutes
- [2058662](https://bugs.launchpad.net/maas/+bug/2058662) : soft power off not working
- [2059710](https://bugs.launchpad.net/maas/+bug/2059710) : MAAS doesn't check if there's enough disk space before migrating images
- [2059773](https://bugs.launchpad.net/maas/+bug/2059773) : LD_LIBRARY_PATH issues
- [2060133](https://bugs.launchpad.net/maas/+bug/2060133) : No events log shown in the UI
- [2060172](https://bugs.launchpad.net/maas/+bug/2060172) : A new installation of maas 3.5.0 fails to start the reverse proxy
- [2060277](https://bugs.launchpad.net/maas/+bug/2060277) : Files under /etc/maas are not removed when maas is uninstalled
- [2060278](https://bugs.launchpad.net/maas/+bug/2060278) : files under /run/lock/ are not deleted when maas is uninstalled
- [2060297](https://bugs.launchpad.net/maas/+bug/2060297) : in 3.5 maasapiserver deb is not started sometimes
- [2060687](https://bugs.launchpad.net/maas/+bug/2060687) : In 3.5 when I release a machine with the 'erase disk option' the disk is actually not erased
- [2062107](https://bugs.launchpad.net/maas/+bug/2062107) : Failed to reload DNS; serial mismatch on domains maas
- [2062141](https://bugs.launchpad.net/maas/+bug/2062141) : Hardware sync state changes are logged as AUDIT
- [2063844](https://bugs.launchpad.net/maas/+bug/2063844) : Cannot boot machine with Legacy BIOS mode
- [2064281](https://bugs.launchpad.net/maas/+bug/2064281) : MAAS 3.4 and 3.5 are not automatically moving the boot NIC to the same VLAN of the rack controller
- [2064726](https://bugs.launchpad.net/maas/+bug/2064726) : Local priviledge escalation in MAAS snap
- [2064727](https://bugs.launchpad.net/maas/+bug/2064727) : In maas 3.5 DEB the UI shows ('Connection aborted.', FileNotFoundError(2, 'No such file or directory')) and does not display any machine
- [2066276](https://bugs.launchpad.net/maas/+bug/2066276) : ipv6 test failures: AttributeError: 'RRHeader' object has no attribute '\_address'
- [2066936](https://bugs.launchpad.net/maas/+bug/2066936) : Some foreign key contraints are missing
- [2067474](https://bugs.launchpad.net/maas/+bug/2067474) : Unable to deploy lxd vm's on new 3.5.0~rc4-16292-g.18b753d78 install with new DB
- [2067793](https://bugs.launchpad.net/maas/+bug/2067793) : tftp returns 0 bytes file when dtb request resulting in boot failure
- [2067998](https://bugs.launchpad.net/maas/+bug/2067998) : MAAS resets vlan on interface if the link is not detected during commissioning
- [2068666](https://bugs.launchpad.net/maas/+bug/2068666) : MAAS API subnet allow_dns and allow_proxy are broken
- [2069059](https://bugs.launchpad.net/maas/+bug/2069059) : Ubuntu 24.04 doesn't deploy on any ARM64 machine
- [2070304](https://bugs.launchpad.net/maas/+bug/2070304) : regiond at 100% CPU after UI reconnect causing API errors
- [2072155](https://bugs.launchpad.net/maas/+bug/2072155) : Discovered ip addresses mapped to an invalid name (ending with -)
- [2055347](https://bugs.launchpad.net/maas/3.6/+bug/2055347) : MAAS IPMI k_g validation error
- [1980000](https://bugs.launchpad.net/maas/3.6/+bug/1980000) : dhcpd.conf not written due to byte size of hosts value in rpc
- [2073501](https://bugs.launchpad.net/maas/+bug/2073501) : Bionic not available for commissioning on pro-enabled systems
- [2073575](https://bugs.launchpad.net/maas/+bug/2073575) : Incorrect display of bondig options
- [2075555](https://bugs.launchpad.net/maas/+bug/2075555) : Custom OSes fail to deploy 'in memory'
- [2076292](https://bugs.launchpad.net/maas/+bug/2076292) : Installing MAAS does not install the required simplestream version
- [2076292](https://bugs.launchpad.net/maas/3.6/+bug/2076292) : Installing MAAS does not install the required simplestream version
- [2077602](https://bugs.launchpad.net/maas/+bug/2077602) : maas 3.5 ipmi machine registration issue.
- [2078052](https://bugs.launchpad.net/maas/+bug/2078052) : Squid initialization issue with pebble
- [2078810](https://bugs.launchpad.net/maas/+bug/2078810) : Can't filter by system id in the UI
- [2078869](https://bugs.launchpad.net/maas/+bug/2078869) : Deploy workflow errors with duplicate workflow ID when re-deploying immediately
- [2078941](https://bugs.launchpad.net/maas/+bug/2078941) : When the snap is initialized again the certificates are not cleaned up
- [2079797](https://bugs.launchpad.net/maas/+bug/2079797) : Redfish powerdriver should be able to handle the reset power status
- [2079987](https://bugs.launchpad.net/maas/+bug/2079987) : LeaseSocketService is sending 10 RPC calls to the region every second even if there are no updates
- [2081098](https://bugs.launchpad.net/maas/+bug/2081098) : Power error despite a valid Intel AMT configuration
- [2081182](https://bugs.launchpad.net/maas/+bug/2081182) : When I deploy a machine, MAAS is showing a machine as Off while it's actually On
- [2081262](https://bugs.launchpad.net/maas/+bug/2081262) : Missing module in MAAS snap, required for AMT power
- [2081262](https://bugs.launchpad.net/maas/3.6/+bug/2081262) : Missing module in MAAS snap, required for AMT power
- [2082260](https://bugs.launchpad.net/maas/+bug/2082260) : MAAS 3.6.0 can't redeploy a machine after a failed deployment
- [2084788](https://bugs.launchpad.net/maas/+bug/2084788) : MAAS 3.5.1 machines staying forever at commissioning
- [2087965](https://bugs.launchpad.net/maas/+bug/2087965) : Registering IPMI address with port fails on latest/edge
- [2089185](https://bugs.launchpad.net/maas/+bug/2089185) : Releasing fails with latest cloud-init on image 20241113
- [2090919](https://bugs.launchpad.net/maas/+bug/2090919) : Can't deploy a machine if the interface has a reserved ip and the interface mode is Static/DHCP
- [2091001](https://bugs.launchpad.net/maas/+bug/2091001) : Listing images is slow if you have many images in a busy MAAS
- [2091084](https://bugs.launchpad.net/maas/+bug/2091084) : Only admins should be able to create/update reserved ips
- [2091087](https://bugs.launchpad.net/maas/+bug/2091087) : MAAS can't deploy Ubuntu 16.04 on 3.6.0 alpha
- [2092172](https://bugs.launchpad.net/maas/+bug/2092172) : Redfish powerdriver I/O operation on closed file
- [2095019](https://bugs.launchpad.net/maas/+bug/2095019) : Disk Erasure Configuration Flags Not Applied During Node Release via MAAS CLI
- [2085160](https://bugs.launchpad.net/maas/3.6/+bug/2085160) : Temporal workflow deadlock
- [2095477](https://bugs.launchpad.net/maas/3.6/+bug/2095477) : boot-resources read is slow when there are a lot of images that have been deployed a lot of times
- [2098498](https://bugs.launchpad.net/maas/+bug/2098498) : maas-agent is writing dhcpd.conf to the wrong path in the snap
- [2099949](https://bugs.launchpad.net/maas/3.6/+bug/2099949) : Redfish power driver requests fails with 412 status code
- [2099952](https://bugs.launchpad.net/maas/3.6/+bug/2099952) : HW sync fails due to MAAS/metadata/2012-03-01 HTTP Error 409: Conflict
- [2100790](https://bugs.launchpad.net/maas/3.6/+bug/2100790) : MAAS KVM Host option disabled for 24.04 noble
- [2102126](https://bugs.launchpad.net/maas/3.6/+bug/2102126) : MAAS 3.6 can't power control AMT BMCs after upgrade from 3.5
- [2102135](https://bugs.launchpad.net/maas/3.6/+bug/2102135) : MAAS 3.6 can't deploy machines with bcaches (vendor specific)
- [2103654](https://bugs.launchpad.net/maas/3.6/+bug/2103654) : Lease expiry removes all IP addresses of a machine
- [2104278](https://bugs.launchpad.net/maas/3.6/+bug/2104278) : MAAS KVM deploy with 24.04 fails sshd.service not found
- [2106542](https://bugs.launchpad.net/maas/3.6/+bug/2106542) : When MAAS receives a DHCP lease it should remove all the old discovered IPs linked to the interface
- [2024466](https://bugs.launchpad.net/maas/+bug/2024466) : vm-host parameters help is wrong
- [2029522](https://bugs.launchpad.net/maas/+bug/2029522) : stacktrace on \_reap_extra_connection()
- [2043816](https://bugs.launchpad.net/maas/+bug/2043816) : Adding new rackd and downloading images causes OOM on regiond
- [2049661](https://bugs.launchpad.net/maas/+bug/2049661) : "Mark broken" error description message not shown in the machines list output
- [2056208](https://bugs.launchpad.net/maas/+bug/2056208) : No option to disable TLS verification on HMC Z
- [2056211](https://bugs.launchpad.net/maas/+bug/2056211) : Configuring an LPAR to boot on a disk doesn't work on HMC Z, which breaks deployments
- [2057935](https://bugs.launchpad.net/maas/+bug/2057935) : Can't delete an image while it is downloading
- [2067503](https://bugs.launchpad.net/maas/+bug/2067503) : maas login --cacerts can't handle non-ascii
- [2069447](https://bugs.launchpad.net/maas/+bug/2069447) : Can't power on broken machines via API in 3.4.1
- [2073540](https://bugs.launchpad.net/maas/+bug/2073540) : Error: ('Connection aborted.', FileNotFoundError(2, 'No such file or directory'))
- [2056208](https://bugs.launchpad.net/maas/3.6/+bug/2056208) : No option to disable TLS verification on HMC Z
- [2081224](https://bugs.launchpad.net/maas/+bug/2081224) : HW sync does not work on machines deployed with MAAS 2.x
- [2081842](https://bugs.launchpad.net/maas/+bug/2081842) : Some systems can fail to commission because of password length issues
- [2087945](https://bugs.launchpad.net/maas/+bug/2087945) : maas block-devices id_path returns unstable path
- [2091979](https://bugs.launchpad.net/maas/+bug/2091979) : Redfish power driver reports twisted errors on retries
- [2095186](https://bugs.launchpad.net/maas/+bug/2095186) : Flaky test mark node failed
- [2096818](https://bugs.launchpad.net/maas/+bug/2096818) : Unable to reuse static IP for network interface bond after commissioning

### Internal changes

This section mentions changes that affect users only indirectly:

- DHCP is now configured via a Temporal workflow for robust, retryable updates
