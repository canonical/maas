> *Errors or typos? Topics missing? Hard to read? <a href="https://docs.google.com/forms/d/e/1FAIpQLScIt3ffetkaKW3gDv6FDk7CfUTNYP_HGmqQotSTtj2htKkVBw/viewform?usp=pp_url&entry.1739714854=https://maas.io/docs/machines" target = "_blank">Let us know.</a>*

Machines are the heart of MAAS.  This page offers a detailed explanation of machines and how they interact with MAAS.

## Machine list (UI) 

The machine list is a valuable dashboard for many MAAS operations. In the illustration below, you see the machine list for a typical small hospital data centre, including servers ready and allocated for functions like Pharmacy, Orders, Charts, and so on:

![image](https://discourse-maas-io-uploads.s3.us-east-1.amazonaws.com/original/1X/30df04b0bcec5fcf6538590ed795cb0514a64675.jpeg)

Rolling the cursor over status icons often reveals more details. For example, a failed hardware test script will place a warning icon alongside the hardware type tested by the script. Rolling the cursor over this will reveal which test failed. Likewise, you can find some immediate options by rolling over the column data items in the machines table.

![image](https://discourse-maas-io-uploads.s3.us-east-1.amazonaws.com/original/1X/8f78a8877a029e7a44bcd4cf3d138499637fe790.jpeg)

The 'Add hardware' drop-down menu is used to add either new machines or a new chassis. This menu changes context when one or more machines are selected from the table, using either the individual check-boxes in the first column or the column title checkbox to select all.

![image](https://discourse-maas-io-uploads.s3.us-east-1.amazonaws.com/original/1X/9a0747649e6aff999d3c04335eb752accedaf3de.jpeg)

With one or more machines selected, the 'Add hardware' drop-down menu moves to the left, and is joined by the 'Take action' menu. This menu provides access to the various [machine actions](/t/reference-maas-glossary/5416):

![image](https://discourse-maas-io-uploads.s3.us-east-1.amazonaws.com/original/1X/e03d5ac8de9ea4f4827ed057bb2dd83e241aac3b.jpeg)

> The 'Filter by' section limits the machines listed in the table to selected keywords and machine attributes.

## jq dashboard (CLI)

You can also create a non-interactive dashboard using the CLI and `jq`:

```nohighlight
FQDN               POWER  STATUS     OWNER  TAGS     POOL       NOTE     ZONE
----               -----  ------     -----  ----     ----       ----     ----
52-54-00-15-36-f2  off    Ready      -      Orders   Prescrbr   @md-all  Medications
52-54-00-17-64-c8  off    Ready      -      HRMgmt   StaffComp  @tmclck  Payroll
52-54-00-1d-47-95  off    Ready      -      MedSupp  SuppServ   @storag  Inventory
52-54-00-1e-06-41  off    Ready      -      PatPrtl  BusOfc     @bzstns  BizOffice
52-54-00-1e-a5-7e  off    Ready      -      Pharm    Prescrbr   @rxonly  Pharmacy
52-54-00-2e-b7-1e  off    Allocated  admin  NursOrd  NurServ    @nstns   Nursing
52-54-00-2e-c4-40  off    Allocated  admin  MedAdmn  NurServ    @rxonly  Nursing
52-54-00-2e-ee-17  off    Deployed   admin  Charts   ProServ    @md-all  Physician
```

You can generate this view with the command:

```nohighlight
maas admin machines read | jq -r '(["FQDN","POWER","STATUS",
"OWNER", "TAGS", "POOL", "NOTE", "ZONE"] | (., map(length*"-"))),
(.[] | [.hostname, .power_state, .status_name, .owner // "-", 
.tag_names[0] // "-", .pool.name, .description // "-", .zone.name]) | @tsv' | column -t
```

These example machines would typically be duplicated in several different geographies, with a quick way to switch to a redundant node, should anything go wrong (e.g., high availability). We used the word node there because, In the network language of MAAS, machines are one of several different types of nodes. A node is simply a network-connected object or, more specifically, an object that can independently communicate on a network. MAAS nodes include controllers, network devices, and of course, machines.

Looking back at the example above, you can see that there are several columns in the machine list, depending on your view:

- **FQDN | MAC**: The fully qualified domain name or the MAC address of the machine.
- **Power**: 'On', 'Off' or 'Error' to highlight an error state.
- **Status**: The current status of the machine, such as 'Ready', 'Commissioning' or 'Failed testing'.
- **Owner**: The MAAS account responsible for the machine.
- **Cores**: The number of CPU cores detected on the machine.
- **RAM**: The amount of RAM, in GiB, discovered on the machine.
- **Disks**: The number of drives detected on the machine.
- **Storage**: The amount of storage, in GB, identified on the machine.

## Machine summary 

Click a machine's FQDN or MAC address to open a detailed view of a machine's status and configuration.

![image](https://discourse-maas-io-uploads.s3.us-east-1.amazonaws.com/original/2X/a/a8ff4caf6362a3d695682499a74d64cb189dfc37.png)

The default view is 'Machine summary', presented as a series of cards detailing the CPU, memory, storage and tag characteristics of the machine, as well as an overview of its current status. When relevant, 'Edit' links take you directly to the settings pane for the configuration referenced within the card. The machine menu bar within the web UI also includes links to logs, events, and configuration options:

![image](https://discourse-maas-io-uploads.s3.us-east-1.amazonaws.com/original/2X/2/21e9f4dca3a3e0a6657b5b2a570c9fc68a3e4961.png)

The machine status card presents an overview of CPU, memory, storage, tags, and general settings:

![image](https://discourse-maas-io-uploads.s3.us-east-1.amazonaws.com/original/2X/a/a8ff4caf6362a3d695682499a74d64cb189dfc37.png)

The first card presents some basics of the machine resources and configuration:

![image](https://discourse-maas-io-uploads.s3.us-east-1.amazonaws.com/original/1X/3e50fb21f4985db0a85519e2e933e24658770b9e.jpeg)

Here are some details on what this card presents, with details on in-card links described in following sections:

- **OVERVIEW** the machine status (in this case "Deployed"), and lists OS version information. 

- **CPU** shows the specifics of the CPU(s), including a link to test the processor(s).

- **MEMORY** gives the total available RAM for this machine, along with a test link.

- **STORAGE** presents the total amount of storage available and the number of disks that provide that storage. There are two links here: one gives the storage layout (with the opportunity to change it for devices that are in 'Ready' or 'Allocated' states.

- **Owner** identifies the owner of the machine.

- **Domain** indicates the domain in which the machine exists.

- **Zone** shows the AZ in which this machine resides, along with a link to edit the machine configuration (to change the AZ, if desired).

- **Resource pool** shows the pool to which this machine has been assigned, and an edit link.

- **Power type** gives the current power type, which links to the relevant edit form.

- **Tags** presents the list of tags associated with this machine, editable via the link.

Note that clicking any of the links in this card will either present a pop-up form or take you to another item in the machine menu -- so using the browser "back" button will take you completely away from this machine's page. For example, you can choose the "Test CPU" option, which brings up this overlay:

![image](https://discourse-maas-io-uploads.s3.us-east-1.amazonaws.com/original/2X/6/6d7fe50e5b296a37a03269a1f5be3d25a2a2481a.png)

From this screen, you can choose test scripts and run the tests (in the background) as the interface returns to the Machine summary. A linked note in the CPU block lets you know that the tests are in progress:

![image](https://discourse-maas-io-uploads.s3.us-east-1.amazonaws.com/original/2X/3/3e140872c407e5b9eb06960b5b42353765567192.png) 

And you can watch the results under the "Tests" option in the Machine menu:

![image](https://discourse-maas-io-uploads.s3.us-east-1.amazonaws.com/original/2X/f/f398c9ed670af8c0886ccc1ed8bf586e3faf1e53.png) 

The rest of the cards on the Machine summary are either self-explanatory, or they're covered in the sections below. The main point is this: You can see that nearly everything about machines takes place within the main menu's "Machines" option. 

## USB/PCI (3.0++)

The machines in your MAAS may have devices attached to them via USB or PCI interface, such as keyboards, cameras, network cards, GPUs, etc. MAAS will recognise these devices and make them visible to you when a machine is commissioned.

For example, the machine details presents USB and PCI devices like this:

![image](https://discourse-maas-io-uploads.s3.us-east-1.amazonaws.com/original/2X/8/87f42bafe321d45af94d73216f933a9067f01df2.png)

Note that this page now includes two new tabs: "PCI devices" and "USB."  For each USB/PCI device attached to your machine, these tabs will list:

- device type
- vendor ID
- a product description
- a product ID
- the driver name
- the containing NUMA node (if any)
- the device address

A typical PCI device tab would look something like this:

![image](https://discourse-maas-io-uploads.s3.us-east-1.amazonaws.com/original/2X/8/82e1e6f8bc511047ac5f773430f7e5812c7a24d4.png)

The USB tab presents similar information in the same format.


If you are upgrading from a previous version of MAAS, PCI and USB devices aren't modelled, so you will have to recommission the machine to capture these devices.



Once you've commissioned the machine, you have the option of deleting
PCI/USB devices from the machine in any machine state, via the CLI
only, using the following command:

```nohighlight
maas $PROFILE node-device delete $SYSTEM_ID $DEVICE_ID
```

where:

- $PROFILE   = your user profile (e.g., "admin")
- $SYSTEM_ID = the ID of the machine in question (e.g., "ngx7ry")
- $DEVICE_ID = the ID of the device you want to delete 

If the device is still present in the system, it will be recognised again (and thus "re-created")
when the machine is commissioned again.


## Network states

The Network "tab" provides you with a way to view/edit the network and interface configuration for a machine: 

![image](https://discourse-maas-io-uploads.s3.us-east-1.amazonaws.com/original/2X/c/c5316db130ae05a9cdabcd49ffaa69f0bb405d1d.png) 

In the case of this deployed machine, there are not many editing options. If the machine is in a 'Ready' state, though, altering the network configuration is possible, as shown in the screenshot above.

Options on this tab are described in the introduction to [Networking](/t/about-maas-networks/5084) article in this documentation set.

## Booting

The final tab from the Machine menu allows you to update machine and power configuration options: 

![image](https://discourse-maas-io-uploads.s3.us-east-1.amazonaws.com/original/2X/7/7cfd77228a5cf1a6f779897d501f14fbf78fd4b4.png) 

There are two sections to this tab. The "Machine configuration" section, shown above, offers some general parameters, mostly related to how this machine is grouped and categorised. More information on these options are found in the relevant sections of the documentation (e.g., tags, resource pools, and so forth). 

The "Power configuration" supplies the parameters necessary for MAAS to access the machine to PXE-boot it: 

![image](https://discourse-maas-io-uploads.s3.us-east-1.amazonaws.com/original/2X/1/198898362285e4a1308535a4aa701156a67c9616.png) 

More information on Power configuration will be found in the [Power management](/t/how-to-set-up-power-drivers/5246) section of this documentation.


## Hard power-off

At any time, you can power off a machine from the MAAS UI or CLI.  This is a "hard" power-off, that is, power to the machine is interrupted without shutting down the OS that may be running at the moment.

## Soft power-off (3.5 UI only)

Beginning with MAAS 3.5, you can command a "soft" power-off via the MAAS UI.  This instructs the deployed machine to shut down gracefully by stopping the running OS through normal shutdown procedures.

## Storage

You have significant latitude when choosing the final storage configuration of a deployed machine. MAAS supports traditional disk partitioning, as well as more complex options such as LVM, RAID, and bcache. MAAS also supports UEFI as a boot mechanism. This article explains boot mechanisms and layouts, and offers some advice on how to configure layouts and manage storage.


MAAS doesn’t currently support deploying with ZFS for devices other than the root one. For this reason, ZFS is not recommended.


A machine's storage is dependant upon the underlying system's disks, but its configuration (i.e., disk usage) is the result of a storage template. In MAAS, this template is called a layout, and MAAS applies it to a machine during commissioning. Once a layout is applied, a regular user can make modifications to a machine at the filesystem level to arrive at the machine's final storage configuration. When a machine is no longer needed, a user can choose from among several disk erasure types before releasing it.


MAAS supports storage configuration for CentOS and RHEL deployments. Support includes RAID, LVM, and custom partitioning with different file systems (ZFS and bcache excluded). This support requires a newer version of Curtin, [available as a PPA](https://launchpad.net/ubuntu/+source/curtin)**^**.


## Resource pools

Resource pools allow administrators to logically group resources -- machines and VM hosts -- into pools. Pools can help you budget machines for a particular set of functions. For example, if you're using MAAS to manage a hospital data centre, you may want to keep a certain number of machines reserved for provider use, whether that be for the charts, documentation, or orders application. You can use resource pools to reserve those machines, regardless of which of the three applications you end up loading onto a particular machine at any given time. 

## Tags

Tags are short, descriptive, searchable words that can be applied to various MAAS objects, including:

- machines (physical and virtual)
- VM hosts
- controllers (rack and region)
- storage (virtual and physical; block devices or partitions)
- network interfaces
- devices
- nodes (in the CLI only)

Tags serve to help you identify, group, and find objects easily, especially when you routinely deploy hundreds of machines.

## Annotations

Annotations are descriptive, searchable phrases that apply only to machines. There are two types of annotations: static (always present in any machine state), and dynamic (only present in allocated or deployed states). Annotations help you identify, characterise, and inform others about your machines.