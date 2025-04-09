This page explains how to deploy virtual machines on the IBM Z series.

*MAAS 2.9 does not support IBM Z*

The IBM Z or LinuxONE system can host MAAS controllers and is able to deploy predefined logical partitions (LPARs) KVM host(s), and virtual machines, if the mainframe is set up properly for MAAS.

The basic architecture is similar to this:

![image](https://discourse-maas-io-uploads.s3.us-east-1.amazonaws.com/original/2X/d/d78aec0bd5d5f485697701ed7316944f918fef94.png)

Networking would be structured like this:

![image](https://discourse-maas-io-uploads.s3.us-east-1.amazonaws.com/original/2X/8/841305949182ba64037f9806396a0e60fdc46d23.png)

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

![image](https://discourse-maas-io-uploads.s3.us-east-1.amazonaws.com/original/2X/d/d085c8113e403546484778c858c27344e8986597.png)

Click on the "Log on..." link, which will bring you to a login screen:

![image](https://discourse-maas-io-uploads.s3.us-east-1.amazonaws.com/original/2X/5/5ccdfac4dc985260dcedd01284d24c5e8e5199d9.png)

Upon successfully logging on, you will land on the Welcome Screen:

![image](https://discourse-maas-io-uploads.s3.us-east-1.amazonaws.com/original/2X/d/d18afe140a1971621ed44fa5fae36033927e293e.png)

Select the "Tasks Index" on the left-hand navigation:

![image](https://discourse-maas-io-uploads.s3.us-east-1.amazonaws.com/original/2X/c/c030c8280b0a6dcfdd0365f9cf50238ae708e34b.jpeg)

From here, you will be able to access the commands needed to prepare your IBM Z to host MAAS.

## Set up a suitable IBM Z partition for a MAAS machine

In order to prevent MAAS from taking over the entire system, you must assign both the controller and the ‘machines’ / KVM hosts to specific partitions, with suitable limitations. To set up suitable IBM Z partitions for hosting MAAS, you must choose “Partition Details” from the “Tasks Index,” which will bring you to a screen like this one:

![image](https://discourse-maas-io-uploads.s3.us-east-1.amazonaws.com/original/2X/2/29e0cc00d68a5add1b13b1d50313ff6966f251a9.png)

You must then choose the “target object” (in this case we’ve chosen TA05) to be operated upon:

![image](https://discourse-maas-io-uploads.s3.us-east-1.amazonaws.com/original/2X/7/754c4926ecf5d9330b60c9b58bdd15bde6f24144.png)

Click “OK,” and you’ll arrive at a screen similar to the one below:

![image](https://discourse-maas-io-uploads.s3.us-east-1.amazonaws.com/original/2X/0/0ecf9bd89c132fd2c7ff8b879dd6c1b4d3090a99.png)

Make sure you’re on the “Partitions” tab, and select the desired object (“TA05…”):

![image](https://discourse-maas-io-uploads.s3.us-east-1.amazonaws.com/original/2X/0/018d8309a1a16571df56a6672cff26e60f42075a.jpeg)

Right-click on the selected object and select “Partition Details:”

![image](https://discourse-maas-io-uploads.s3.us-east-1.amazonaws.com/original/2X/5/5a7f696435b504eb212234acdd09c928f16b1670.jpeg)

On the “General” tab, edit the partition details to suit your proposed MAAS deployment:

![image](https://discourse-maas-io-uploads.s3.us-east-1.amazonaws.com/original/2X/6/60ff5ca98d8b615ee4a947607872c973cf2c7f41.png)


Next, you will set up the networking details for this partition, as shown in the following section.

## Set up IBM Z networking for a MAAS machine

To properly enable networking within the IBMZ partitions, you must change to the “Network” tab under “Partition Details:”

![image](https://discourse-maas-io-uploads.s3.us-east-1.amazonaws.com/original/2X/d/daf386497781df42ba7ffaa518c1f186ebef66ee.png)

Click on the NIC of interest to bring up the “NIC Details” screen:

![image](https://discourse-maas-io-uploads.s3.us-east-1.amazonaws.com/original/2X/e/e9b65711cf97dd722db1b1df4b69d4f590166a99.png)

Confirm that the parameters on this screen are consistent with your planned MAAS deployment, then bring up the network adaptor(either OSA or Hipersockets) by selecting it:

![image](https://discourse-maas-io-uploads.s3.us-east-1.amazonaws.com/original/2X/0/0a0873d7cd40147884c861d1fcde15ddc37c8853.png)

Ensure that all settings on the “General” tab conform to your planned MAAS deployment; then select the “Network Interface Cards” tab on the left-hand navigation:

![image](https://discourse-maas-io-uploads.s3.us-east-1.amazonaws.com/original/2X/0/0a0873d7cd40147884c861d1fcde15ddc37c8853.png)


Again, ensure that the parameters associated with the networking arrangement are consistent with your planned MAAS deployment.

Next, you will set up the storage layout for your MAAS partition(s).

## Set up IBM Z storage for a MAAS machine

To set up suitable storage for a MAAS deployment, you should bring up the “Partition Details” for your chosen MAAS partition and select the “Storage” tab from the left-hand navigation:

![image](https://discourse-maas-io-uploads.s3.us-east-1.amazonaws.com/original/2X/c/c25792eeacd5aef57ca74a68b203c23ed74268d7.png)

Choose the “VOLUMES” sub-tab, and lick on the hyperlinked partition name to bring up the storage configuration tab:

![image](https://discourse-maas-io-uploads.s3.us-east-1.amazonaws.com/original/2X/c/cf8d1427abda94ccd3b79966d06bee210ac1240b.png)

Click on “GET DETAILS” for the Boot Volume in the Volume list to bring up the “Configuration details” screen:

![image](https://discourse-maas-io-uploads.s3.us-east-1.amazonaws.com/original/2X/a/a081c97b8196e708495156187b983b70c32fcdc5.png)

Ensure that the Boot Volume is configured appropriately for your planned MAAS deployment, then click “Done.” Then return to the storage configuration tab and choose the Data Volume, and tune it to the appropriate parameters.

Next, choose the “ADAPTERS” sub-tab to bring up information on the storage adaptors:

![image](https://discourse-maas-io-uploads.s3.us-east-1.amazonaws.com/original/2X/8/821edff17e3fe8f2fbf9b5cb1682928dc9bb34d7.png)

Set any necessary parameters to conform to your planned MAAS deployment.

## Set the partition boot parameters

Return to the “Partition Details” screen and select the “Boot” tab in the left-hand navigation:

![image](https://discourse-maas-io-uploads.s3.us-east-1.amazonaws.com/original/2X/c/c5df4937135c1a9a1758b20855742bd038700c65.png)

Change any settings as necessary to support your planned MAAS deployment.

## Set up your IBM Z virtual machine for enlistment

To cause IBM Z KVM partition guests to enlist, it’s necessary to manually put in the BMC information for each guest. MAAS can then detect the guest, enlist it, and boot it as necessary.
