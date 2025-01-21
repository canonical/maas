It may be beneficial to understand how LXD projects fit into the overall MAAS ecosystem.  LXD projects are not intended to be MAAS projects; they are only intended to limit which LXD containers and VMs are available to MAAS. 

> Pro tip: MAAS 2.9 does not support LXD projects.  Best to upgrade if you need them.

## LXD projects

[LXD projects](https://ubuntu.com/tutorials/introduction-to-lxd-projects#1-overview) are a feature of the [LXD lightweight container hypervisor](https://ubuntu.com/server/docs/containers-lxd)**^** -- a next-generation container manager which makes containers as easy to manage as virtual machines.  With LXD, you can create lots of containers, providing different services across many different use cases.  As a result of this flexibility, it can become confusing to keep track of exactly which containers are providing what services to answer which use case.

To help with this potential confusion, LXD provides a "projects" feature, which allows you to group one or more containers together into related projects.  These projects can be manipulated and managed with the same `lxc` tool used to manage the containers and virtual machines themselves.

Since MAAS makes use of LXD as a VM host, it's useful to be able to manipulate and manage projects not only through MAAS, but also directly through LXD.  In fact, to properly scope MAAS access to your LXD resources, it's essential that you understand how to use LXD projects in some detail.

## Design choices

Prior versions of MAAS implemented LXD VM hosts, but did so in a strongly-coupled way; that is, MAAS essentially took control of the VMs, disallowing or overriding some direct LXD controls.  In a sense, MAAS became the owner, rather than simply a separate program, communicating interdependently with LXD to accomplish user purposes.

This was less than ideal.  For example, MAAS would discover all running LXD VMs and immediately commission them, essentially performing a "clean install" and wiping out their contents.  This behaviour isn't suitable when MAAS is connected to a deployed LXD with VMs already running services that may not have been targeted for enlistment by MAAS.

With the release of MAAS 3.0 version, MAAS now becomes a LXD tenant, rather than an owner.

As you can infer from some of the discussion above, MAAS and LXD are separate products.  It's beneficial for them to interact, but not if one product cannot be controlled and managed independently of the other.  The combination of MAAS and LXD can cover a much broader set of use cases between them if they act as independent tools.  While the most loosely-coupled model would have MAAS selecting individual VMs, that model isn't compatible with how MAAS works with other networks and devices, so we chose to implement projects as a way to section off LXD VMs for normal use by MAAS.

## MAAS and LXD projects 

Essentially, MAAS still commissions any VMs it discovers within a VM host, but the scope of the discovery is now limited to a single project.  That project can contain any subset of the existing VMs, from zero to all of them.  Any VM that's already in a project assigned to MAAS will still be re-commissioned, which is the normal behaviour of MAAS upon network discovery.

Here are the criteria which drove this decision:

- It should be possible for an administrator to select which project(s) MAAS manages, and thus which machines will be automatically enlisted and commissioned.
- It should be possible for MAAS to create and self-assign a new (empty) project, so that the user can compose new VMs within LXD from within the MAAS interface.
- No per-project features should be enabled by default in MAAS-created projects.
- The project must be explicitly specified when creating the LXD VM host.
- When a LXD VM host is added, only the existing VMs assigned to the selected project (if any) should be visible to MAAS (and thus, automatically commissioned), and VMs in non-MAAS projects are not affected in any way.
- When a LXD VM host is deleted, the default behaviour should be for MAAS to leave existing VMs, rather than automatically deleting them; VMs in non-MAAS projects are not affected in any way.
- MAAS will not create VMs in projects that it doesn't own.
- When a VM is composed in MAAS, it's created in the target LXD project.

In addition, a MAAS administrator should be able to:

- refresh information about a specific LXD VM host, and receive correct, up-to-date, and timely status.
- explicitly specify connections between networks and VM interfaces.
- deploy a machine directly as an LXD VM host, connected to MAAS from the outset.

These criteria were fully met in the MAAS LXD tenant implementation released as part of MAAS 3.0.

## LXD project alternatives

You can see from the discussion above that LXD projects were used primarily to cordon off some LXD VMs from MAAS, to avoid them from being enlisted and commissioned by MAAS (and thus, essentially, destroyed, from an operational perspective).  These LXD project features provide some limited capabilities to group machines. Because LXD projects only deal with LXD VMs and VM hosts, they are not a complete or comprehensive set of project tools.  MAAS already has those machine grouping capabilities in the form of resource pools.

We realised, though, as we were working with LXD projects, that we could vastly improve the documentation for resource pools in the area of projects and project management.  You'll find significant new material in the resource pools section of the doc.  We also realised that it would be helpful to have "real-time tags" for machines, that is, annotations that persist only while a machine is allocated or deployed.  These new "tags" are known as workload annotations, and they have also been given a thorough treatment, also with their own page in the left-hand navigation.