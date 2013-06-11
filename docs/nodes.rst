Adding nodes to the system
==========================

Now that the MAAS controller is running, we need to make the nodes
aware of MAAS and vice-versa. If you have set up DHCP correctly, and
your nodes can boot via PXE then things really couldn't be much easier
and you can use :ref:`the automatic discovery procedure <auto-enlist>`


.. _auto-enlist:

Automatic Discovery
-------------------

With nodes set to boot from a PXE image, they will start, look for a
DHCP server, receive the PXE boot details, boot the image, contact the
MAAS server and shut down.

During this process, the MAAS server will be passed information about
the node, including the architecture, MAC address and other details
which will be stored in the database of nodes. You can accept and
comission the nodes via the web interface.  When the nodes have been
accepted the selected series of Ubuntu will be installed.

To save time, you can also accept and commission all nodes from the
commandline. This requires that you first login with the API key,
which :ref:`you can retrieve from the web interface <api-key>`::

   $ maas-cli maas nodes accept-all


.. _enlist-via-boot-media:

Enlist nodes via boot media
---------------------------

Using Boot media such as an AVAHI boot image or the Ubuntu Server
install disk, it is possible to perform the discovery and enlistment
process without using DHCP/PXE.

Boot from the media and follow the instructions.


Manually add nodes
------------------

If you know the MAC address of a node, you can manually enter details
about the node through the web interface.
