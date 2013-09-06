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
version in the archive has since been updated.

The script reads a configuration file /etc/maas/import_pxe_files in
order to determine:

**ARCHIVE:** 
Location of the Ubuntu download archive

**RELEASES:** 
Ubuntu releases to download

**ARCHES:** 
Architectures for which images should be downloaded

The script uses `wget` to download the kernel and initrd image for
each architecture in ARCHES and each release in RELEASES.  In addition 
it copies the Intel-architecture pre-boot loader `pxelinux.0` (plus 
some of its modules such as `chain.c32`) from its installed location in
/usr/lib/syslinux/.

These images are the minimum that's required to start installing a node.
During installation, a node may download its packages over the network.


Further Documentation
^^^^^^^^^^^^^^^^^^^^^
For more documentation of MAAS, please see https://maas.ubuntu.com/docs

See Also
^^^^^^^^
`maas`, `maas-cli`
