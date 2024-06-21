> *Errors or typos? Topics missing? Hard to read? <a href="https://docs.google.com/forms/d/e/1FAIpQLScIt3ffetkaKW3gDv6FDk7CfUTNYP_HGmqQotSTtj2htKkVBw/viewform?usp=pp_url&entry.1739714854=https://maas.io/docs/interpreting-testing-logs" target = "_blank">Let us know.</a>*

This page explains how to interpret MAAS test logs.

## `smartctl-validate`

Provided by Canonical, `smartctl-validate` uses the [smartmontools](https://www.smartmontools.org) kit to ensure your disk's integrity. A successful run looks something like this:

```nohighlight
INFO: Verifying SMART support for the following drive: /dev/sda
INFO: Running command: sudo -n smartctl --all /dev/sda
INFO: SMART support is available; continuing...
INFO: Verifying SMART data on /dev/sda
INFO: Running command: sudo -n smartctl --xall /dev/sda
SUCCESS: SMART validation has PASSED for: /dev/sda
--------------------------------------------------------------------------------
smartctl 6.6 2016-05-31 r4324 [x86_64-linux-4.15.0-115-generic] (local build)
Copyright (C) 2002-16, Bruce Allen, Christian Franke, www.smartmontools.org

=== START OF INFORMATION SECTION ===
Device Model:     QEMU HARDDISK
Serial Number:    QM00001
Firmware Version: 2.5+
User Capacity:    5,368,709,120 bytes [5.36 GB]
Sector Size:      512 bytes logical/physical
Device is:        Not in smartctl database [for details use: -P showall]
ATA Version is:   ATA/ATAPI-7, ATA/ATAPI-5 published, ANSI NCITS 340-2000
Local Time is:    Wed Sep  2 22:29:12 2020 UTC
SMART support is: Available - device has SMART capability.
SMART support is: Enabled
AAM feature is:   Unavailable
APM feature is:   Unavailable
Rd look-ahead is: Unavailable
Write cache is:   Enabled
ATA Security is:  Unavailable
Wt Cache Reorder: Unavailable

=== START OF READ SMART DATA SECTION ===
SMART overall-health self-assessment test result: PASSED

General SMART Values:
Offline data collection status:  (0x82)	Offline data collection activity
					was completed without error.
					Auto Offline Data Collection: Enabled.
Self-test execution status:      (   0)	The previous self-test routine completed
					without error or no self-test has ever 
					been run.
Total time to complete Offline 
data collection: 		(  288) seconds.
Offline data collection
capabilities: 			 (0x19) SMART execute Offline immediate.
					No Auto Offline data collection support.
					Suspend Offline collection upon new
					command.
					Offline surface scan supported.
					Self-test supported.
					No Conveyance Self-test supported.
					No Selective Self-test supported.
SMART capabilities:            (0x0003)	Saves SMART data before entering
					power-saving mode.
					Supports SMART auto save timer.
Error logging capability:        (0x01)	Error logging supported.
					No General Purpose Logging support.
Short self-test routine 
recommended polling time: 	 (   2) minutes.
Extended self-test routine
recommended polling time: 	 (  54) minutes.

SMART Attributes Data Structure revision number: 1
Vendor Specific SMART Attributes with Thresholds:
ID# ATTRIBUTE_NAME          FLAGS    VALUE WORST THRESH FAIL RAW_VALUE
  1 Raw_Read_Error_Rate     PO----   100   100   006    -    0
  3 Spin_Up_Time            PO----   100   100   000    -    16
  4 Start_Stop_Count        -O----   100   100   020    -    100
  5 Reallocated_Sector_Ct   PO----   100   100   036    -    0
  9 Power_On_Hours          PO----   100   100   000    -    1
 12 Power_Cycle_Count       PO----   100   100   000    -    0
190 Airflow_Temperature_Cel PO----   069   069   050    -    31 (Min/Max 31/31)
                            ||||||_ K auto-keep
                            |||||__ C event count
                            ||||___ R error rate
                            |||____ S speed/performance
                            ||_____ O updated online
                            |______ P prefailure warning

Read SMART Log Directory failed: scsi error badly formed scsi parameters

General Purpose Log Directory not supported

SMART Extended Comprehensive Error Log (GP Log 0x03) not supported

SMART Error Log Version: 1
No Errors Logged

SMART Extended Self-test Log (GP Log 0x07) not supported

SMART Self-test log structure revision number 1
No self-tests have been logged. [To run self-tests, use: smartctl -t]

Selective Self-tests/Logging not supported

SCT Commands not supported

Device Statistics (GP/SMART Log 0x04) not supported

SATA Phy Event Counters (GP Log 0x11) not supported
```

## `smartctl` output

The `smartctl` output can be dense, so let's decode each section.

### *Header*

```nohighlight
smartctl 6.6 2016-05-31 r4324 [x86_64-linux-4.15.0-115-generic] (local build)
Copyright (C) 2002-16, Bruce Allen, Christian Franke, www.smartmontools.org
```

This part provides metadata about `smartctl` itself, such as the version you're running and the copyright information. It helps in ensuring you're using an updated toolset.

### *Device specifics*

```nohighlight
Device Model:     QEMU HARDDISK
Serial Number:    QM00001
Firmware Version: 2.5+
User Capacity:    5,368,709,120 bytes [5.36 GB]
Sector Size:      512 bytes logical/physical
```

Here, you see details about the hard disk model, its serial number, firmware, storage capacity, and the size of its data sectors. These give you an overall snapshot of your drive's hardware specifics.

### *SMART support*

```nohighlight
SMART support is: Available - device has SMART capability.
SMART support is: Enabled
AAM feature is:   Unavailable
APM feature is:   Unavailable
```

This section confirms whether SMART capabilities are available and enabled. AAM (Automatic Acoustic Management) and APM (Advanced Power Management) are also mentioned, but they are unavailable in this example.

### *Timestamp/ATA*

```nohighlight
Local Time is:    Wed Sep  2 22:29:12 2020 UTC
ATA Version is:   ATA/ATAPI-7, ATA/ATAPI-5 published, ANSI NCITS 340-2000
```

The timestamp informs you when the test was conducted. The ATA Version gives details about the ATA protocol that your drive supports.

### *SMART attributes*

The lengthy section on SMART attributes provides specific metrics about your drive's health. Each attribute—like `Raw_Read_Error_Rate` or `Reallocated_Sector_Ct`—has its numerical values and flags. These serve as indicators for disk performance or upcoming failures. For example, `Reallocated_Sector_Ct` refers to the number of sectors that have been flagged as faulty and reallocated.

### *Error logs/other*

```nohighlight
No Errors Logged
```

If there were issues during the SMART data collection or previous tests, they would be listed here. 

### *Command sets*

```nohighlight
SCT Commands not supported
```

The absence or presence of SCT (SMART Command Transport) commands could influence the kinds of tests and operations you can perform on the disk.

### *Unsupported features*

```nohighlight
Device Statistics (GP/SMART Log 0x04) not supported
SATA Phy Event Counters (GP Log 0x11) not supported
```

Finally, these lines indicate features that are not supported by the disk. It's useful to know these limitations for advanced troubleshooting.

The output of `smartctl` can help you understand your disk's status, potentially diagnosing issues before they become problems.

## Advanced insights

MAAS allows you to scrutinise individual logs. Navigate to a machine of interest and choose the 'Hardware tests' page. There, you'll see a 'Log view' link in the 'Results' column for each test. Clicking this grants you access to detailed outputs, enabling more sophisticated diagnostics.