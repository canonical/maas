> *Errors or typos? Topics missing? Hard to read? <a href="https://docs.google.com/forms/d/e/1FAIpQLScIt3ffetkaKW3gDv6FDk7CfUTNYP_HGmqQotSTtj2htKkVBw/viewform?usp=pp_url&entry.1739714854=https://maas.io/docs/about-resource-pools" target = "_blank">Let us know.</a>*

Resource pools in MAAS let admins group machines and VM hosts
logically, aiding in resource allocation for specific functions. By
default, all machines are added to the "default" pool, but custom
pools can be created for specific needs. For example, in a hospital
data center, you might reserve machines for applications like charts, documentation, or orders.

Assigning machines to resource pools ensures they're allocated appropriately, regardless of the specific application deployed on them. This grouping also enhances multi-tenancy by restricting user access based on roles and assigned pools.  MAAS auto-assigns new machines to the "default" resource pool.
