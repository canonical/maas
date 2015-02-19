======================================
How cluster registration works in MAAS
======================================

A region controller associates with one or more cluster controllers, each
of which is responsible for contacting the region controller itself and
announcing its presence.  An admin must accept or reject each cluster that
registers itself with the region controller, except in the special
circumstance mentioned in :ref:`first-cluster`.

There is always at least one cluster controller in MAAS (known as a
NodeGroup in the code) which is known as the 'master'. The Nodegroup entry
always exists even if no cluster controllers have contacted the region
controller yet, so that it can be used as a default when adding nodes in the
API or UI before the cluster controller is defined.  Once a real cluster
controller connects it will become this master.

This logic was originally implemented as an easy way to upgrade older
installations that were created before nodegroups were introduced.

Region Controller Location
--------------------------

The cluster obviously needs to know where the region controller is, and this is
configured in a file ``/etc/maas/maas_cluster.conf`` (or
``etc/demo_maas_cluster.conf`` for development environments).


.. _first-cluster:

First cluster to connect
------------------------

For the convenience of small setups (and the development environment), the
first cluster controller to connect to the region controller becomes the
'master' nodegroup, and if the cluster connects *from the same host*, it
is automatically accepted.

The logic currently looks like this:

#. If there is one, the oldest nodegroup is the master.

#. If none exists, the code creates a placeholder master nodegroup on the fly,
   pre-accepted but without a UUID.

#. If the placeholder is the only nodegroup, the first cluster controller to
   register becomes the master.

Sadly, there is some code complexity to clear up here as this logic is not
encapsulated in a single place, but instead in both:

* ``NodeGroup.objects.ensure_data()`` and
* ``AnonNodeGroupsHandler.register()``.
