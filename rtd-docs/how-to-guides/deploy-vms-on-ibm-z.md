# Deploy VMs on IBM Z

You can deploy virtual machines on the IBM Z series with MAAS version 3.0 or higher.

The IBM Z or LinuxONE system can host MAAS controllers and is able to deploy predefined logical partitions (LPARs) KVM host(s), and virtual machines, if the mainframe is set up properly for MAAS.

The basic architecture is similar to this:

![image](/images/ibmz/basic-architecture.webp)

Networking would be structured like this:

![image](/images/ibmz/networking.webp)

Note that net-booting the KVM guests (through the two bridges) can be problematic. There are two options:

1. Adding VNIC characteristics to enable "learning" on the network interface that's the base for bridge "br2."  This is the recommended approach.

2. Enable full promiscuous bridge port mode at the network interface that's the base for bridge "br2."  This approach is not recommended because it has some built-in limitations.

MAAS will automatically configure option 1 for you, in case an LPAR is deployed as KVM host (the bridge names may differ).

The MAAS controller does not necessarily need to run on an LPAR on the IBM Z system itself, but can also run on a different system outside. But since the MAAS controller requires a network connection to the hardware management console (HMC), it is recommended to keep it co-located and (for security reasons) as close as possible to the HMC and run it in a dedicated LPAR.

Such a MAAS controller LPAR should have at least two SMT hardware threads (one IFL), since it runs several services (bind, rack-, region-controller and more), 16 GB RAM and 100 GB disk space - recommended is to use the double amount of these resources.

The resources of the LPARs to deploy on ('machines' in terms of MAAS) depending on the use case. LPARs that are deployed as KVM host would of course require significantly more resources to be able to host KVM guest on top.

There are several constraints on the definition and setup of the 'machine' LPARs - please see below.

## Evaluate IBM Z requirements

The system requirements to host MAAS and its virtual machines on the IBM Z platform are as follows:

- IBM z14 GA2 (or newer) or IBM LinuxONE III (or newer)
- HMC running in DPM mode (mandatory, traditional mode is not supported!)
- HMC firmware level H39 - (HMC at H40 and SE at S55)
- HMCs Rest-API enabled
- python-zhmcclient (0.29 or later) running on the MAAS controller system, connected to the HMC
- HMC user ID for the zhmcclient access to the HMC API (must have permissions for the “Manage Web Services API Logs” role and “Manage Web Services API Logs” role)
- I/O auto-configuration enabled for the ‘machine’ LPARs
- zFCP (SCSI) disk storage (only, no DASD support), recommended are two disks, one defined as type ‘boot,’ the second as type ‘data’
- a dedicated storage group per ‘machine’ LPAR; these must include the dedicated zFCP storage for this particular managed LPAR only (‘boot’ and ‘data’ for LPAR n) - but no additional shared storage!
- qeth network devices (Hipersockets or OSA, recommended); at least one qeth NIC, recommended two (or more)
- Ubuntu Server 20.04 installed on a dedicated system (LPAR or PC), that acts as MAAS Controller
- one or more LPARs as ‘machines’ (aka MAAS deployment targets)

Be aware that these are minimum system requirements.

## Access the HMC and login to the IBM Z

To login to the HMC, you must have at least “system programmer” privileges. Gaining that level of access is beyond the scope of this document. Once you are sure that you have the necessary access, you first need to navigate to the Hardware Management Console (HMC) application in your Web browser:

![image](/images/ibmz/hmc.webp)

Click on the "Log on..." link, which will bring you to a login screen:

![image](/images/ibmz/logon.webp)

Upon successfully logging on, you will land on the Welcome Screen:

![image](/images/ibmz/welcome-screen.webp)

Select the "Tasks Index" on the left-hand navigation:

![image](/images/ibmz/left-hand-navigation.webp)

From here, you will be able to access the commands needed to prepare your IBM Z to host MAAS.

## Set up a suitable IBM Z partition for a MAAS machine

In order to prevent MAAS from taking over the entire system, you must assign both the controller and the ‘machines’ / KVM hosts to specific partitions, with suitable limitations. To set up suitable IBM Z partitions for hosting MAAS, you must choose “Partition Details” from the “Tasks Index,” which will bring you to a screen like this one:

![image](/images/ibmz/partition-details-object-selection.webp)

You must then choose the “target object” (in this case we’ve chosen TA05) to be operated upon:

![image](/images/ibmz/target-object.webp)

Click “OK,” and you’ll arrive at a screen similar to the one below:

![image](/images/ibmz/systems-management.webp)

Make sure you’re on the “Partitions” tab, and select the desired object (“TA05…”):

![image](/images/ibmz/partition-tab-target-object.webp)

Right-click on the selected object and select “Partition Details:”

![image](/images/ibmz/partition-details.webp)

On the “General” tab, edit the partition details to suit your proposed MAAS deployment:

![image](/images/ibmz/partition-details-editing.webp)

Next, you will set up the networking details for this partition, as shown in the following section.

## Set up IBM Z networking for a MAAS machine

To properly enable networking within the IBMZ partitions, you must change to the “Network” tab under “Partition Details:”

![image](/images/ibmz/partition-details-network.webp)

Click on the NIC of interest to bring up the “NIC Details” screen:

![image](/images/ibmz/nic-details.webp)

Confirm that the parameters on this screen are consistent with your planned MAAS deployment, then bring up the network adaptor(either OSA or Hipersockets) by selecting it:

![image](/images/ibmz/network-adapter.webp)

Ensure that all settings on the “General” tab conform to your planned MAAS deployment; then select the “Network Interface Cards” tab on the left-hand navigation:

![image](/images/ibmz/network-adapter.webp)

Again, ensure that the parameters associated with the networking arrangement are consistent with your planned MAAS deployment.

Next, you will set up the storage layout for your MAAS partition(s).

## Set up IBM Z storage for a MAAS machine

To set up suitable storage for a MAAS deployment, you should bring up the “Partition Details” for your chosen MAAS partition and select the “Storage” tab from the left-hand navigation:

![image](/images/ibmz/partition-details-storage.webp)

Choose the “VOLUMES” sub-tab, and lick on the hyperlinked partition name to bring up the storage configuration tab:

![image](/images/ibmz/volume.webp)

Click on “GET DETAILS” for the Boot Volume in the Volume list to bring up the “Configuration details” screen:

![image](/images/ibmz/volume-configuration-details.webp)

Ensure that the Boot Volume is configured appropriately for your planned MAAS deployment, then click “Done.” Then return to the storage configuration tab and choose the Data Volume, and tune it to the appropriate parameters.

Next, choose the “ADAPTERS” sub-tab to bring up information on the storage adaptors:

![image](/images/ibmz/storage-adapters.webp)

Set any necessary parameters to conform to your planned MAAS deployment.

## Set the partition boot parameters

Return to the “Partition Details” screen and select the “Boot” tab in the left-hand navigation:

![image](/images/ibmz/boot.webp)

Change any settings as necessary to support your planned MAAS deployment.

## Set up your IBM Z virtual machine for enlistment

To cause IBM Z KVM partition guests to enlist, it’s necessary to manually put in the BMC information for each guest. MAAS can then detect the guest, enlist it, and boot it as necessary.
