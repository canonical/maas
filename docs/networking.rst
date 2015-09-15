.. -*- mode: rst -*-

.. _networking:

=========================
Networking
=========================

.. note::

  This feature is available in MAAS versions 1.9 and above.

MAAS 1.9 adds support for the modeling of a wide variety of networking concepts
and configurations.

Networking Concepts
-------------------

At a high level, MAAS supports the following networking concepts:

Fabrics
^^^^^^^

A fabric is a set of interconnected VLANs that are capable of mutual
communication. A fabric can be thought of as a logical grouping in which VLANs
can be considered unique.

For example, a distributed network may have a fabric in London containing
VLAN 100, while a separate fabric in San Francisco may contain a VLAN 100,
whose attached subnets are completely different and unrelated.

A "Default Fabric" is created when MAAS is installed (or upgraded).

Subnets
^^^^^^^

A subnet is a "layer 3" network defined by a particular network prefix, plus
a network mask length (in bits). This notation is also referred to as a *CIDR*.

MAAS supports IPv4 and IPv6 subnets.

Examples::

    10.0.0.0/8
    172.16.0.0/12
    192.168.0.0/16
    2001:db8:4d41:4153::/64

Subnets can be annotated with a descriptive name, their default gateway,
and/or their DNS server(s).

A subnet can be in a single space.

Subnets are considered managed if a cluster interface specifies the cluster
network range.

VLANs
^^^^^

VLANs (Virtual LANs) are a common way to create logically separate networks
using the same physical infrastructure.

Managed switches can assign VLANs to each port in either a "tagged" or an
"untagged" manner. A VLAN is said to be "untagged" on a particular port when
it is the default VLAN for that port, and requires no special configuration
in order to access.

"Tagged" VLANs (traditionally used by network administrators in order to
aggregate multiple networks over inter-switch "trunk" lines) can also be used
with nodes in MAAS. That is, if a switch port is configured such that "tagged"
VLAN frames can be sent and received by a MAAS node, that MAAS node can be
configured to automatically bring up VLAN interfaces, so that the deployed node
can make use of them.

A "Default VLAN" is created for every Fabric, to which every new VLAN-aware
object in the fabric will be associated to by default (unless otherwise
specified).

Spaces
^^^^^^

A Space is a logical grouping of subnets that should be able to communicate
with each other. Subnets within each space need not belong to the same fabric.
For example, you may have a "DMZ" space in both your London and San Francisco
fabrics, and a "Storage" space to indicate subnets attached to your storage
network.

A "Default space" is created when MAAS is installed (or upgraded), which
every subnet will belong to by default (unless otherwise specified).

Interfaces
^^^^^^^^^^

**Physical**

After a node is commissioned, MAAS discovers its physical interfaces. In
addition, devices are created with physical interfaces.

Prior to deployment, a MAAS administrator can specify additional interfaces
to be configured on the node, including one or more of the below types.

**Bond**

A bond interface is capable of aggregating two or more physical interfaces
into a single logical interface. Bonds can be used in conjunction with a
managed switch (using Link Aggregation and Control Protocol, or LACP), or
independently (software bonds).

**VLAN**

A VLAN interface can be used to connect to a tagged VLAN, if the switch port
the node is connected to is authorized to access it.

**Unknown**

Unknown interfaces cannot be created by users.

Sometimes, *unknown* interfaces are discovered by MAAS. (For example, when
MAAS learns of a new DHCP lease that is not associated with any known node
or device.)

How to Configure Nodes for Networking
-------------------------------------

Creating a Bond Interface
^^^^^^^^^^^^^^^^^^^^^^^^^

Use the ``node-interfaces create-bond`` API to create a bond. For example::

    $ maas admin node-interfaces create-bond node-d83ce230-4b50-11e5-a267-00163eb185eb name=bond0 vlan=0 parents=30 parents=31 mac_address=00:50:56:2b:60:53
    Success.
    Machine-readable output follows:
    {
        "name": "bond0",
        "links": [],
        "tags": [],
        "vlan": {
            "id": 0,
            "resource_uri": "/MAAS/api/1.0/fabrics/0/vlans/0/",
            "name": "Default VLAN",
            "vid": 0,
            "fabric": "Default fabric"
        },
        "enabled": true,
        "id": 41,
        "parents": [
            "eth0",
            "eth1"
        ],
        "mac_address": "00:50:56:2b:60:53",
        "type": "bond",
        "children": [],
        "resource_uri": "/MAAS/api/1.0/nodes/node-d83ce230-4b50-11e5-a267-00163eb185eb/interfaces/41/"
    }

Note that in the example above, the bond contains two interfaces because
the ``parents`` parameter was specified twice, such as
``parents=30 parents=31``.

Creating a VLAN Interface
^^^^^^^^^^^^^^^^^^^^^^^^^

To create a VLAN interface, use the ``node-interfaces create-vlan`` API.

Be aware that the ``vlan`` paremeter does not indicate a VLAN ID that
corresponds to the VLAN tag. You must first create the VLAN, and then
associate it with the interface. For example::

    $ maas admin vlans create 0 name="Storage network" vid=100
    Success.
    Machine-readable output follows:
    {
        "id": 1,
        "resource_uri": "/MAAS/api/1.0/fabrics/0/vlans/1/",
        "name": "Storage network",
        "vid": 100,
        "fabric": "Default fabric"
    }

Note that the ``0`` in the command above indicates the ``fabric_id``. If you
have not defined any additional fabrics, the ``fabric_id`` of the default
fabric will be ``0``.

Now that a VLAN is created, it may be associated with a new interface::

    $ maas admin node-interfaces create-vlan node-d83ce230-4b50-11e5-a267-00163eb185eb vlan=1 parent=30
    Success.
    Machine-readable output follows:
    {
        "name": "eth0.100",
        "links": [],
        "tags": [],
        "vlan": {
            "id": 1,
            "resource_uri": "/MAAS/api/1.0/fabrics/0/vlans/1/",
            "name": "Storage network",
            "vid": 100,
            "fabric": "Default fabric"
        },
        "enabled": true,
        "id": 44,
        "parents": [
            "eth0"
        ],
        "mac_address": "00:50:56:2b:60:53",
        "type": "vlan",
        "children": [],
        "resource_uri": "/MAAS/api/1.0/nodes/node-d83ce230-4b50-11e5-a267-00163eb185eb/interfaces/44/"
    }


Deleting an Interface
^^^^^^^^^^^^^^^^^^^^^

To delete an interface, use the ``node-interface delete`` API. For example::

    $ maas admin node-interface delete node-d83ce230-4b50-11e5-a267-00163eb185eb 41
    Success.

