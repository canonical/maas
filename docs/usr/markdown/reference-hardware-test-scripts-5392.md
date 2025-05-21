This page enumerates standard MAAS test scripts and explains how to create your own custom scripts.

## MAAS test scripts

| **Name** | **Tags** | **What It Does** |
|:--------:|:--------:|:----------------:|
| `smartctl-short` | storage | Executes a short SMART self-test, assessing all your drives concurrently |
| `smartctl-long` | storage | Like the short test, but goes deeper. Ideal for comprehensive disk health checks |
| `smartctl-conveyance` | storage | Specialised SMART test that checks how your disks fare during transit |
| `memtester` | memory | Pushes your RAM with various memory-specific tests |
| `internet-connectivity` | network, internet, node | Verifies if the node has an active internet connection |
| `stress-ng-cpu-long` | cpu | A 12-hour CPU endurance test to push its limits |
| `stress-ng-cpu-short` | cpu | A quick 5-minute stress test for the CPU |
| `stress-ng-memory-long` | memory | A marathon 12-hour memory stress test |
| `stress-ng-memory-short` | memory | A quick dip to test memory, lasting only 5 minutes |
| `ntp` | network, ntp, node | Checks if the node can connect to NTP servers for time syncing |
| `badblocks` | storage | Scans the disk for bad sectors, in read-only mode |
| `badblocks-destructive` | destructive, storage | Same as above, but in a read/write mode that wipes data |
| `7z` | cpu | Tests CPU performance using 7zip benchmarking |
| `fio` | storage, destructive | Storage performance testing, with the potential to alter data |

## Real-time updates

As MAAS runs these tests, it gives you real-time updates. Navigate to the 'Hardware tests' page for the machine in question and click on the 'Log view' link in the 'Results' column to view unfiltered test output.

## DIY testing

You can create your own test scripts; here's a simple example:

```nohighlight
#!/bin/bash -e
# --- Start MAAS 1.0 script metadata ---
# name: stress-ng-cpu-test
# title: CPU Validation
# description: 5-minute stress test to validate your CPU.
# script_type: test
# hardware_type: cpu
# packages: {apt: stress-ng}
# tags: cpu
# timeout: 00:05:00
# --- End MAAS 1.0 script metadata ---

sudo -n stress-ng --matrix 0 --ignite-cpu --log-brief --metrics-brief --times \
    --tz --verify --timeout 2m
```

This Bash snippet features metadata comments that help configure the environment and handle any package dependencies. It ends with a line that triggers `stress-ng`, the workhorse that stresses your CPU to its core.

