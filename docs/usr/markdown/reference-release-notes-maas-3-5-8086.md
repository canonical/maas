## Release history

This section recaps the release history of MAAS version 3.5.

### MAAS 3.5.4 has been released

We are happy to announce that MAAS 3.5.4 has been released, with the following bug fixes
- [2095477](https://bugs.launchpad.net/maas/+bug/2095477)**^**: boot-resources read is slow when there are a lot of images that have been deployed a lot of times
- [2092172](https://bugs.launchpad.net/bugs/2092172)**^**:  Redfish powerdriver I/O operation on closed file.
- [2099949](https://bugs.launchpad.net/bugs/2099949)**^**:  Redfish power driver requests fails with 412 status code 
- (No bug link) HW sync fails due to MAAS/metadata/2012-03-01 HTTP Error 409: Conflict.
- [2095019](https://bugs.launchpad.net/maas/+bug/2095019)**^**: read the global configurations disk_erase_with_secure_erase and disk_erase_with_quick_erase when releasing a machine
- [2091370](https://bugs.launchpad.net/maas/+bug/2091370)**^**: MAAS snap build pulls python modules from outside Ubuntu Archive / MAAS PPAs

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


MAAS 3.5 delivers substantial improvements in core functionality.  We've integrated Temporal for enhanced process and thread management, and started a transition to Go, re-implementing some of the rack controller functions as the "MAAS agent."  We've standardised logging and monitoring to use tools like syslogd, stepping away from the custom code we had been using.  We've also expanded the capabilities of existing features to include comprehensive service monitoring and support for deploying ephemeral (RAM-only) OS images.  And we've made great strides in visibly improving the performance of MAAS.

## Capabilities added in MAAS 3.5

### Faster and more efficient image storage and sync

MAAS previously stored the boot resources (boot-loaders, kernels and disk images) in the MAAS database, and then replicated them on all Rack controllers. This make operations difficult and slow, as the database quickly became huge and files had to be transferred to all Racks before they were available for use. To address this issue, we have moved the resource storage from the database to the Region controller, and repurposed the storage in the Rack.

#### Storing boot resources in the Region Controllers

All boot resources are stored in the local disk in each Controller host (`/var/lib/maas/image-storage` for *deb* or `$SNAP_COMMON/maas/image-storage` for *snap*). MAAS checks the contents of these directories on every start-up, removing unknown/stale files and downloading any missing resource. 

MAAS checks the amount of disk space available before downloading any resource, and stops synchronising files if there isn't enough free space. This error will be reported in the logs and a banner in the Web UI.

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

When downloading boot resources from an upstream source (e.g. images.maas.io), MAAS divides the workload between all Region controllers available, so each file is downloaded only once, but not all by the same controller. After all external files were fetched, the controllers synchronise files among them in a peer-to-peer fashion. This requires **direct communication between Regions to be allowed**, so you should review your firewall rules before upgrading.

In this new model, a given image is *only* available for deployment after *all* regions have it, although stale versions can be used until everyone is up to date. This differs from previous versions where the boot resource needed to be copied to all Rack controllers before it was available, meaning that the images should be ready for use sooner.

### Faster machine listing when deploying many machines

We have made the MAAS machine listing considerably faster for large page sizes.

### Soft Power Off

MAAS 3.5 allows you to execute a "soft" power-off for one or more machines.  Rather than commanding a power-off via the BMC, MAAS will ask the running OS to power-down the machine.  This allows machines to go through their normal shutdown routines before powering off.

### Improved "Select All" in the machine list

With MAAS 3.5, you can select only the machines that are visible on the current page. 

### Improved support for multipath storage devices

MAAS support of multipath storage devices has been reviewed and improved, and now it's capable of correctly identifying the following technologies:

* SCSI
* iSCSI
* Fiber Channel
* SAS (including wide port and expanders)

When one of these devices is detected by the commissioning scripts, MAAS will suppress the duplicated disks.

### MAAS services exposed as Prometheus metrics

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

### Logs collapsed into system log files

With the advent of 3.5, all of the separate logs used by MAAS through version 3.4 have been eliminated and replaced with logging into the standard `systemd` files.  See [How to use MAAS systemd logs](/t/how-to-use-maas-systemd-logs/8103) in the documentation set for details.

### Deployment of Oracle Linux 8 and 9 on MAAS machines

Concurrent with the release of MAAS 3.5, we have added Oracle Linux 8 and Oracle Linux 9 to the stable of custom OS images that can be deployed on MAAS machines.

### Ephemeral OS deployments

With the release of MAAS 3.5, ephemeral deployments for Ubuntu and custom images should succeed.  Networking is only set up for Ubuntu images. For non-Ubuntu images, you only get the PXE interface set up to do DHCP against MAAS. All other interfaces need to be configured manually after deployment.

You can choose an ephemeral OS deployment from the deployment configuration screen in the machine list: Just select the "Deploy in memory" option and deploy as normal.

#### New filters to support ephemeral deployments

You can now select two new filters for deployment targets: "Deployed in memory" and "Deployed to disk."

### Machine release scripts

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
 
## Updates to the MAAS UI

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
 
### "Agent" and "Temporal" controller services

MAAS 3.5 makes some internal changes to improve the operation of MAAS, including:

- adding a rack agent to assist the rack controller (this agent will eventually replace the rack controller).

- using a product called Temporal to improve process management and scheduling.

There are no exposed controls, and there is no need for users to take any action on these changes. You will, though, see two new services in *Controllers > <controller> > Services: "agent" and "temporal."

## UI bug fixes

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
- Machine list filters are now properly synchronised with the URL
- Made the tool-tip message for "Automatically sync images" a bit more concise

## Back-end bug fixes
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
