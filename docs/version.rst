.. -*- mode: rst -*-

.. _capabilities:

Version
=======

MAAS publishes a special view at ``.../api/2.0/version/`` that returns the
version of the MAAS server and the list of the server's capabilities.
When programmatically probing a MAAS installation, use only the
``capabilities`` list. Avoid using ``version`` and ``subversion`` for anything
other than informational purposes. It's transferred as a JSON document::

    {
      "version": "1.8.0",
      "subversion": "6472-gc33bbb8",
      "capabilities": [
          "name-of-capability-1",
          "name-of-capability-2"
      ]
    }


List of capabilities
--------------------

Check for the following strings in the capabilities list to see what
features the MAAS server supports. Use these in preference to gating on
the version when creating a client application.

.. _cap-networks-management:

``networks-management``
  Passive modelling of the network environment that cluster controllers
  nodes are in, including network interfaces, subnets, VLAN tags, and
  connectivity between them. See :doc:`networking` for more information.

.. _cap-static-ipaddresses:

``static-ipaddresses``
  Static IP address allocation to nodes, including user-reserved IPs and admin-
  allocated 'sticky' IPs. Available since version 1.6. See :ref:`static-ips`
  for more information.

.. _cap-ipv6-deployment-ubuntu:

``ipv6-deployment-ubuntu``
  Deploy Ubuntu nodes with IPv6 networking enabled.  See :ref:`ipv6` for more
  about this feature.

.. _cap-devices-management:

``devices-management``
  Management of devices (non-installable nodes).  Available since version 1.8.
  See :ref:`devices` for more about this feature.

.. _cap-storage-deployment-ubuntu:

``storage-deployment-ubuntu``
  Deploy nodes with custom storage layout and configuration. Available since
  version 1.9 on Ubuntu deployments. See :ref:`storage` for more about this
  feature.

.. _cap-network-deployment-ubuntu:

``network-deployment-ubuntu``
  Deploy nodes with custom network layout and configuration. Available since
  version 1.9 on Ubuntu deployments. See :ref:`networking` for more about this
  feature.

.. _cap_bridging-interface-ubuntu:

``bridging-interface-ubuntu``
  Deploy nodes, selectively configuring bridges on network interfaces.
  Available since 2.1 on Ubuntu deployments.

.. _cap_bridging-automatic-ubuntu:

``bridging-automatic-ubuntu``
  Deploy nodes, automatically configuring bridges on all interfaces.
  Available since 2.1 on Ubuntu deployments.

.. _cap_authenticate_api:

``authenticate-api``
  An ``/accounts/authenticate/`` endpoint is available for API clients.
  Clients can pass a username and password and, assuming they are valid,
  receive in return an API token. The caller is *not* logged-in to MAAS
  via a session cookie.
