.. -*- mode: rst -*-

***************************
DHCP lease scanning and DNS
***************************

Overview
========

In a MAAS system, cluster controllers may optionally manage the DHCP, and the
region controller may optionally manage the DNS.

The region controller periodically tells the cluster controllers to report
their DCHP leases.  When a cluster controller reports new leases, the region
controller creates DNS records for them, and instructs the cluster controller
to convert the leases to static host mappings.


Leases scanning
===============

MAAS will periodically scan the DHCP leases file using the
``upload_dhcp_leases()`` celery task, which originates via celerybeat.

As leases are discovered, it calls the api function ``update_leases()`` which
will subsequently generate a new task called ``add_new_dhcp_host_map()`` that
will use omshell to write a permanent mapping from MAC to IP in the DHCP
server.

That host map remains until the node is deleted, at which point the
``remove_dhcp_host_map()`` task is invoked which uses omshell to remove the
map.


Updating the DNS zone file
==========================

If a new lease is found then the dns.change_dns_zones() function gets called
which invokes two tasks::

 #. ``write_dns_zone_config()``
 #. ``rndc_command()``

The first is responsible for writing out a new zone file with the appropriate
sequence number and timestamp, and then the second is chained on to that
and sends an rndc message to the DNS server to reload the zone.
