Once MAAS has discovered a machine, it begins a structured life-cycle that reflects the real stages of bringing hardware into service, operating it, and eventually returning it to the pool.  Understanding this flow is essential to managing machines effectively.


## Enlistment: when MAAS first meets a machine

When a machine is configured to network boot (PXE/iPXE) on a subnet controlled by MAAS, it will contact MAAS during boot.  MAAS responds with a small ephemeral image, boots the machine, and records its basic identity (MAC address, architecture).  At this point the machine appears in MAAS with the state:

- New - visible to admins, but not yet trusted for workloads.

Admins can also manually add machines.  In that case MAAS skips the “new” stage and immediately commissions them.


## Commissioning: gathering the details

Commissioning turns a "new" machine into a usable one.  MAAS:

- Boots the machine into an ephemeral Ubuntu image.
- Runs hardware probes to detect CPU, RAM, storage, and network devices.
- Applies baseline configuration (firmware settings, power parameters).
- Runs optional hardware tests to confirm the machine is healthy.

Power parameters:

For supported power drivers, MAAS creates a dedicated `maas` user on the
BMC with a randomly generated password, then uses those credentials for
power control.  MAAS stores the credentials in its database and does not
modify existing BMC users unless you explicitly configure it to do so.
Examples include power drivers using IPMI and Redfish.

Note that if your policy forbids new BMC users, you can supply existing
credentials instead; MAAS will use what you provide and skip creating
`maas`.

Outcomes:

- Commissioning - while the process is in progress.
- Failed - if MAAS cannot complete commissioning or if tests fail.
- Ready - if the machine passes.

At this point MAAS has a complete hardware inventory for scheduling and can deploy the machine.


## Allocation and ownership

To prevent conflicts in multi-user environments, machines must be allocated before they can be deployed:

- Allocated - a "ready" machine has been reserved by a user or project.  Other users can’t deploy it until it’s released.

Allocation does not change the machine’s state on the wire — it still sits idle — but it locks the record in MAAS for one user.


## Deployment: making the machine useful

When the user initiates deployment:

1.  MAAS powers on the allocated machine.
2.  It boots via PXE and installs the chosen operating system.
3.  MAAS reboots the machine into the new OS, adds user data (via `cloud-init`), and hands control to the user.

The states:

- Deploying - installation is in progress.
- Deployed - installation succeeded; the machine is running in the chosen OS.

From here, the machine is fully usable as a server.


## Releasing: returning to the pool

When the workload is finished, a machine can be released:

- Releasing - MAAS is wiping the disks (if secure erase options are selected).
- Ready - once released, the machine is idle again and available for others to allocate.

Disk erasure ensures sensitive data isn’t passed to the next user.


## Exceptional and maintenance states

Some states occur outside the normal cycle:

- Rescue mode - boots the machine into an ephemeral environment for troubleshooting.  Useful if an OS won’t boot or if you need to repair storage.
- Broken - an admin can mark a machine as broken when it has hardware issues; it cannot be deployed until repaired and recommissioned.
- Failed - an automatic state assigned when commissioning or deployment did not succeed.  Machines must be recommissioned before use.


## Advanced features

- Cloning configurations (3.1+): admins can copy storage and network layouts from one machine to others, provided their hardware is compatible.
- Adding live machines (3.1+): MAAS can import machines that are already running workloads.  These appear as "deployed" immediately, bypassing the usual commissioning sequence.


## Key takeaway

The life-cycle is MAAS’s way of mirroring the real operational journey of a server:

New > Commissioning > Ready > Allocated > Deploying > Deployed > Releasing > Ready again.

Understanding the transitions -- what MAAS is doing, what the admin can do, and what failures mean -- lets you manage machines with confidence and keep your fleet healthy.

## Next steps

- Dig into [the commissioning process](https://canonical.com/maas/docs/about-commissioning-machines) to understand the kinds of hardware knowledge MAAS needs to deploy a machine successfully.
- Take a deep dive into [machine deployment](https://canonical.com/maas/docs/about-deploying-machines); this is how MAAS provisions machines to run workloads.
