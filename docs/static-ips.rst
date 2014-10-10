.. _static-ips:

Static IPs
==========

.. note::

  This feature is available in MAAS versions 1.6 and above.
  If you're writing a client application, you can check if MAAS
  supports this feature via the web API; see the documentation for the
  ``static-ipaddresses`` capability :ref:`here<cap-static-ipaddresses>`.

Previously, MAAS relied on the DHCP server to allocate its own IP
addresses to nodes, using the IP range defined on the relevant cluster
interface. This was found to be unreliable since the IPs were only known
once the node had booted and requested an address, and had race conditions
when the lease expired and another machine was looking for its own IP.

MAAS now defines an additional range on the cluster for static IPs that
are allocated by MAAS itself (see :doc:`cluster-configuration` for more
information about this).

In normal operation, MAAS will automatically choose and allocate a static IP to
any node network interfaces where it knows on which cluster interface that node
interface is connected.

The :doc:`api` contains functions to request additional static IPs, which are
summarised here:

Sticky IPs
----------
Synopsis:
  ``POST /api/1.0/nodes/{system_id}/`` ``op=claim_sticky_ip_address``

Normally, IPs are released back into the pool of available IPs once a node
is released by a user.  A "Sticky" IP is one which is allocated to an interface
on a node that does not change unless the sticky IP is removed.  This enables
more predictable IPs at the cost of wasting IPs when the node is not in use.

Unmanaged User-allocated IPs
----------------------------
Synopsis:
  ``GET /api/1.0/ipaddresses/``

  ``POST /api/1.0/ipaddresses/`` ``op=release``

  ``POST /api/1.0/ipaddresses/`` ``op=reserve``

This API allows users to request an ad-hoc IP address for use in any way they
see fit.  The IP is not tied to any node in MAAS and is guaranteed not to be
in use by MAAS itself.

See the full :doc:`api` documentation for precise technical details.
