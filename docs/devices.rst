.. -*- mode: rst -*-

.. _devices:

Devices
========

.. note::

  This feature is available in MAAS versions 1.8 and above.
  If you're writing a client application, you can check if MAAS
  supports this feature via the web API; see the documentation for the
  ``devices-management`` capability :ref:`here<cap-devices-management>`.

In addition to nodes, a MAAS cluster controller can manage *devices*. Devices
represent non-installable machines. This feature can be used to track
routers, virtual machines, etc. within MAAS.

Same as nodes, devices can be assigned IP addresses and DNS names. IP
addresses can be fixed, in which case the device should be configured to use
the defined IP address, or dynamic, in which case the device can obtain an
IP address from the MAAS DHCP server and will receive the configured IP
address.

Devices can also be assigned a parent node and will be automatically deleted
(along with all the IP address reservations associated with it) when the
parent node is deleted or released. This is designed to model and manage the
virtual machines or containers running on a MAAS-deployed node.