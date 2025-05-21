Distinguish groups of machines by assigning availability zones, tags, and resource pools.

## Availability zones

An availability zone is an organizational unit containing nodes, with each node belonging to exactly one zone. Zones help with fault tolerance, service performance, and power management. Machines can be allocated from specific zones in production.

### Fault tolerance

Fault tolerance ensures a system continues operating despite failures. MAAS zones can improve resilience by separating resources based on power supply, network segmentation, or data center location.

- Machines working together should be in the same zone.
- The entire service should be replicated in another zone for redundancy.

### Service performance

Service performance focuses on efficiency and speed. MAAS zones help by placing nodes close to performance-critical resources.

- Allocate nodes based on network topology and latency needs.
- Use smaller, well-defined zones to group resources efficiently.

### Power management

Power management optimizes power usage and cooling.

- Distribute high-power or heat-generating nodes across zones.
- Prevent hotspots and balance power consumption.

### Default zone

A newly installed MAAS includes a default zone that holds all nodes. You cannot remove or rename this zone, but you can create new ones and assign machines. If zones aren’t relevant to your setup, you can ignore them.

## Tags

Tags are short, descriptive, searchable words that can be applied to various objects, including:

- machines
- VM hosts
- controllers (rack and region)
- storage devices (block devices or partitions)
- network interfaces
- devices
- nodes (via CLI)

They help identify, group and locate objects efficiently, especially when managing numerous machines. 

### Tag types

Two types of tags can be used:

- **Manual Tags:** These are user-defined tags applied directly to MAAS objects. Users can create and assign tags based on specific criteria or organizational needs. For example, tagging machines based on their role, location, or hardware specifications.

- **Automatic Tags:** Introduced in MAAS 3.2 and above, automatic tags use XPath expressions to auto-apply tags to machines that match specific hardware characteristics or settings. This feature allows for dynamic tagging based on machine attributes, such as CPU features, memory size, or presence of specific hardware components. For instance, machines with Intel VT-d enabled and a Tesla V100 GPU can be automatically tagged for GPU passthrough configurations.

## Annotations

Annotations are descriptive, searchable phrases that apply only to machines. They come in two types:

- **Static Annotations:** Always present, regardless of the machine's state.

- **Dynamic Annotations:** Present only when machines are in allocated or deployed states.

Annotations assist in identifying, characterizing, and conveying information about machines within the MAAS environment.

## Managing Tags and Annotations

- **Creating and Assigning Tags:** In the MAAS UI, creating and assigning tags is a combined operation. Users can enter the desired tag name in the "Tags" field when editing an object, and the tag will be created and assigned simultaneously.

- **Removing Tags:** To remove a tag, users can click the "X" next to the tag name in the object's "Tags" field. The tag is effectively deleted when it's removed from all associated objects. 

- **Automatic Tagging:** By defining XPath expressions, MAAS can automatically apply tags to machines that match specific criteria. This automation ensures that machines with particular hardware configurations or capabilities are consistently tagged, facilitating efficient management and deployment.

Utilizing tags and annotations in MAAS enhances the organization, searchability, and management of resources, streamlining operations in complex environments.

## Resource pools

Resource pools in MAAS let admins group machines and VM hosts logically, aiding in resource allocation for specific functions. By default, all machines are added to the "default" pool, but custom pools can be created for specific needs. For example, in a hospital data center, you might reserve machines for applications like charts, documentation, or orders.

Assigning machines to resource pools ensures they're allocated appropriately, regardless of the specific application deployed on them. This grouping also enhances multi-tenancy by restricting user access based on roles and assigned pools. MAAS auto-assigns new machines to the "default" resource pool.

