=====================================
Installing Ubuntu and deploying nodes
=====================================

Once a node has been accepted into MAAS and is ready for use, users can
deploy services to that node.

Prior to deployment, MAAS is responsible for:

1. Powering up the node.
2. Installing Ubuntu on the node (with the help of :ref:`curtin
   <curtin-installer>`).
3. Installing the user's SSH keys on the node.

Once these steps have been completed, the node is ready to have services
deployed to it, either manually or by using a tool like Juju_.

.. _Juju: http://juju.ubuntu.com


.. _curtin-installer:

Curtin: The Curt Installer
--------------------------

As the name suggests this installs Ubuntu on a node more quickly than
would be possible using the traditional Debian installer.

Curtin is enabled by default and is the only mechanism for installing
Ubuntu supported by MAAS. It copies a pre-built Ubuntu image to the
node, with all the packages installed that would be normally found in an
Ubuntu installation. It's very fast!

For more information about curtin, see its `project page`_ on Launchpad.

.. _project page: https://launchpad.net/curtin
