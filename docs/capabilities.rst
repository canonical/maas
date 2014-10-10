.. -*- mode: rst -*-

.. _capabilities:

Capabilities
============

MAAS publishes a special view at ``.../api/1.0/version/`` that returns a
list of the server's capabilities. It's transferred as a JSON document::

    {"capabilities": ["name-of-capability", ...]}

.. note::

  The view is called ``version`` because this will, later, include
  version information too.


List of capabilities
--------------------

Check for the following strings in the capabilities list to see what
features the MAAS server supports. Use these in preference to gating on
the version when creating a client application.

.. _cap-networks-management:

``networks-management``
  Passive modelling of the network environment that cluster controllers
  nodes are in, including network interfaces, subnets, VLAN tags, and
  connectivity between them. See :ref:`networks` for more information.

.. _cap-static-ipaddresses:

``static-ipaddresses``
  Static IP address allocation to nodes, including user-reserved IPs and admin-
  allocated 'sticky' IPs. Available since version 1.6. See :ref:`static-ips`
  for more information.

.. _cap-ipv6-deployment-ubuntu:

``ipv6-deployment-ubuntu``
  Deploy Ubuntu nodes with IPv6 networking enabled.  See :ref:`ipv6` for more
  about this feature.
