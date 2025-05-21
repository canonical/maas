LXD provides a projects feature that groups containers, managed with `lxc`. Projects are a feature of LXD; MAAS uses them strictly to limit visibility of LXD VMs, beginning with MAAS 3.0. Prior versions of MAAS enlisted all LXD VMs, overriding LXD control.

With the 3.0 version, MAAS now becomes a LXD tenant, rather than an owner. MAAS now enlists only the VMs within a specified project. Any VM that's already in a project assigned to MAAS will be commissioned -- the normal behaviour of MAAS upon network discovery.

