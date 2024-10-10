> *Errors or typos? Topics missing? Hard to read? <a href="https://docs.google.com/forms/d/e/1FAIpQLScIt3ffetkaKW3gDv6FDk7CfUTNYP_HGmqQotSTtj2htKkVBw/viewform?usp=pp_url&entry.1739714854=https://maas.io/docs/what-is-new-with-maas-3-4" target = "_blank">Let us know.</a>*

## Release history

This section recaps the release history of MAAS version 3.4.

### MAAS 3.4.2 has been released

We are happy to announce that MAAS 3.4.2 has been released, with the following bug fixes:

- [2012596](https://bugs.launchpad.net/maas/+bug/2012596)**^**: MAAS 3.2 deb package memory leak after upgrading
- [2033632](https://bugs.launchpad.net/maas/+bug/2033632)**^**: New deployments do not take into account the new configurations (ephemeral_deployments, hw_sync etc..))
- [2043970](https://bugs.launchpad.net/maas/+bug/2043970)**^**: MAAS 3.2.9 creates for Calico Interfaces 80.000 fabrics
- [2051988](https://bugs.launchpad.net/maas/+bug/2051988)**^**: Unexpected hardware sync state change
- [2054915](https://bugs.launchpad.net/maas/+bug/2054915)**^**: Failed configuring DHCP on rack controller - too many values to unpack (expected 5)
- [2056050](https://bugs.launchpad.net/maas/+bug/2056050)**^**: MAAS doesn't allow specify port for Forward DNS server
- [2062107](https://bugs.launchpad.net/maas/+bug/2062107)**^**: Failed to reload DNS; serial mismatch on domains maas
- [2064281](https://bugs.launchpad.net/maas/+bug/2064281)**^**: MAAS 3.4 and 3.5 are not automatically moving the boot NIC to the same VLAN of the rack controller
- [1887558](https://bugs.launchpad.net/maas/+bug/1887558)**^**: multipathd bcache disks do not get picked up by multipath-tools during boot

### MAAS 3.4.1 has been released

We are happy to announce that MAAS 3.4.1 has been released, with a large number of bug fixes:

- [2053033](https://bugs.launchpad.net/maas/+bug/2053033)**^**: Creating MAAS Virsh VM does not work (libvirt: error)
- [2033505](https://bugs.launchpad.net/maas/+bug/2033505)**^**: Failed to update regiond's processes and endpoints
- [2018476](https://bugs.launchpad.net/maas/+bug/2018476)**^**: Postgres deprecation notice does not give upgrade instructions
- [2026824](https://bugs.launchpad.net/maas/+bug/2026824)**^**: Enlistment fail for a machine with BIOS Legacy if PXE interface is the second one
- [2029417](https://bugs.launchpad.net/maas/+bug/2029417)**^**: RPC failure to contact rack/region - operations on closed handler
- [2034014](https://bugs.launchpad.net/maas/+bug/2034014)**^**: Conflict error during w3 request
- [2015411](https://bugs.launchpad.net/maas/+bug/2015411)**^**: StaticIPAddress matching query does not exist.
- [2040188](https://bugs.launchpad.net/maas/+bug/2040188)**^**: MAAS config option for IPMI cipher suite ID is not passed to bmc-config script
- [2041276](https://bugs.launchpad.net/maas/+bug/2041276)**^**: [MAAS 3.2.9] Adding subnet sends named into crash loop [rdns zones]
- [2048519](https://bugs.launchpad.net/maas/+bug/2048519)**^**: Migration during the upgrade to 3.4 stable is failing for MAAS instances that were originally installed with 1.x
- [2048399](https://bugs.launchpad.net/maas/+bug/2048399)**^**: MAAS LXD VM creation issue (Ensure this value is less than or equal to 0)
- [2049508](https://bugs.launchpad.net/maas/+bug/2049508)**^**: MAAS has orphan ip addresses and dns records that are slowing down the entire service
- [2044403](https://bugs.launchpad.net/maas/+bug/2044403)**^**: allow_dns=false doesn't take effect - MAAS DNS is added to an interface with allowed_dns=false
- [2052958](https://bugs.launchpad.net/maas/+bug/2052958)**^**: PPC64 machines without disk serial fail condense LUNs
- [1852745](https://bugs.launchpad.net/maas/+bug/1852745)**^**: UI authentication session is not expiring
- [1928873](https://bugs.launchpad.net/maas/+bug/1928873)**^**: MAAS Web UI doesn't allow specifying soft stop_mode
- [2042847](https://bugs.launchpad.net/maas/+bug/2042847)**^**: Machines commonly appear in reverse alphabetical order
- [1996500](https://bugs.launchpad.net/maas/+bug/1996500)**^**: UI: Subnets page pagination - a group can be displayed on two pages
- [2054672](https://bugs.launchpad.net/maas/+bug/2054672)**^**: Deploying a server with bcache on top of HDD and mdadm can frequently fail

### MAAS 3.4 has been released

We are happy to announce that MAAS 3.4 has been released.

## Features

MAAS 3.4 provides several new features.

### Redesigned UI

The MAAS User Interface (UI) has undergone a significant redesign, introducing the MAAS UI new layout. This new layout incorporates various features and improvements aimed at enhancing the user experience for MAAS users and operators who primarily interact with the UI.  The MAAS UI new layout introduces several enhancements that aim to improve usability, customisation, and navigation within the application

- Customised column visibility: One of the major improvements in the MAAS UI new layout is the ability for users to customize the visibility of columns on the machine list. This feature empowers users to focus on the specific information they need, while hiding irrelevant columns. By allowing users to tailor their view, this enhancement improves readability, reduces clutter, and provides a more personalised experience.

- Action forms in side panel: Previously, the action forms in MAAS were located in the header section, which made it less intuitive for users to access and interact with them. The redesigned UI moves these action forms to the side panel, providing a more logical placement and easy access to perform actions on machines. This change enhances the usability of the forms and improves the overall workflow for users.

- Streamlined action button group: The introduction of a new action button group eliminates the need for the previous "Take action" menu. Users can now directly access commonly used actions for machines, both in the details view and the machine list. This streamlines the workflow and simplifies the process of performing actions on machines, saving users time and effort.

- Improved side navigation: To enhance navigation within the application, the MAAS UI new layout implements a new side navigation system. Users can conveniently navigate through different sections of the app using the side panel. Additionally, the inclusion of a secondary side navigation specifically for settings and account pages improves the organisation and accessibility of these sections.

#### Intended Benefits

The MAAS UI was redesigned with several user benefits in mind.

- Enhanced table interaction: Users can now customize their views by selecting the columns they care about the most. This modular table feature allows for a personalised experience, ensuring users can focus on the information that matters to them.

- Improved form interaction: Forms in the MAAS UI have been redesigned to scale with the content. By migrating all forms into panels, users have more space to view other components such as the machine list, resulting in a more comfortable and efficient form interaction experience.

- Efficient navigation: The new layout addresses the challenges posed by a growing navigation menu. With the introduction of the side panel navigation, users can easily explore different sections of the app, providing a scalable and user-friendly navigation experience.

- Enhanced search capability: The MAAS UI new layout improves the efficiency of the search feature. Users can search for machines based on conventions and tags, making it easier to find specific machines and take actions. The new layout also provides clearer feedback when the "take action" button is disabled, enhancing the overall search and interaction experience.

- Performance improvements based on user feedback: Based on user feedback received through Discourse, several performance issues have been identified and addressed. The MAAS team has worked diligently to optimise machine information loading times and resolve delays encountered while opening machine pages. These performance improvements ensure a smoother and faster user experience when interacting with the MAAS UI.

The MAAS UI new layout introduces a redesigned interface with enhanced features to provide a more efficient and user-friendly experience for MAAS users and operators. By allowing users to customize their views, streamlining form interactions

<!--
- DGX kernel support: There’s ongoing work from Canonical to provide an optimised kernel for Nvidia DGX machines. We want to promote that and make sure that DGX machines use that optimised kernel by default, without the user having to do any special configuration.
-->

### Configurable session timeout

In MAAS 3.4, we've introduced the Configurable Session Timeout feature, offering better control over session length. This feature allows you to set a personalised duration for your sessions, hopefully avoiding abrupt disconnections or lingering sessions.  If you're a user who has login repeatedly, due to short session defaults, or you're concerned about leaving your session accessible for too long, setting a custom timeout is useful and potentially more secure.

### Packer MAAS - SLES

The MAAS 3.4 release expands Packer support to include SUSE Linux Enterprise Server (SLES), expanding the the list of deployable Linux distributions.  We also support openSUSE and openSUSE Tumbleweed. And we’ve added a template for Red Hat Enterprise Linux (RHEL) version 9.

## Installation

MAAS will run on [just about any modern hardware configuration](/t/installation-requirements/6233).

- [How to do a fresh install of MAAS 3.4](/t/how-to-install-maas/5128): Use the tabs to select snaps or packages.

- [How to upgrade from an earlier version to MAAS 3.4](/t/how-to-upgrade-maas/5436): Use the tabs to select snaps or packages.

- [Initialise MAAS for a production configuration](/t/how-to-install-maas/5128#heading--init-maas-production)

## Bug fixes

<a href id="heading--3-4-1-bugs"> </a>

### MAAS 3.4.1

- [2053033](https://bugs.launchpad.net/maas/+bug/2053033)**^**: Creating MAAS Virsh VM does not work (libvirt: error)
- [2033505](https://bugs.launchpad.net/maas/+bug/2033505)**^**: Failed to update regiond's processes and endpoints
- [2018476](https://bugs.launchpad.net/maas/+bug/2018476)**^**: Postgres deprecation notice does not give upgrade instructions
- [2026824](https://bugs.launchpad.net/maas/+bug/2026824)**^**: Enlistment fail for a machine with BIOS Legacy if PXE interface is the second one
- [2029417](https://bugs.launchpad.net/maas/+bug/2029417)**^**: RPC failure to contact rack/region - operations on closed handler
- [2034014](https://bugs.launchpad.net/maas/+bug/2034014)**^**: Conflict error during w3 request
- [2015411](https://bugs.launchpad.net/maas/+bug/2015411)**^**: StaticIPAddress matching query does not exist.
- [2040188](https://bugs.launchpad.net/maas/+bug/2040188)**^**: MAAS config option for IPMI cipher suite ID is not passed to bmc-config script
- [2041276](https://bugs.launchpad.net/maas/+bug/2041276)**^**: [MAAS 3.2.9] Adding subnet sends named into crash loop [rdns zones]
- [2048519](https://bugs.launchpad.net/maas/+bug/2048519)**^**: Migration during the upgrade to 3.4 stable is failing for MAAS instances that were originally installed with 1.x
- [2048399](https://bugs.launchpad.net/maas/+bug/2048399)**^**: MAAS LXD VM creation issue (Ensure this value is less than or equal to 0)
- [2049508](https://bugs.launchpad.net/maas/+bug/2049508)**^**: MAAS has orphan ip addresses and dns records that are slowing down the entire service
- [2044403](https://bugs.launchpad.net/maas/+bug/2044403)**^**: allow_dns=false doesn't take effect - MAAS DNS is added to an interface with allowed_dns=false
- [2052958](https://bugs.launchpad.net/maas/+bug/2052958)**^**: PPC64 machines without disk serial fail condense LUNs
- [1852745](https://bugs.launchpad.net/maas/+bug/1852745)**^**: UI authentication session is not expiring
- [1928873](https://bugs.launchpad.net/maas/+bug/1928873)**^**: MAAS Web UI doesn't allow specifying soft stop_mode
- [2042847](https://bugs.launchpad.net/maas/+bug/2042847)**^**: Machines commonly appear in reverse alphabetical order
- [1996500](https://bugs.launchpad.net/maas/+bug/1996500)**^**: UI: Subnets page pagination - a group can be displayed on two pages
- [2054672](https://bugs.launchpad.net/maas/+bug/2054672)**^**: Deploying a server with bcache on top of HDD and mdadm can frequently fail

### MAAS 3.4.0

Here is the list of bug fixes for all versions of MAAS 3.4, from first Beta through final release:

- (3.4.0)[2038381](https://bugs.launchpad.net/maas/+bug/2003745)**^**:	Hardware Sync Docs link in UI leads to a 404
- (3.4.0)[2045228](https://bugs.launchpad.net/maas/+bug/2003745)**^**:	DNS updates are consumed concurrently, leading to an incorrect nsupdate payload
- (3.4.0)[1908452](https://bugs.launchpad.net/maas/+bug/2003745)**^**:	MAAS stops working and deployment fails after `Loading ephemeral` step
- (3.4.0)[2022082](https://bugs.launchpad.net/maas/+bug/2003745)**^**:	30-maas-01-bmc-config commissioning script fails on Power9 (ppc64le)
- (3.4-rc1)[2003745](https://bugs.launchpad.net/maas/+bug/2003745)**^**: Cannot deploy older Ubuntu releases
- (3.4-rc1)[2026802](https://bugs.launchpad.net/maas/+bug/2026802)**^**: MAAS 3.4 installed with deb fails to start the rack due to permission error
- (3.4-rc1)[2027735](https://bugs.launchpad.net/maas/+bug/2027735)**^**: Concurrent API calls don't get balanced between regiond processes
- (3.4-rc1)[2029481](https://bugs.launchpad.net/maas/+bug/2029481)**^**: MAAS 3.4 RC (Aug 2nd 2023) breaks DNS
- (3.4-rc1)[2003812](https://bugs.launchpad.net/maas/+bug/2003812)**^**: MAAS servers have two NTP clients
- (3.4-rc1)[2023138](https://bugs.launchpad.net/maas/+bug/2023138)**^**: UI: Deleted machines don't correctly update MAAS web UI
- (3.4-rc1)[2022926](https://bugs.launchpad.net/maas/+bug/2022926)**^**: Wrong metadata url in enlist cloud-config
- (3.4-rc1)[2012801](https://bugs.launchpad.net/maas/+bug/2012801)**^**: MAAS rDNS returns two hostnames that lead to Services not running that should be: apache2, SSLCertificateFile: file '/etc/apache2/ssl//cert_ does not exist or is empty
- (3.4-rc1)[2025375](https://bugs.launchpad.net/maas/+bug/2025375)**^**: Machine listing pagination displays incorrect total number of pages
- (3.4-rc1)[2027621](https://bugs.launchpad.net/maas/+bug/2027621)**^**: ipv6 addresses in dhcpd.conf
- (3.4-rc1)[1914812](https://bugs.launchpad.net/maas/+bug/1914812)**^**: curtin fails to deploy centos 8 on nvme with multipath from ubuntu 20.04
- (3.4-rc1)[2020397](https://bugs.launchpad.net/maas/+bug/2020397)**^**: Custom images which worked ok is not working with 3.2
- (3.4-rc1)[2024625](https://bugs.launchpad.net/maas/+bug/2024625)**^**: DNS Forward failures
- (3.4-rc1)[1880016](https://bugs.launchpad.net/maas/+bug/1880016)**^**: show image last synced time 
- (3.4-rc1)[2023207](https://bugs.launchpad.net/maas/+bug/2023207)**^**: MAAS Images show "last deployed" as null even after being deployed
- (3.4-rc1)[2025468](https://bugs.launchpad.net/maas/+bug/2025468)**^**: maas-dhcp-helper stopped working which gives issues with DNS updates
- (3.4-rc1)[1995053](https://bugs.launchpad.net/maas/+bug/1995053)**^**: maas config-tls requires root but WebUI instruction assumes a normal user
- (3.4-rc1)[2018310](https://bugs.launchpad.net/maas/+bug/2018310)**^**: MAAS UI warns about PostgreSQL version but link does not help 
- (3.4-beta3)[2020882](https://bugs.launchpad.net/maas/+bug/2020882)**^**: Machine config hints FileNotFoundError
- (3.4-beta3)[2022833](https://bugs.launchpad.net/maas/+bug/2022833)**^**: machine-config-hints fails on Power machines
- (3.4-beta3)[1835153](https://bugs.launchpad.net/maas/+bug/1835153)**^**: Ephemeral deployment creates pending ScriptResult
- (3.4-beta3)[1996204](https://bugs.launchpad.net/maas/+bug/1996204)**^**: failing metrics cause 500 error
- (3.4-beta3)[2011841](https://bugs.launchpad.net/maas/+bug/2011841)**^**: DNS resolution fails
- (3.4-beta3)[2013529](https://bugs.launchpad.net/maas/+bug/2013529)**^**: Nodes stuck in Failed Disk Erasing due to wrong ipxe boot file
- (3.4-beta3)[2021965](https://bugs.launchpad.net/maas/+bug/2021965)**^**: MAAS Settings (sidebar) scroll issue
- (3.4-beta3)[1807725](https://bugs.launchpad.net/maas/+bug/1807725)**^**: Machine interfaces allow '_' character, results on a interface based domain breaking bind (as it doesn't allow it for the host part).
- (3.4-beta3)[2006497](https://bugs.launchpad.net/maas/+bug/2006497)**^**: unsupported configuration in virsh command
- (3.4-beta3)[2011853](https://bugs.launchpad.net/maas/+bug/2011853)**^**: Auto-discovered subnet does not get correct VLAN 
- (3.4-beta3)[2020865](https://bugs.launchpad.net/maas/+bug/2020865)**^**: flaky test: src/tests/maasperf/cli/test_machines.py::test_perf_list_machines_CLI- [1974050](https://bugs.launchpad.net/bugs/1974050)**^**: Vmware no longer supports image cloning
- (3.4-beta2)[2009209](https://bugs.launchpad.net/bugs/2009209)**^**: snap deployed maas is not able to use openstack nova power type due to missing python3-novaclient dependency
- (3.4-beta2)[1830619](https://bugs.launchpad.net/bugs/1830619)**^**: The "authoritative" field value is ignored when creating/editing domains
- (3.4-beta2)[1914762](https://bugs.launchpad.net/bugs/1914762)**^**: test network configuration broken with openvswitch bridge
- (3.4-beta2)[1999668](https://bugs.launchpad.net/bugs/1999668)**^**: reverse DNS not working for some interfaces
- (3.4-beta2)[2016908](https://bugs.launchpad.net/bugs/2016908)**^**: udev fails to make prctl() syscall with apparmor=0 (as used by maas by default)
- (3.4-beta2)[2019229](https://bugs.launchpad.net/bugs/2019229)**^**: 3.4.0~beta1 maas-region-api fails to start with pylxd 2.3.2~alpha1-420-10-g.72426bf~ubuntu22.04.1
- (3.4-beta2)[1818672](https://bugs.launchpad.net/bugs/1818672)**^**: Option to show full name of a user in the UI
- (3.4-beta2)[1823153](https://bugs.launchpad.net/bugs/1823153)**^**: maas init doesn't check if the user or email already exists
- (3.4-beta2)[1876365](https://bugs.launchpad.net/bugs/1876365)**^**: host passthrough not working with KVMs
- (3.4-beta2)[2018149](https://bugs.launchpad.net/bugs/2018149)**^**: MAAS generates netplan with illegal autoconf and accept_ra flags for 22.04
- (3.4-beta2)[2020427](https://bugs.launchpad.net/bugs/2020427)**^**: crash importing large database dump into maas-test-db
- (3.4-beta1)[1999160](https://bugs.launchpad.net/bugs/1999160)**^**:	Region controller fails to run commissioning scripts in proxied environment		
- (3.4-beta1)[1999191](https://bugs.launchpad.net/bugs/1999191)**^**:	bad interaction between Colorama and the CLI		
- (3.4-beta1)[1999557](https://bugs.launchpad.net/bugs/1999557)**^**:	MAAS fails to startup when installed from deb package and vault is enabled		
- (3.4-beta1)[2002109](https://bugs.launchpad.net/bugs/2002109)**^**:	Migration of BMC power credentials fails with manual driver		
- (3.4-beta1)[2002111](https://bugs.launchpad.net/bugs/2002111)**^**:	Connection to local Vault fails if proxy is configured		
- (3.4-beta1)[2003888](https://bugs.launchpad.net/bugs/2003888)**^**:	Grouped machine list view: Inconsistent display when machine state changes		
- (3.4-beta1)[1743648](https://bugs.launchpad.net/bugs/1743648)**^**:	Image import fails		
- (3.4-beta1)[1811799](https://bugs.launchpad.net/bugs/1811799)**^**:	Normal users can read machine details of owned machines		
- (3.4-beta1)[1812377](https://bugs.launchpad.net/bugs/1812377)**^**:	An admin is allowed to create raids for an Allocated node in the UI, but not the API		
- (3.4-beta1)[1958451](https://bugs.launchpad.net/bugs/1958451)**^**:	power_driver parameter is not preserved		
- (3.4-beta1)[1990172](https://bugs.launchpad.net/bugs/1990172)**^**:	"20-maas-03-machine-resources" commissioning script improperly reports a Pass when the test fails		
- (3.4-beta1)[1995084](https://bugs.launchpad.net/bugs/1995084)**^**:	MAAS TLS sets HSTS forcibly and with too short value		
- (3.4-beta1)[1999147](https://bugs.launchpad.net/bugs/1999147)**^**:	[3.3.0-candidate] failure when arch is requested as a filter		
- (3.4-beta1)[1999368](https://bugs.launchpad.net/bugs/1999368)**^**:	[3.3.0 RC] wrong DNS records		
- (3.4-beta1)[1999579](https://bugs.launchpad.net/bugs/1999579)**^**:	MAAS OpenAPI docs are not available in air-gapped mode		
- (3.4-beta1)[2001546](https://bugs.launchpad.net/bugs/2001546)**^**:	Server reboot will make subnet entries disappear from zone.maas-internal		
- (3.4-beta1)[2003310](https://bugs.launchpad.net/bugs/2003310)**^**:	Refresh scripts are not re-run if they pass, but fail to report the results to the region		
- (3.4-beta1)[2003940](https://bugs.launchpad.net/bugs/2003940)**^**:	MAAS 3.3 RC shows incorrect storage amount		
- (3.4-beta1)[2008275](https://bugs.launchpad.net/bugs/2008275)**^**:	Intel AMT support is broken in MAAS 3.3.0		
- (3.4-beta1)[2009137](https://bugs.launchpad.net/bugs/2009137)**^**:	MAAS OpenApi Schema missing parameters		
- (3.4-beta1)[2009186](https://bugs.launchpad.net/bugs/2009186)**^**:	CLI results in connection timed out when behind haproxy and 5240 is blocked		
- (3.4-beta1)[2009805](https://bugs.launchpad.net/bugs/2009805)**^**:	machine deploy install_kvm=True fails		
- (3.4-beta1)[2011274](https://bugs.launchpad.net/bugs/2011274)**^**:	MAAS 3.4: Deployment fails on LXD VMs		
- (3.4-beta1)[2011822](https://bugs.launchpad.net/bugs/2011822)**^**:	Reverse DNS resolution fails for some machines		
- (3.4-beta1)[2012139](https://bugs.launchpad.net/bugs/2012139)**^**:	maas commands occasionally fail with NO_CERTIFICATE_OR_CRL_FOUND when TLS is enabled		
- (3.4-beta1)[2017504](https://bugs.launchpad.net/bugs/2017504)**^**:	Cannot deploy from the cli when "Allow DNS resolution" is set on minimal subnet		
- (3.4-beta1)[1696108](https://bugs.launchpad.net/bugs/1696108)**^**:	Interface model validates the MAC address twice		
- (3.4-beta1)[1773150](https://bugs.launchpad.net/bugs/1773150)**^**:	smartctl verify fails due to Unicode in Disk Vendor Name		
- (3.4-beta1)[1773671](https://bugs.launchpad.net/bugs/1773671)**^**:	MAC address column should use mono font		
- (3.4-beta1)[1959648](https://bugs.launchpad.net/bugs/1959648)**^**:	Websocket vlan handler should include associated subnet ids		
- (3.4-beta1)[1979403](https://bugs.launchpad.net/bugs/1979403)**^**:	commission failed with MAAS 3.1 when BMC has multiple channels but the first channel is disabled		
- (3.4-beta1)[1986590](https://bugs.launchpad.net/bugs/1986590)**^**:	maas-cli from PPA errors out with traceback - (3.4-beta1)ModuleNotFoundError: No module named 'provisioningserver'		
- (3.4-beta1)[1990416](https://bugs.launchpad.net/bugs/1990416)**^**:	MAAS reports invalid command to run when maas-url is incorrect		
- (3.4-beta1)[1993618](https://bugs.launchpad.net/bugs/1993618)**^**:	Web UI redirection policy can invalidate HAProxy and/or TLS setup		
- (3.4-beta1)[1994945](https://bugs.launchpad.net/bugs/1994945)**^**:	Failure to create ephemeral VM when no architectures are found on the VM host		
- (3.4-beta1)[1996997](https://bugs.launchpad.net/bugs/1996997)**^**:	LXD resources fails on a Raspberry Pi with no Ethernet		
- (3.4-beta1)[1999064](https://bugs.launchpad.net/bugs/1999064)**^**:	`maas_run_scripts.py` does not clean up temporary directory		
- (3.4-beta1)[2002550](https://bugs.launchpad.net/bugs/2002550)**^**:	Controller type displays as "Undefined"		
- (3.4-beta1)[2007297](https://bugs.launchpad.net/bugs/2007297)**^**:	LXD REST API connection goes via proxy		
- (3.4-beta1)[2009045](https://bugs.launchpad.net/bugs/2009045)**^**:	WebSocket API to report reasons for failure for machine bulk actions		
- (3.4-beta1)[2009140](https://bugs.launchpad.net/bugs/2009140)**^**:	MAAS OpenApi Schema cutoff variable names		
- (3.4-beta1)[2012054](https://bugs.launchpad.net/bugs/2012054)**^**:	RPC logging when debug is too verbose
