.. _orientation:

Orientation
===========


MAAS in Brief
-------------

Canonical’s MAAS brings the dynamism of cloud computing to the world
of physical provisioning and Ubuntu. Connect, commission and deploy
physical servers in record time, re-allocate nodes between services
dynamically, and keep them up to date and in due course, retire them
from use.

MAAS is a new way of thinking about physical infrastructure. Compute,
storage and network are commodities in the virtual world, and for
large-scale deployments the same is true of the metal. “Metal as a
service” lets you treat farms of servers as a malleable resource for
allocation to specific problems, and re-allocation on a dynamic basis.

In conjunction with the Juju service orchestration software (see
https://juju.ubuntu.com/docs/), MAAS will enable you to get the most
out of your physical hardware and dynamically deploy complex services
with ease and confidence.


Do I Need MAAS?
---------------

MAAS certainly isn't for everyone, but why not ask yourself these
questions?

You probably *SHOULD* use MAAS if any or all of the following
statements are true:

    * You are trying to manage many physical servers.
    * You want to deploy services with the minimum fuss.
    * You need to get the most from your resources.
    * You want things to work, repeatably and reliably.

You probably don't need MAAS if any or all of these statements are
true:

    * You don't need to manage physical hardware
    * You relish time spent in the server room
    * You like trying to set up complicated, critical services without any help


.. _setup:

A Typical MAAS setup
--------------------

MAAS is designed to work with your physical hardware, whether your
setup includes thousands of server boxes or only a few. The key
components of the MAAS software are:

  * Region controller
  * Cluster controller(s)
  * Nodes

The nodes are the computers you manage using MAAS.  These can range from just
a handful to many thousands of systems.

For small (in terms of number of nodes) setups, you will probably just
install the Region controller and a cluster controller on the same
server - it is only worth having multiple region controllers if you
need to organize your nodes into different subnets (e.g. if you have a
lot of nodes).  If you install the ``maas`` package, it will include both a
region controller and a cluster controller, and they will be automatically
set up to work together.

.. image:: media/orientation_architecture-diagram.*


How MAAS is used
----------------

MAAS manages a pool of nodes.  After registering a new system with the MAAS
and preparing it for service ("commissioning"), the new system joins this pool.

From the moment a node is accepted into the MAAS, any operating system,
software, or data that it may have had installed before is meant to be
overwritten.  A node in the pool is under MAAS's sole control, and off-limits
to users.

Once you have nodes in the pool, users of the MAAS can allocate them for their
own use.  At that point, the nodes are installed with the selected operating
system and set up with the user's login credentials for remote access.  This
is referred to as "starting" a node in the browser interface, and as
"acquiring" (and, as a separate step, "starting") a node in the API.

When allocating from the API, you can specify constraints such as how much
memory you need, how many CPUs, what networks the node should be connected to,
what physical zone they should be in, and so on.  API commands can also be
issued through the ``maas`` command-line utility.

An allocated node is not like a virtual instance in a cloud: you get complete
control, including hardware drivers and root access.  To upgrade a BIOS, for
example, an administrator could allocate a node to themselves, and run a
vendor-supplied upgrade utility.  Needless to say, you also get full hardware
performance and tweaking!

Once you are done with a node you have allocated, you can release it back to
the pool.  Once again any data, software, or operating system will no longer
be available.
