.. -*- mode: rst -*-

.. _dhcpsnippets:

=========================
DHCP Snippets
=========================

.. note::

  This feature is available in MAAS versions 2.0 and above. Modifications made
  directly to dhcpd.conf.template or dhcpd6.conf.template are no longer
  supported.

MAAS allows customizing dhcpd.conf and dhcpd6.conf through the use of DHCP
snippets. DHCP snippets are user defined dhcpd.conf configuration options which
are inserted into /var/lib/maas/dhcpd.conf and /var/lib/maas/dhcpd6.conf by
MAAS. Custom dhcpd.conf configuration options can be inserted either globally,
on a subnet, or on a node. For information about dhcpd.conf options refer to
the dhcpd.conf man or info page.

Creating a DHCP Snippet
-----------------------

Administrators can create DHCP Snippets over the API using the following command:::

  $ maas <profile> dhcpsnippets create name=<DHCP Snippet Name> value=<valid DHCP configuration options>

The name of the DHCP snippet will be added to /var/lib/maas/dhcpd.conf and
/var/lib/maas/dhcpd6.conf as a comment above the value. Optionally a
description can also be specified as such::

  $ maas <profile> dhcpsnippets create name=<DHCP Snippet Name> value=<valid DHCP configuration options> description=<DHCP Snippet description>

Global DHCP Snippets
^^^^^^^^^^^^^^^^^^^^

If no subnet or node is specified, the DHCP Snippet will be considered global.
A global DHCP Snippet is a configuration option which is applied to all VLANS,
subnets, and nodes. The global_snippet flag can also be used to force a DHCP
Snippet to be global::

  $ maas <profile> dhcpsnippets create name=<DHCP Snippet Name> value=<valid DHCP configuration options> global_snippet=true

Subnet DHCP Snippets
^^^^^^^^^^^^^^^^^^^^

DHCP Snippets can be applied only to a specific subnet as follows::

  $ maas <profile> dhcpsnippets create name=<DHCP Snippet Name> value=<valid DHCP configuration options> subnet=<subnet id or cidr>

Node DHCP Snippets
^^^^^^^^^^^^^^^^^^

DHCP Snippets can be applied only to a specific node. When a node is specified,
each snippet will be added to the host entry for each interface. A node can be
specified as follows::

  $ maas <profile> dhcpsnippets create name=<DHCP Snippet Name> value=<valid DHCP configuration options> node=<system_id or hostname>

DHCP Snippet Enablement
^^^^^^^^^^^^^^^^^^^^^^^

DHCP Snippets can be turned off by using the enabled flag option as follows::

  $ maas <profile> dhcpsnippets create name=<DHCP Snippet Name> value=<valid DHCP configuration options> enabled=false

Listing DHCP Snippets
---------------------

To list all DHCP Snippets use the following command::

  $ maas <profile> dhcpsnippets read

To list a particular DHCP Snippet use the following command.::

  $ maas <profile> dhcpsnippet read <DHCP Snippet id or name>

Updating a DHCP Snippet
-----------------------

Administrators can update the DHCP Snippet attributes using the following
command::

  $ maas <profile> dhcpsnippet update <DHCP Snippet id or name> <options>

DHCP Snippet Value History
--------------------------

MAAS stores the complete history of changes made to the DHCP Snippet's
value. MAAS only uses the latest revision of the value when writing
dhcpd.conf.

Reverting a Value
^^^^^^^^^^^^^^^^^

.. warning::
  Reverting a value will result in all later versions being deleted!

The revert operation allows the user to revert to a previous value. When
specifying what to revert to the user can either provide the value id or a
negative number representing how many revivisions to go back::

  $ maas <profile> dhcpsnippet revert <DHCP Snippet id or name> to=<value id or negative number>

Deleting a DHCP Snippet
-----------------------

Administrators can delete a DHCP Snippet using the following command::

  $ maas <profile> dhcpsnippet delete <DHCP Snippet id or name>
