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
``LeaseUploadService()`` pserv service.

As leases are discovered, it calls the RPC function ``UpdateLeases`` which
stores the active leases in the DHCPLease table.


Updating one or more DNS zone files
===================================

If a new lease is found then the dns.dns_update_zones() function gets called
which takes two steps::

 #. Write out updated zone files.
 #. Ask BIND to reload the zone.
