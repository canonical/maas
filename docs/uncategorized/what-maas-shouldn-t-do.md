# What MAAS shouldn't do

MAAS is powerful for what it was designed for: bare-metal lifecycle management and provisioning of servers. But when a tool is this flexible, it’s tempting to push it into spaces it wasn’t built to handle. This page lists common anti-patterns and misuses of MAAS, with guidance on what to do instead.

Think of MAAS as a scalpel, not a Swiss Army knife: precise and effective for the right jobs, but not the right tool for every situation.

## 1. Wrong scope of problem

* Personal PXE playground
  MAAS can boot and install machines, but if you only want to boot a single box over PXE once in a while, a simple `dnsmasq` + `tftp` setup will be easier.

* Cloud control plane replacement
  MAAS provisions hardware. It doesn’t replace OpenStack, Kubernetes, or your virtualization platform. Think of MAAS as the bottom layer you can build those systems on.

## 2. Networking anti-patterns

* Production DNS for your whole company
  MAAS can run DNS, but it’s meant for lab- or cluster-level service discovery. Don’t point your entire enterprise at it. Use a dedicated DNS infrastructure.

* DHCP across the corporate LAN
  MAAS DHCP works best on VLANs it controls. Pointing it at your entire office network will usually end in conflict and chaos.

* Firewall or NAT manager
  MAAS does not manage firewalls, NAT, or VPNs. Use a network security tool designed for those tasks.

## 3. Machine lifecycle misconceptions

* Ongoing desktop or laptop management
  MAAS is not designed to provision or manage desktops at scale. It doesn’t replace enterprise desktop imaging, endpoint management, or mobile device management (MDM) systems.

* Application patching and updates
  Once a machine is deployed, MAAS steps back. It won’t update application software, apply patches, or manage configuration drift. Tools like Ansible, Puppet, or Landscape are designed for that role.

* Continuous config management
  Don’t expect MAAS to act like Ansible or Puppet. Its job is to deliver a working machine, not to continuously configure or repair it.

* 24/7 monitoring
  MAAS checks machine state for provisioning purposes. It’s not Nagios, Zabbix, or Prometheus.

## 4. Image and operating system misuse

* General-purpose image factory
  MAAS streams and mirrors Ubuntu images, but it’s not your patch server or enterprise image pipeline. If you need hardened or custom images, build them with `packer`, `curtin`, or cloud-init tools.

* Unsupported distributions
  Fedora, CentOS, and Windows don’t “just work.” MAAS supports Ubuntu (and some specific integrations). Anything else requires effort outside normal workflows.

## 5. Scale mismatches

* Recursive “cloud-in-cloud” experiments
  Running MAAS inside MAAS inside LXD inside Multipass might work as a demo, but it’s not stable for real workloads.

* Internet-scale hosting
  MAAS can manage thousands of machines, but it’s not designed to operate like AWS or Azure across multiple regions.

## 6. Security pitfalls

* Using MAAS as an auth provider
  MAAS has basic roles. It’s not meant to replace LDAP, SSO, or IAM.

* Exposing the API/GUI to the internet
  MAAS is designed for trusted cluster admins. Putting it directly on the public internet without protection is risky.

## What to do instead

If you find yourself trying to bend MAAS into one of these roles, stop and ask:

* Is there a simpler tool for the job (e.g., `dnsmasq`, `tftp`, MDM, Ansible)?
* Am I trying to turn MAAS into something it was never designed to be?
* Can I layer the right tool on top of MAAS instead of expecting MAAS to handle everything?

## Summary

MAAS is an excellent tool for what it’s built to do: discover bare-metal servers, commission them, and hand them off ready for use. It is not a desktop imaging tool, a patch management service, a corporate DNS/DHCP backbone, or a monitoring system.

Stay inside its design boundaries and MAAS will serve you well. Try to use it for everything, and you’ll quickly discover its limits.
