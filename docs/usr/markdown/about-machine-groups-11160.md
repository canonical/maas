MAAS provides several built-in grouping mechanisms them can be used to help find suitable machines faster.  Some of these groups support special use cases for tools like Juju or OpenStack, but none of them are limited.  These groups are just labels to MAAS; you decide how much structure to impose. 

## Options for grouping
MAAS exposes three main grouping tools: tags, availability zones, and resource pools.  Each was originally designed for a slightly different problem, but all three can be used more flexibly if your environment calls for it.  MAAS also provides notes and dynamic annotations.  While they’re not formal grouping tools, they give you extra ways to mark machines with context or live metadata that can help characterize machines quickly.

## Tags: flexible labels

Tags are the most open-ended grouping mechanism.  You can:

- Apply them directly to machines: You can assign one or more tags to any machine, by hand.

- Automate them with XPath: MAAS lets you set up XPath expressions that automatically attach tags when a machine meets certain criteria (for example, a particular CPU feature or interface type).

- Use them for selection: Tags are especially useful for selecting subsets of machines to commission or deploy.  For instance, you might tag machines with a specific NIC type so they can be targeted during commissioning.

Tags are flexible, multi-valued, and easy to search.  Think of them as a lightweight way to create many groups slice across your inventory in different ways, without re-archtecting it.

## Availability zones: designed as fault-domain labels

Availability zones (AZs) come from the cloud world.  They are:

Assigned one to a machine: MAAS only allows a machine to belong to a single AZ.

Originally for Juju and OpenStack: These tools treat AZs as “fault domains” — if something fails in one zone, they can redeploy workloads into another.  MAAS, on the other hand, makes no decisions about AZs.

Are compatible with failover semantics: In Juju or OpenStack, zones act like high-availability boundaries, so you get resilience by spreading workloads across them.

In MAAS alone, an AZ is just a label.  You can repurpose them any way you like, but they’re most valuable if you also run tools that respect fault domains.

## Resource pools: designed for access-control

Resource pools are another single-assignment label.  They are:

Assigned one to a machine: Like AZs, each machine belongs to one pool.

Designed for RBAC: Pools were added primarily to support role-based access control.  You can assign a pool to a user or team, giving them access to just that subset of machines.

Easy to customize: The pool name can be anything -- finance, HPC, staging, or “arm64-nodes." It’s entirely up to you.

Outside RBAC, MAAS does not’t enforce semantics beyond the label.  If you’re not using RBAC, pools are just another way to subdivide your machines.  Often this is useful when you have a limited number of machines per corporate function.

For example, if you run the IT department of a large hospital, you may want to reserve so many machines for nursing stations, so many for physicians, so many for pharamacy, and so on.  This helps make sure that one or two failed machines won't mean pulling capacity from another department.

## Notes and dynamic annotations

In addition to formal grouping, MAAS lets you attach notes or dynamic annotations to machines.  These aren’t designed as grouping tools, but they can provide context that helps you reason about why a machine is in a particular tag, zone, or pool.  Notes are human-readable reminders that persist through any state from Ready to Deployed.  Annotations are dynamic and persist only while a machine is deployed, but they can be updated programmatically to reflect changing conditions.
