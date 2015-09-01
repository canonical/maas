=====================================
Installing Ubuntu and deploying nodes
=====================================

Once a node has been accepted into MAAS and is ready for use, users can
deploy services to that node.

Prior to deployment, MAAS is responsible for:

1. Powering up the node.
2. Installing Ubuntu on the node.
3. Installing the user's SSH keys on the node.

Once these steps have been completed, the node is ready to have services
deployed to it, either manually or by using a tool like Juju_.

There are two ways to install Ubuntu on a node:

1. :ref:`The Curtin installer <curtin-installer>`.
2. :ref:`The Debian installer (Deprecated) <debian-installer>`.


.. _Juju: http://juju.ubuntu.com

.. _curtin-installer:

The Curtin Installer
--------------------

The Curtin Installer is, as the name suggests, installs
Ubuntu on a node more quickly than would be possible using the
:ref:`Debian installer <debian-installer>`.

The Curtin installer is enabled by default and is the only one supported.

The Curtin installer copies a pre-built Ubuntu image to the node, with all
the packages installed that would be normally found in an Ubuntu
installation. The Curtin installer is the fastest OS installer yet.

For more information about the Curtin installer, see the `curtin project`_
on Launchpad.

.. _curtin project: https://launchpad.net/curtin

.. _debian-installer:

The Debian Installer (Deprecated)
---------------------------------

The Debian Installer installs Ubuntu on a node in exactly the same way
as you would install it manually.

.. note::
  Starting from MAAS 1.8, the Debian Installer has been deprecated and
  it is no longer supported. While it is still available in MAAS, it is
  not recommended and is not supported.
