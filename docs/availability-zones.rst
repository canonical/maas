Availability Zones
==================

To help you maximise fault-tolerance and performance of the services you
deploy, MAAS administrators can define *availability zones* (or just *zones*
for short), and assign nodes to them.  When a user requests a node, they can
ask for one that is in a specific zone, or one that is not in a specific zone.

It's up to you as an administrator to decide what an availability zone should
represent: it could be a server rack, a room, a data centre, machines attached
to the same UPS, or a portion of your network.  Zones are most useful when they
represent portions of your infrastructure.  But you could also use them simply
to keep track of where your systems are located.

Each node can be in at most one availability zone.  In a default setup, no
zones are defined and a node will not be in any zone at all.  If you do not
need this feature, you can simply pretend it does not exist.


Applications
------------

Since you run your own MAAS, its availability zones give you more flexibility
than those of a third-party hosted cloud service.  That means that you get to
design your zones and define what they mean.  Below are some examples of how
availability zones can help you get the most out of your MAAS.


Using Zones for Fault Tolerance
...............................

If you are concerned about availability of services you deploy through MAAS, an
availability zone could be on one power supply, or it could be an entire data
centre location, or an area of your network that is unlikely to suffer problems
when another zone experiences an outage.

For example, you might roll out separate instances of the same web application
into different availability zones of the same MAAS, and either load-balance
between them or keep one as a warm stand-by.  If one zone suffers a power loss,
is cut off from the internet, or is affected by a natural disaster, the other
instance of your application may still be available in the other zone, and
ready to take over.

For fault tolerance, machines that work together in order to provide one
instance of a service should generally be allocated in the same zone.  The
entire service should have a backup instance in another zone.


Using Zones for Performance
...........................

Even if fault tolerance is not an issue, you may still want to divide your
nodes into groups that communicate efficiently through a high-performance local
network, or share efficient access to external resources.

When it comes to performance, machines should generally be allocated in the
zone closest to performance-critical resources they need.

For example, for applications that are highly sensitive to network latency, it
may make sense to divide your MAAS into smaller physical networks, and
represent each of those networks as an availability zone.  Now, you can use the
availability zones to allocate nodes just where they get the best performance
when communicating with specific other nodes.

In another example, your application may rely on a third-party service
available on the internet.  If your MAAS is spread out across multiple data
centre locations, you may want the application to be deployed in the location
with the best access to that service.


Using Zones for Power Management
................................

If you are concerned about power density and cooling, you can lay out your
availability zones to match server racks.  Instead of allocating machines that
share an availability zone, you can spread out the load by ensuring that "hot"
systems are in located different zones.


Creating a Zone
---------------

Only administrators can create and manage zones.  To create an availability
zone in the web user interface, log in as an administrator and browse to the
"Zones" section in the top bar.  This will takes you to the zones listing page.
At the bottom of the page is a button for creating a new zone:

.. image:: media/add-zone.*

Or to do it in the :ref:`region-controller API <region-controller-api>`, POST
your zone definition to the *"zones"* endpoint.


Assigning Nodes to a Zone
-------------------------

Once you have created one or more availability zones, you can set nodes' zones
from the nodes listing page in the UI.  Select the nodes for which you wish to
set a zone, and choose "Set availability zone" from the "Bulk action" dropdown
list near the top.  A second dropdown list will appear, to let you select which
zone you wish to set.  Leave it blank to clear nodes' availability zones.
Clicking "Go" will apply the change to the selected nodes.

You can also set an individual node's zone on its "Edit node" page.  Both ways
are available in the API as well: edit an individual node through a ``PUT``
request to the node's URI, or set the zone on multiple nodes at once by calling
the ``set_zone`` operation on the ``nodes`` endpoint.


Allocating a Node in a Zone
---------------------------

To deploy in a particular zone, call the ``acquire`` method in the
:ref:`region-controller API <region-controller-api>` as before, but pass the
``zone`` parameter with the name of the zone.  The method will allocate a node
in that zone, or fail with an HTTP 409 ("conflict") error if the zone has no
nodes available that match your request.

Alternatively, you may want to request a node that is *not* in a particular
zone, or one that is not in any of several zones.  To do that, specify the
``not_in_zone`` parameter to ``acquire``.  This parameter takes a list of zone
names; the allocated node will not be in any of them.  Again, if that leaves no
nodes available that match your request, the call will return a "conflict"
error.

It is possible, though not usually useful, to combine the ``zone`` and
``not_in_zone`` parameters.   If your choice for ``zone`` is also present in
``not_in_zone``, no node will ever match your request.  Or if it's not, then
the ``not_in_zone`` values will not affect the result of the call at all.
