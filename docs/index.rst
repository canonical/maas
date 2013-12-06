.. MAAS documentation master file

########################
Metal As A Service: MAAS
########################

This is the documentation for the MAAS project http://maas.ubuntu.com

************************
MAAS: Metal as a Service
************************

Metal as a Service -- MAAS -- lets you treat physical servers like
virtual machines in the cloud. Rather than having to manage each
server individually, MAAS turns your bare metal into an elastic
cloud-like resource.

What does that mean in practice? Tell MAAS about the machines you want
it to manage and it will boot them, check the hardware's okay, and
have them waiting for when you need them. You can then pull nodes up,
tear them down and redeploy them at will; just as you can with virtual
machines in the cloud.

When you're ready to deploy a service, MAAS gives Juju the nodes it
needs to power that service. It's as simple as that: no need to
manually provision, check and, afterwards, clean-up. As your needs
change, you can easily scale services up or down. Need more power for
your Hadoop cluster for a few hours? Simply tear down one of your Nova
compute nodes and redeploy it to Hadoop. When you're done, it's just
as easy to give the node back to Nova.

MAAS is ideal where you want the flexibility of the cloud, and the
hassle-free power of Juju charms, but you need to deploy to bare
metal.

************
Introduction
************
.. toctree::
   :maxdepth: 2
   
   about
   changelog
   orientation


***************
Getting started
***************

.. toctree::
   :maxdepth: 2

   install
   configure
   cluster-configuration
   nodes
   kernel-options


******************
Deploying services
******************

.. toctree::
   :maxdepth: 2

   juju-quick-start
   tags


******************************
Using the maas-cli commandline
******************************

.. toctree::
   :maxdepth: 2

   maascli


***************
Developing MAAS
***************

.. toctree::
   :maxdepth: 2

   development/philosophy
   development/security
   development/building-packages
   development/cluster-registration
   development/tagging
   development/lease-scanning-and-dns
   development/preseeds


**********
Appendices
**********

.. toctree::
   :maxdepth: 2

   troubleshooting
   hacking
   api
   models
   enum


Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`
