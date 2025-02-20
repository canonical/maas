These release notes for MAAS summarize new features, bug fixes and backwards-incompatible changes in each version.

## Releases
[Version 3.5](https://maas.io/docs/release-notes-and-upgrade-instructions#p-9229-version-35-release-notes)
[Version 3.4](https://maas.io/docs/release-notes-and-upgrade-instructions#p-9229-version-34-release-notes)

### Older releases
 [MAAS 3.3 release notes](https://maas.io/docs/reference-release-notes-maas-3-3)
 [MAAS 3.2 release notes](https://maas.io/docs/reference-release-notes-maas-3-2)
 [MAAS 3.1 release notes](https://maas.io/docs/reference-release-notes-maas-3-1)
 [MAAS 3.0 release notes](https://maas.io/docs/reference-release-notes-maas-3-0)
 [MAAS 2.9 release notes](https://maas.io/docs/reference-release-notes-maas-2-9)
 [MAAS 2.8 release notes](https://maas.io/docs/reference-release-notes-maas-2-8)
 [MAAS 2.7 release notes](https://maas.io/docs/reference-release-notes-maas-2-7)

<!--
## Release policy and schedule

Our release cadence is roughly two versions per calendar year, depending upon when we reach feature-complete.

## Version support

We support two releases of MAAS plus one Beta release (when available).  The two previous releases are supported by Canonical Systems Engineering Group.  At any given time, support is available for four releases plus one Beta release (when available).
-->
## Version 3.5 release notes

This section recaps the release history of MAAS version 3.5.

### MAAS 3.5.3 has been released

We are happy to announce that MAAS 3.5.3 has been released, with the following bug fixes
 - [2040324](https://bugs.launchpad.net/maas/3.5/+bug/2040324)**^** : Power configuration change fails with <image> is not a valid distro series error
 - [2058496](https://bugs.launchpad.net/maas/3.5/+bug/2058496)**^** : Commissioning failed during 1st pxe install 24.04
 - [2072155](https://bugs.launchpad.net/maas/3.5/+bug/2072155)**^** : Discovered ip addresses mapped to an invalid name (ending with -)
 - [2055347](https://bugs.launchpad.net/maas/3.5/+bug/2055347)**^** : MAAS IPMI k_g validation error
 - [2073501](https://bugs.launchpad.net/maas/3.5/+bug/2073501)**^** : Bionic not available for commissioning on pro-enabled systems
 - [2078810](https://bugs.launchpad.net/maas/3.5/+bug/2078810)**^** : Can't filter by system id in the UI
 - [2084788](https://bugs.launchpad.net/maas/3.5/+bug/2084788)**^** : MAAS 3.5.1 machines staying forever at commissioning
 - [2063457](https://bugs.launchpad.net/maas/3.5/+bug/2063457)**^** : dhcpd6.conf can contain IPv4 nameserver options
 - [2091001](https://bugs.launchpad.net/maas/3.5/+bug/2091001)**^** : Listing images is slow if you have many images in a busy MAAS
 - [2089185](https://bugs.launchpad.net/maas/3.5/+bug/2089185)**^** : Releasing fails with latest cloud-init on image 20241113
 - [2058063](https://bugs.launchpad.net/maas/3.5/+bug/2058063)**^** : Controllers show different versions when installed with debs

### MAAS 3.5.2 has been released

We are happy to announce that MAAS 3.5.2 has been released, with the following bug fixes
- [2079987](https://bugs.launchpad.net/bugs/2079987)**^**:  LeaseSocketService is sending 10 RPC calls to the region every second even if there are no updates 
- [2079797](https://bugs.launchpad.net/bugs/2079797)**^**:  Redfish powerdriver should be able to handle the reset power status 
- [2075555](https://bugs.launchpad.net/bugs/2075555)**^**:  Custom OSes fail to deploy 'in memory' 
- [2069059](https://bugs.launchpad.net/bugs/2069059)**^**:  Ubuntu 24.04 doesn't deploy on any ARM64 machine 
- [2078941](https://bugs.launchpad.net/bugs/2078941)**^**:  When the snap is initialized again the certificates are not cleaned up 
- [2004661](https://bugs.launchpad.net/bugs/2004661)**^**:  MAAS deployment failures on server with Redfish 
- [2076910](https://bugs.launchpad.net/bugs/2076910)**^**:  'crypto/rsa: verification error' while trying to verify candidate authority certificate 'maas-ca' 
- [2077602](https://bugs.launchpad.net/bugs/2077602)**^**:   Unknown power configuration error for new machines registered with IPMI
- [2078052](https://bugs.launchpad.net/bugs/2078052)**^**:   Squid initialization issue with pebble - [2039737](https://bugs.launchpad.net/bugs/2039737)**^**:   Page sizing on machine table doesn't work
- [2081262](https://bugs.launchpad.net/bugs/2081262)**^**:   Missing module in MAAS snap, required for AMT power

### MAAS 3.5.1 has been released

We are happy to announce that MAAS 3.5.1 has been released, with the following bug fixes
- [2073731](https://bugs.launchpad.net/bugs/2073731)**^**: BMC commissioning error on HPE Gen 10 with ILO 5
- [1953049](https://bugs.launchpad.net/bugs/1953049)**^**: Error while calling ScanNetworks: Unable to get RPC connection for rack controller
- [1980000](https://bugs.launchpad.net/bugs/1980000)**^**: dhcpd.conf not written due to byte size of hosts value in rpc
- [2073575](https://bugs.launchpad.net/bugs/2073575)**^**: Incorrect display of bondig options
- [2076292](https://bugs.launchpad.net/bugs/2076292)**^**: Installing MAAS does not install the required simplestream version
- [2073540](https://bugs.launchpad.net/bugs/2073540)**^**: 	Error: ('Connection aborted.', FileNotFoundError(2, 'No such file or directory'))

### Capabilities added in MAAS 3.5

MAAS 3.5 delivers substantial improvements in core functionality.  We've integrated Temporal for enhanced process and thread management, and started a transition to Go, re-implementing some of the rack controller functions as the "MAAS agent."  We've standardized logging and monitoring to use tools like syslogd, stepping away from the custom code we had been using.  We've also expanded the capabilities of existing features to include comprehensive service monitoring and support for deploying ephemeral (RAM-only) OS images.  And we've made great strides in visibly improving the performance of MAAS.

#### Faster and more efficient image storage and sync

MAAS previously stored the boot resources (boot-loaders, kernels and disk images) in the MAAS database, and then replicated them on all Rack controllers. This make operations difficult and slow, as the database quickly became huge and files had to be transferred to all Racks before they were available for use. To address this issue, we have moved the resource storage from the database to the Region controller, and repurposed the storage in the Rack.

#### Storing boot resources in the Region Controllers

All boot resources are stored in the local disk in each Controller host (`/var/lib/maas/image-storage` for *deb* or `$SNAP_COMMON/maas/image-storage` for *snap*). MAAS checks the contents of these directories on every start-up, removing unknown/stale files and downloading any missing resource. 

MAAS checks the amount of disk space available before downloading any resource, and stops synchronizing files if there isn't enough free space. This error will be reported in the logs and a banner in the Web UI.

#### Storage use by the Rack Controller 

Images are no longer copied from the MAAS database to the rack. Instead, the rack downloads images from the region on-demand.  This works well with the redesign of the rack controller (now known as the *MAAS agent*), which has been re-imagined as a 4G LRU caching agent.  The MAAS agent has limited storage space, managing cache carefully, but it is possible to configure the size of this cache if you need to do so.

As boot resources are now downloaded from a Region controller on-demand, a fast and reliable network connection between Regions and Racks is essential for a smooth operation. Adjusting the cache size might also be important for performance if you regularly deploy a large number of different systems.

#### One-time image migration process

The first Region controller that upgrades will try to move all images out of the database. This is a background operation performed after all database migrations are applied, and **it's not reversible**. This is also a blocking operation, so MAAS might be un-available for some time (i.e., you should plan for some downtime during the upgrade process). 

MAAS will check if the host has enough disk space before starting to export the resources, and it will not proceed otherwise. In order to discover how much disk space you need for all your images, you can run the following SQL query in MAAS database before upgrading:

```sql
select sum(n."size") from (select distinct on (f."sha256") f."size" from maasserver_bootresourcefile f order by f."sha256") n;
```

The controllers are no longer capable of serving boot resources directly from the database, and won't be able to commission or to deploy machines until this migration succeeds. If the process fails, you must free enough disk space and restart the controller for the migration to be attempted again.

#### Sync works differently

When downloading boot resources from an upstream source (e.g. images.maas.io), MAAS divides the workload between all Region controllers available, so each file is downloaded only once, but not all by the same controller. After all external files were fetched, the controllers synchronize files among them in a peer-to-peer fashion. This requires **direct communication between Regions to be allowed**, so you should review your firewall rules before upgrading.

In this new model, a given image is *only* available for deployment after *all* regions have it, although stale versions can be used until everyone is up to date. This differs from previous versions where the boot resource needed to be copied to all Rack controllers before it was available, meaning that the images should be ready for use sooner.

#### Faster machine listing when deploying many machines

We have made the MAAS machine listing considerably faster for large page sizes.

#### Soft Power Off

MAAS 3.5 allows you to execute a "soft" power-off for one or more machines.  Rather than commanding a power-off via the BMC, MAAS will ask the running OS to power-down the machine.  This allows machines to go through their normal shutdown routines before powering off.

#### Improved "Select All" in the machine list

With MAAS 3.5, you can select only the machines that are visible on the current page. 

#### Improved support for multipath storage devices

MAAS support of multipath storage devices has been reviewed and improved, and now it's capable of correctly identifying the following technologies:

* SCSI
* iSCSI
* Fiber Channel
* SAS (including wide port and expanders)

When one of these devices is detected by the commissioning scripts, MAAS will suppress the duplicated disks.

#### MAAS services exposed as Prometheus metrics

All services found in the *Hardware > Controllers > <controller> > Services* panel are now exposed as Prometheus metrics, to include: 

- regiond
- bind9
- NTP
- proxy
- syslog
- reverse-proxy
- rackd
- HTTP
- TFTP
- dhcpd(v4)
- dhcpd6
- DNS

This should improve the user's ability to monitor MAAS.

#### Monitoring setup sequence updated

Also, the monitoring setup sequence for MAAS [has changed](/t/how-to-monitor-maas/5204).

#### Logs collapsed into system log files

With the advent of 3.5, all of the separate logs used by MAAS through version 3.4 have been eliminated and replaced with logging into the standard `systemd` files.  See [How to use MAAS systemd logs](/t/how-to-use-maas-systemd-logs/8103) in the documentation set for details.

#### Deployment of Oracle Linux 8 and 9 on MAAS machines

Concurrent with the release of MAAS 3.5, we have added Oracle Linux 8 and Oracle Linux 9 to the stable of custom OS images that can be deployed on MAAS machines.

#### Ephemeral OS deployments

With the release of MAAS 3.5, ephemeral deployments for Ubuntu and custom images should succeed.  Networking is only set up for Ubuntu images. For non-Ubuntu images, you only get the PXE interface set up to do DHCP against MAAS. All other interfaces need to be configured manually after deployment.

You can choose an ephemeral OS deployment from the deployment configuration screen in the machine list: Just select the "Deploy in memory" option and deploy as normal.

#### New filters to support ephemeral deployments

You can now select two new filters for deployment targets: "Deployed in memory" and "Deployed to disk."

#### Machine release scripts

MAAS now supports machine release scripts -- scripts that will be run when releasing a machine from deployment.  These scripts run on an ephemeral copy of Ubuntu that is loaded after the deployed OS has been shut down.  This ephemeral Ubuntu is similar to the OS image used to commission machines.

Release scripts are the same type of scripts that you can create for commissioning or testing, with one difference: `script_type: release`.  Here's a sample release script:

```nohighlight
#!/usr/bin/env python3
#
# hello-maas - Simple release script.
#
# Copyright (C) 2016-2024 Canonical
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as
# published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
# --- Start MAAS 1.0 script metadata ---
# name: hello-maas
# title: Simple release script
# description: Simple release script
# script_type: release
# packages:
#   apt:
#     - moreutils
# --- End MAAS 1.0 script metadata --

import socket

host = '10.10.10.10'
port = 3333
s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s.connect((host, port))
s.sendall(b'Hello, MAAS')
s.close()
```

You can upload release scripts via API or CLI with a command similar to this one:

```nohighlight
maas $PROFILE node-scripts create type=release name='hello-maas' script@=/home/ubuntu/hello-maas.py
```

You can check your uploaded release scripts like this:

```nohighlight
maas $PROFILE node-scripts read type=release
```

Among listed scripts you might see one named `wipe-disks`. This is the script that comes with MAAS to support the *Disk Erase* functionality.

Once you have your script uploaded to MAAS, you can pass it as a parameter to the MAAS CLI:

```nohighlight
maas $PROFILE machine release $SYSTEM_ID scripts=hello-maas
```

You can inspect release script results via the MAAS CLI:

```nohighlight
maas $PROFILE node-script-results read $SYSTEM_ID type=release
```
 
#### Updates to the MAAS UI

- The header of the "Deploy" form now sticks to the top of the screen when you scroll down
- Added a message on empty tables across the UI
- Moved collapsible forms to side panels
- Improved UI performance by only fetching JavaScript code for pages when it's needed
- The width of the settings pages is now more consistent
- Improved the grouping of subnets
- Proxied the local documentation so it can be accessed from the UI
- Columns on the machine list will now adapt to the screen size, and hide if there's not  enough space
- Improved the side panel for managing tags
 -- Creating a new tag while applying tags to a machine now expands the side panel with the fields for the new tag
 -- Clicking a tag will expand the side panel to show information on that tag
- Pressing `/` on your keyboard will now automatically focus the search bar on pages that have one
- If an action fails, the reason for it is now shown in the error message (if applicable)
- Removed the footer from all pages, and moved the links to the status bar at the bottom
- Migrated the maas-ui tooling from "create-react-app" to Vite
 -- Less JavaScript code has to be fetched on the initial page load
 -- Increased performance of the development environment of the UI
 
#### "Agent" and "Temporal" controller services

MAAS 3.5 makes some internal changes to improve the operation of MAAS, including:

- adding a rack agent to assist the rack controller (this agent will eventually replace the rack controller).

- using a product called Temporal to improve process management and scheduling.

There are no exposed controls, and there is no need for users to take any action on these changes. You will, though, see two new services in *Controllers > <controller> > Services: "agent" and "temporal."

### UI bug fixes

- Images that are queued for download can now be deleted
- Improved alignment of headers in side panels
- Improved header spacing and form layouts across the UI
- Some errors that were appearing as JSON strings are now properly formatted
- Removed a typo on the machine network table's empty state
- Improved layout of login screen when a login error is shown
- IP range reservation on subnets now shows the correct error messages for start and end IPs
- Improved keyring data placeholder text on the "Change source" form in the Images page
- Image import can now be stopped in the UI
- Fixed label positioning for KVM CPU resources on smaller screens
- On mobile devices, the side navigation will now collapse after a link is tapped
- The "name" column on the partitions table will now re-enable after the "Create volume group" form is closed
- Adding an SSL key no longer shows a "Removed" message 
- Adding/editing a user no longer shows a "Deleted" message
- The "Change storage layout" form now has a correct title, and closes after submission
- Adding/editing an API key no longer shows a "Deleted" message
- Composing a VM will now immediately display the new VM in the list
- Reduced padding at the top of the settings pages
- Updating a tag will no longer show an "Error: Not found" screen
- Reduced the font size in the "Delete tag" form
- Improved accessibility in the MAAS intro pages
- The "Filters" dropdown is now disabled if there are no nodes to filter through
- Changed the Network Discovery URL from "dashboard" to "network-discovery"
- Machine status is visible again on machine summary pages
- The "Total VMs" button on a KVM host now links to the list of its VMs
- Clicking the logo in the top corner will now always navigate to the machine list, regardless of user role
- Machines are now sorted by their names in ascending alphabetical order by default
- The "Check power" action can now be accessed from the "Power" dropdown menu
- Confirming image import on the controller list will now close the side panel
- Improved performance of updating multiple settings
- The subnet table now automatically updates after adding a new subnet
- Fixed horizontal scroll bar on the Authentication section of the "Add LXD" form
- Full-screen "Error: the server connection failed" messages should now be much less frequent
- "Allocated" machines can no longer have their storage layout modified
- Fixed a nullable field error in the Windows image settings
- The side panel will now close automatically when navigating to a different page
- Fixed a full screen error message that would sometimes display on machine network and storage tabs
- The secondary side navigation will no longer display on the login screen
- Non-admin usernames are now displayed correctly in the side navigation
- Fixed table pagination in the "Add DHCP snippet" form
- Machine list pagination now displays the correct total number of pages
- Machine list filters are now properly synchronized with the URL
- Made the tool-tip message for "Automatically sync images" a bit more concise

### Back-end bug fixes
 - [2055009](https://bugs.launchpad.net/maas/+bug/2055009)**^** : Default zone can not be renamed
 - [2049508](https://bugs.launchpad.net/maas/+bug/2049508)**^** : MAAS has orphan ip addresses and dns records that are slowing down the entire service
 - [2054377](https://bugs.launchpad.net/maas/+bug/2054377)**^** : Temporal worker pool configuration failure
 - [2053033](https://bugs.launchpad.net/maas/+bug/2053033)**^** : Creating MAAS Virsh VM does not work (libvirt: error)
 - [2052958](https://bugs.launchpad.net/maas/+bug/2052958)**^** : PPC64 machines without disk serial fail condense LUNs
 - [2052503](https://bugs.launchpad.net/maas/+bug/2052503)**^** : Additional Power States in Redfish Schema
 - [2049626](https://bugs.launchpad.net/maas/+bug/2049626)**^** : Failed to update NTP configuration
 - [2044396](https://bugs.launchpad.net/maas/+bug/2044396)**^** : allow_dns accepts boolean instead of Int in the help
 - [2046255](https://bugs.launchpad.net/maas/+bug/2046255)**^** : For every interface MAAS is adding an A record for the name <machine>.<domain>
 - [2045228](https://bugs.launchpad.net/maas/+bug/2045228)**^** : DNS updates are consumed concurrently, leading to an incorrect nsupdate payload
 - [2042645](https://bugs.launchpad.net/maas/+bug/2042645)**^** : Power management using ProxMox is broken
 - [2040188](https://bugs.launchpad.net/maas/+bug/2040188)**^** : MAAS config option for IPMI cipher suite ID is not passed to bmc-config script
 - [2042540](https://bugs.launchpad.net/maas/+bug/2042540)**^** : Machine sometimes revert to old status after power control
 - [2041854](https://bugs.launchpad.net/maas/+bug/2041854)**^** : maas config-vault migrate failed due to region not restarting
 - [2039455](https://bugs.launchpad.net/maas/+bug/2039455)**^** : Temporal system status traceback
 - [2015411](https://bugs.launchpad.net/maas/+bug/2015411)**^** : StaticIPAddress matching query does not exist
 - [1923315](https://bugs.launchpad.net/maas/+bug/1923315)**^** : MaaS API ignores osystem and distro parameters
 - [1979058](https://bugs.launchpad.net/maas/+bug/1979058)**^** : "space" option still exists as available on Subnet API while being deprecated
 - [2036759](https://bugs.launchpad.net/maas/+bug/2036759)**^** : Adding a custom MAAS sstreams image source without trailing / fails
 - [2037420](https://bugs.launchpad.net/maas/+bug/2037420)**^** : MAAS metadata_url contains a domain name even when DNS resolution is disallowed
 - [2029417](https://bugs.launchpad.net/maas/+bug/2029417)**^** : RPC failure to contact rack/region - operations on closed handler
 - [1993916](https://bugs.launchpad.net/maas/+bug/1993916)**^** : ThinkSystem SR645 failed commissioning ERROR: Failed to commit `User3:Password': Invalid/Unsupported Config
 - [1999152](https://bugs.launchpad.net/maas/+bug/1999152)**^** : websocket API support for stop_mode
 - [2020397](https://bugs.launchpad.net/maas/+bug/2020397)**^** : Custom images which worked ok is not working with 3.2
 - [2019216](https://bugs.launchpad.net/maas/+bug/2019216)**^** : Flaky test- dhcp notify test_sends_notification_over_socket_for_processing
 - [2026283](https://bugs.launchpad.net/maas/+bug/2026283)**^** : TestDynamicDNSUpdate.test_as_reverse_record_update flaky test

## Version 3.4 release notes

This section recaps the release history of MAAS version 3.4.

### MAAS 3.4.6 has been released

We are happy to announce that MAAS 3.4.6 has been released, with the following bug fixes

- [2040324](https://bugs.launchpad.net/bugs/2040324)^: Power configuration change fails with <image> is not a valid distro series error
- [2055347](https://bugs.launchpad.net/bugs/2055347)^: MAAS IPMI k_g validation error
- [2058496](https://bugs.launchpad.net/bugs/2058496)^: Commissioning failed during 1st pxe install 24.04
- [2072155](https://bugs.launchpad.net/bugs/2072155)^: Discovered ip addresses mapped to an invalid name (ending with -)
- [2073501](https://bugs.launchpad.net/bugs/2073501)^: Bionic not available for commissioning on pro-enabled systems
- [2078810](https://bugs.launchpad.net/bugs/2078810)^: Can't filter by system id in the UI
- [2084788](https://bugs.launchpad.net/bugs/2084788)^: MAAS 3.5.1 machines staying forever at commissioning
- [2089185](https://bugs.launchpad.net/bugs/2089185)^: Releasing fails with latest cloud-init on image 20241113
- [2091370](https://bugs.launchpad.net/bugs/2091370)^: MAAS snap build pulls python modules from outside Ubuntu Archive / MAAS PPAs
- [2058063](https://bugs.launchpad.net/bugs/2058063)^: Controllers show different versions when installed with debs

### MAAS 3.4.5 has been released

We are happy to announce that MAAS 3.4.5 has been released, with the following bug fixes
- [2004661](https://bugs.launchpad.net/bugs/2004661)**^**: MAAS deployment failures on server with Redfish
- [2024242](https://bugs.launchpad.net/bugs/2024242)**^**: Unable to Deploy Machines; get() returned more than one Neighbour -- it returned 2!
- [2052503](https://bugs.launchpad.net/bugs/2052503)**^**: Additional Power States in Redfish Schema
- [2079797](https://bugs.launchpad.net/bugs/2079797)**^**: Redfish powerdriver should be able to handle the reset power status

### MAAS 3.4.4 has been released

We are happy to announce that MAAS 3.4.4 has been released, with the following bug fixes
- [2073731](https://bugs.launchpad.net/bugs/2073731)**^**: BMC commissioning error on HPE Gen 10 with ILO 5
- [1953049](https://bugs.launchpad.net/bugs/1953049)**^**: Error while calling ScanNetworks: Unable to get RPC connection for rack controller

### MAAS 3.4.3 has been released

We are happy to announce that MAAS 3.4.3 has been released, with the following bug fixes
- [2029522](https://bugs.launchpad.net/bugs/2029522)**^**: stacktrace on _reap_extra_connection()
- [2031482](https://bugs.launchpad.net/bugs/2031482)**^**: Subnet changed to wrong fabric, impacting DHCP
- [2066276](https://bugs.launchpad.net/bugs/2066276)**^**: IPv6 test failures: AttributeError: 'RRHeader' object has no attribute '_address'
- [2067998](https://bugs.launchpad.net/bugs/2067998)**^**: MAAS resets VLAN on interface if no link is detected during commissioning
- [2070304](https://bugs.launchpad.net/bugs/2070304)**^**: regiond at 100% CPU after UI reconnect causing API errors

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

### New capabilities in MAAS 3.4

MAAS 3.4 provides several new features.

#### Redesigned UI

The MAAS User Interface (UI) has undergone a significant redesign, introducing the MAAS UI new layout. This new layout incorporates various features and improvements aimed at enhancing the user experience for MAAS users and operators who primarily interact with the UI.  The MAAS UI new layout introduces several enhancements that aim to improve usability, customization, and navigation within the application

- Customized column visibility: One of the major improvements in the MAAS UI new layout is the ability for users to customize the visibility of columns on the machine list. This feature empowers users to focus on the specific information they need, while hiding irrelevant columns. By allowing users to tailor their view, this enhancement improves readability, reduces clutter, and provides a more personalized experience.

- Action forms in side panel: Previously, the action forms in MAAS were located in the header section, which made it less intuitive for users to access and interact with them. The redesigned UI moves these action forms to the side panel, providing a more logical placement and easy access to perform actions on machines. This change enhances the usability of the forms and improves the overall workflow for users.

- Streamlined action button group: The introduction of a new action button group eliminates the need for the previous "Take action" menu. Users can now directly access commonly used actions for machines, both in the details view and the machine list. This streamlines the workflow and simplifies the process of performing actions on machines, saving users time and effort.

- Improved side navigation: To enhance navigation within the application, the MAAS UI new layout implements a new side navigation system. Users can conveniently navigate through different sections of the app using the side panel. Additionally, the inclusion of a secondary side navigation specifically for settings and account pages improves the organization and accessibility of these sections.

##### Intended Benefits

The MAAS UI was redesigned with several user benefits in mind.

- Enhanced table interaction: Users can now customize their views by selecting the columns they care about the most. This modular table feature allows for a personalized experience, ensuring users can focus on the information that matters to them.

- Improved form interaction: Forms in the MAAS UI have been redesigned to scale with the content. By migrating all forms into panels, users have more space to view other components such as the machine list, resulting in a more comfortable and efficient form interaction experience.

- Efficient navigation: The new layout addresses the challenges posed by a growing navigation menu. With the introduction of the side panel navigation, users can easily explore different sections of the app, providing a scalable and user-friendly navigation experience.

- Enhanced search capability: The MAAS UI new layout improves the efficiency of the search feature. Users can search for machines based on conventions and tags, making it easier to find specific machines and take actions. The new layout also provides clearer feedback when the "take action" button is disabled, enhancing the overall search and interaction experience.

- Performance improvements based on user feedback: Based on user feedback received through Discourse, several performance issues have been identified and addressed. The MAAS team has worked diligently to optimize machine information loading times and resolve delays encountered while opening machine pages. These performance improvements ensure a smoother and faster user experience when interacting with the MAAS UI.

The MAAS UI new layout introduces a redesigned interface with enhanced features to provide a more efficient and user-friendly experience for MAAS users and operators. By allowing users to customize their views, streamlining form interactions

<!--
- DGX kernel support: There’s ongoing work from Canonical to provide an optimized kernel for Nvidia DGX machines. We want to promote that and make sure that DGX machines use that optimized kernel by default, without the user having to do any special configuration.
-->

#### Configurable session timeout

In MAAS 3.4, we've introduced the Configurable Session Timeout feature, offering better control over session length. This feature allows you to set a personalized duration for your sessions, hopefully avoiding abrupt disconnections or lingering sessions.  If you're a user who has login repeatedly, due to short session defaults, or you're concerned about leaving your session accessible for too long, setting a custom timeout is useful and potentially more secure.

#### Packer MAAS - SLES

The MAAS 3.4 release expands Packer support to include SUSE Linux Enterprise Server (SLES), expanding the the list of deployable Linux distributions.  We also support openSUSE and openSUSE Tumbleweed. And we’ve added a template for Red Hat Enterprise Linux (RHEL) version 9.

### Installation

MAAS will run on [just about any modern hardware configuration](/t/installation-requirements/6233).

- [How to do a fresh install of MAAS 3.4](/t/how-to-install-maas/5128): Use the tabs to select snaps or packages.

- [How to upgrade from an earlier version to MAAS 3.4](/t/how-to-upgrade-maas/5436): Use the tabs to select snaps or packages.

- [Initialize MAAS for a production configuration](/t/how-to-install-maas/5128#heading--init-maas-production)

### Bug fixes

<a href id="heading--3-4-1-bugs"> </a>

#### MAAS 3.4.1

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

#### MAAS 3.4.0

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