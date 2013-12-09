=========
Changelog
=========

13.10
=====

Major new features
------------------

LLDP collection.
  MAAS now collects LLDP data on each node during its
  commissioning cycle.  The router to which the node is connected will have
  its MAC address parsed out of the data and made available for using as a
  placement constraint (passing connected_to or not_connected_to to the
  acquire() API call), or you can define tags using expressions such as
  ``//lldp:chassis/lldp:id[@type="mac"]/text() = "20:4e:7f:94:2e:10"``
  which would tag nodes with a router using that MAC address.

New faster installer for nodes.
  MAAS will now make use of the new Curtin_ installer which is much quicker
  than the old Debian Installer process.  Typically an installation now
  takes a couple of minutes instead of upwards of 10 minutes.  To have a node
  use the faster installer, add the ``use-fastpath-installer`` tag to it,
  or click the "Use the fast installer" button on the node page.

.. _Curtin: https://launchpad.net/curtin

More extensible templates for DHCP, power control, PXE and DNS.
  Templates supplied for these activities are now all in their own template
  file that is customisable by the user.  The files now generally live under
  /etc/maas/ rather than embedded in the code tree itself.

Minor feature changes
---------------------

Reworked ephemeral downloading
  While there is no end-user visible change, the ephemeral image download
  process is now driven by a data stream published by Canonical at
  http://maas.ubuntu.com/images/streams. In the future this will allow end
  users to use their own customised images by creating their own stream.
  The configuration for this is now also part of ``pserv.yaml``, obsoleting
  the maas_import_ephemerals configuration file.  The config will be auto-
  migrated on the first run of the ``maas-import-ephemerals`` script.

Improved maas-cli support
  Users can now manage their SSH keys and API credentials via the maas-cli
  tool.

Django 1.5
  MAAS is updated to work with Django 1.5

HP Moonshot Systems support.
  MAAS can now manage HP Moonshot Systems as any other hardware. However,
  in order for MAAS to power manage these systems, it requires the user
  to manually specify the iLO credentials before the enlistment process
  begins. This can be done in the ``maas_moonshot_autodetect.py``
  template under ``/etc/maas/templates/commissioning-user-data/snippets/``.

Bugs fixed in this release
--------------------------
#1039513  maas-import-pxe-files doesn't cryptographically verify what
it downloads

#1158425  maas-import-pxe-files sources path-relative config

#1204507  MAAS rejects empty files

#1208497  netboot flag defaults to 'true' on upgrade, even for allocated
nodes

#1227644  Releasing a node using the API errors with "TypeError:
00:e0:81:dd:d1:0b is not JSON serializable"

#1234853  MAAS returns HTTP/500 when adding a second managed interface
to cluster controller

#971349  With 100% of nodes in 'declared' state, pie chart is white on white

#974035  Node listing does not support bulk operations

#1045725  SAY clauses in PXE configs are being evaluated as they're
encountered, not when the label is branched to

#1054518  distro_series can be None or ""

#1064777  If a node's IP address is known, it's not shown anywhere

#1084807  Users are editing the machine-generated dhcpd.conf

#1155607  Conflict between "DNS zone name" in Cluster controller and
"Default domain for new nodes" in settings

#1172336  MAAS server reference to AvahiBoot wiki page that does not exist

#1185160  no way to see what user has a node allocated

#1202314  Discrepancy between docs and behavior

#1206222  Documentation Feedback and Site suggestions

#1209039  Document that MAAS requires 'portfast' on switch ports connected
to nodes

#1215750  No way of tracing/debugging http traffic content in the appserver.

#1223157  start_commissioning needlessly sets owner on commissioning nodes

#1227081  Error in apache's log "No handlers could be found for logger
"maasserver""

#1233069  maas-import-pxe-files fails when md5 checksums can't be downloaded

#1117415  maas dhcp responses do not have domain-name or domain-search

#1136449  maas-cli get-config and set-config documentation

#1175405  Pie chart says "deployed" which is inconsistent with the node
list's "allocated"

#1233833  Usability: deleting nodes is too easy

#1185897  expose ability to re-commission node in api and cli

#997092  Can't delete allocated node even if owned by self

