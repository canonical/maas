.. -*- mode: rst -*-

Networks
========

.. note::
  This feature is available in MAAS versions 1.5 and above, starting with
  revision 1961.

A MAAS cluster controller can manage nodes on one or more networks.  The
cluster controller must have direct interfaces connected to these networks,
and each node must be managed through one of them.

But nodes may also be connected to additional networks, for your production
workload, for internet access, for internal communication, or perhaps for
system-level or application-level management tasks.  MAAS does not need to
manage these networks, but it can be useful for MAAS to be aware of them.  If
MAAS is aware of these networks, you can allocate nodes with specific network
requirements.  For example, when requesting a node, you could specify:

* "Must be connected to the staging network" (for a test application).
* "Needs to share a network with a given other node" (for fast communication).
* "Should not be connected to the DMZ network" (for security).
* "Can't be on the Houston network" (for resilience).
* "Has to be connected to a particular VLAN" (for software-defined networking).

To avoid confusion, MAAS imposes three rules on the networks you define.  Apart
from these, MAAS places no restrictions on the number or nature of your
networks, or on which nodes are connected to which networks.  The rules are:

1. Each node must be on a network that is directly connected to an interface
   on the node's cluster controller.  It is recommended that you let the
   cluster controller manage DHCP and DNS on this network. See
   :doc:`cluster-configuration` for the details.
2. All networks must have different, non-overlapping IP ranges.  Any possible
   IP address in the MAAS should belong to only one network.
3. If you use virtual networks, each must have a different VLAN tag in the
   range 0x001 to 0xffe (1 to 4094) inclusive.  Non-virtual networks have no
   tag, and you can have as many of these as you want.

Networks are defined globally, not within clusters.  They can span clusters,
or be confined to clusters, or connect selected nodes from different clusters,
as suits your needs.  For now, if you want to make use of these placement
constraints when allocating nodes, you need to define your networks explicitly.
Future versions of MAAS may detect some of your networks and define them
automatically.

The networks on which MAAS manages nodes are special, however: they cannot
connect to different clusters.   These are the networks that connect to
interfaces on the cluster controller.  You may define these networks, but you
don't have to.  You need a cluster interface for MAAS to manage nodes (or even
just serve DHCP) on the network to which it is connected.  Networks, on the
other hand, only need to be defined in order to enable network placement
constraints when allocating nodes, as in the examples above.


Defining networks
-----------------

There are two ways to define networks: through the web user interface, or
through the API.  The command-line interface acts a front-end for the API.

To define a network in the user interface, click on ``Networks`` in the top
bar.  This will take you to the listing of known networks.  Click the
``Add network`` button to start entering your network's information.

.. image:: media/add-network.png

Assign each network a short name for easy reference, and optionally, a more
detailed description.  Fill out the other fields as detailed below.  Click
``Add network`` to bring your network definition into effect.

Networks are defined as a pair of a base IP address and a netmask.  For a
24-bit network ``10.122.1.0/24``, for example, the IP address would be
``10.122.1.0`` and the netmask would be ``255.255.255.0``.

The bits that correspond to zeroes in the netmask are not part of the network
address, so if you entered ``10.122.1.9`` as the network's IP address, it would
still come out as ``10.122.1.0``.

MAAS also supports virtual networks, or VLANs.  Multiple VLANs can share the
same underlying physical network.  A "tag" on each network packet tells the
infrastructure on which of the VLANs the packet is travelling.  Each VLAN is
effectively a separate network.

The VLAN tag is a number between 1 and 4094 inclusive, as dictated by the
underlying technical standard.  Leave this blank if the network is not a VLAN,
or if it is untagged.  The number zero is a reserved value that means
"no VLAN," as you would get with conventional networks, and so MAAS treats it
as a blank field.

You can also define a network through the
:ref:`region-controller API <region-controller-api>`.  The values are the same
as for the web UI.  To do this, ``POST`` your network definition to the
*"networks"* endpoint.


Connecting nodes to networks
----------------------------

In order for network placement constraints to take effect, you must also tell
MAAS which nodes are connected to each network.

Nodes connect to networks through their network interface cards.  Each of
these NICs has a MAC address, and so, a connection between a node and a
network is associated with one of the node's MAC addresses.  The network
interface and its MAC address must be registered with MAAS before it can be
attached to a network.  A node's network interfaces are normally registered
:ref:`automatically when the node is enlisted <auto-enlist>`, but in some
situations you may need to do this manually in the web user interface.

To inform MAAS about nodes' connections to a network through the user
interface, you must either specify them when creating the network, or edit the
network's details.  You can get to a network's edit page either by browsing to
its details page and clicking the "Edit" link in the right-hand bar, or by
clicking on the "pencil" icon for the network's entry in the networks listing
under the "Networks" section in the top bar.

On the network add/edit pages, you will see a selection box where you can
select which network interfaces are connected to that network, as well as the
nodes to which they belong.

.. image:: media/connect-nodes-to-network.png

The box lets you select multiple network interfaces, even if they belong to
the same node.  Click "Save network" to make your changes permanent.

You can also connect nodes to networks using the
:ref:`region-controller API <region-controller-api>`.  A network has a ``POST``
method ``connect_macs``, which lets you connect any number of network
interfaces to the network in one call.  The network interfaces are identified
as a list of MAC addresses.  The list may also be empty (in which case the
call does nothing), and connecting a network and a network interface that are
already connected is not an error.

Connecting a node to a network does not affect any other connections between
the node and other networks, or between the network and other nodes.  A
matching ``POST`` method, ``disconnect_macs``, removes connections between a
network and network interfaces.  Again, empty lists are accepted and
disconnecting a node from a network that it is not connected to is not an
error.

Future versions of MAAS may detect and register some of the networks and their
connections to nodes automatically.


Placement constraints
---------------------

When you allocate a node through the API, or search for nodes in the web UI,
you can specify two kinds of constraints for the node's network placement:

1. ``networks`` specifies that the node you want must be connected to *all* of
   the given networks.
2. ``not_networks`` says that a node must *not* be connected to *any* of the
   given networks.

Constraints can identify a network in any of several ways.  You may combine
these freely.  Each is a way of referring to a specific network, just expressed
in different ways.

* "``network-name``": The name of a network as it was defined in the MAAS.  The
  example is for the case where you have defined a network with the name,
  ``network-name``.
* "``ip:10.122.1.0``": An IP address in the network.  This can be the network's
  base address, or its broadcast address, or any other IP address that falls
  within the network.  So ``ip:10.122.1.0`` identifies the same network as, for
  example, ``ip:10.122.1.99``.
* "``vlan:13``": a VLAN tag.  This can only be used for VLANs, so the tag must
  be nonzero.  The tag is a number between 1 to 4094 inclusive.
* "``vlan:0x0d``": a VLAN tag in hexadecimal notation.  The valid range is from
  ``0x1`` to ``0xffe`` inclusive.  The notation is case-insensitive and leading
  zeroes are ignored.  So, ``vlan:0x0d``, ``vlan:0Xd``, ``vlan:0xD``, and
  ``vlan:0X0d`` are all equivalent to ``vlan:13``.
