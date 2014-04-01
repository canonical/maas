maas-import-pxe-files
---------------------

USAGE
^^^^^

maas-import-pxe-files [-h, --help]

DESCRIPTION
^^^^^^^^^^^

This is a helper script for the MAAS software. It downloads Ubuntu
images and organises them for use by MAAS in commissioning nodes.
The script is usually run regularly by a cron task, though it
needs to be run manually the first time a MAAS system is installed.
Images that are already in place are kept unchanged, unless the
version in the archive has since been updated.  Only new data is
downloaded, so routine runs will not be costly.

An easier way to run the script is to trigger it from the MAAS web user
interface.  To do that, log in to your MAAS as an administrator using a
web browser, click the cogwheel icon in the top right of the page to go
to the Settings page, and click "Import boot images."  This will start
imports on all cluster controllers simultaneously.  The same thing can
also be done through the region-controller API, or through the
command-line interface.

The script reads a configuration file `/etc/maas/bootresources.yaml` in
order to determine:

* the location in the filesystem where downloaded images should be stored,
  and made available to nodes through TFTP and iSCSI;
* where boot images should be downloaded; and
* which kinds of images are needed: architecture, operating system
  release, etc.

These images are the minimum that's required to start installing a node.
During installation, a node may download its packages over the network.


Further Documentation
^^^^^^^^^^^^^^^^^^^^^
For more documentation of MAAS, please see https://maas.ubuntu.com/docs

See Also
^^^^^^^^
`maas-region-admin`, `maas`
