The Metadata API
================

A MAAS region controller provides a separate API (the metadata API) for the
benefit of the nodes themselves.  This is where a node obtains the details of
how it should be set up, such as which SSH keys should be installed in order to
give a particular user remote access to the system.

As a MAAS user or administrator, you do not need to request this information
yourself.  It is normally up to ``cloud-init`` to do this while setting up the
node.  You'll find more about how this works in cloud-init's datasources_
documentation.

.. _datasources: http://cloudinit.readthedocs.org/en/latest/topics/datasources.html


Similarity to EC2
-----------------

The metadata API is very similar, and partly identical, to the EC2 metadata
service.  It follows a similar directory structure and provides several items
in the same formats.  For example, in order to find out its own host name, a
node would perform an http GET request for::

  /2012-03-01/meta-data/local-hostname

The first item in the path is the API version.  The API has been extended since
March 2012, but not changed incompatibly and so that date is still the current
version number.

The items following that form a directory hierarchy based on that of the EC2
metadata service.  The metadata service "knows" which node makes the request,
and so there is no need for the request URL to identify the node whose hostname
should be retrieved.  The request automatically returns the hostname for the
node which requested it.

Just like EC2, the MAAS metadata API will accept GET requests to::

  /
  /2012-03-01/
  /2012-03-01/meta-data/
  /2012-03-01/meta-data/instance-id
  /2012-03-01/meta-data/local-hostname
  /2012-03-01/meta-data/public-keys
  /2012-03-01/user-data

Hopefully their meanings are fairly obvious.  The ``public-keys`` will contain
the user's SSH keys.

MAAS adds a tarball of scripts that a node should run during its commissioning
phase::

  /2012-03-01/meta-data/maas-commissioning-scripts

There are other differences.  Where EC2 makes the metadata service available at
a fixed IP address, MAAS configures the location of the metadata service on the
node while installing its operating system.  It does this through installation
:ref:`preseeds <preseeds>`.  These preseeds also include the node's access
credentials.


Additional Directory Trees
--------------------------

.. _enlistment-tree:

MAAS adds some entirely new directories as well.  An enlisting node
(which does not have access credentials for the metadata API yet) can
anonymously request the same items for itself under ``/enlist/``, e.g.::

  /enlist/2012-03-01/meta-data/local-hostname

If you set the ``ALLOW_UNSAFE_METADATA_ACCESS`` configuration item, the
metadata service will also provide the information on arbitrary nodes to
authenticated users under a separate sub-tree.  For security reasons this is
not recommended, but it may be useful in debugging.  With this option enabled,
the information for the node with MAC address 99:99:99:99:99:99 is available
at::

  /2012-03-01/by-mac/99:99:99:99:99:99/meta-data/local-hostname

And so on for the other information.  There is a similar facility keyed by
MAAS system identifiers.

.. _curtin-tree:

Finally, a curtin-specific metadata API with largely the same information lives
in the ``/curtin/`` subtree::

  /curtin/2012-03-01/meta-data/local-hostname

The curtin subtree however differs in the ``user-data`` endpoint.  It returns a
curtin-specific form of user data.


Authentication
--------------

Most metadata requests are authenticated similar to ones to the
region-controller API, through OAuth.  Every node in a MAAS has its own OAuth
key.  (On the region controller side, these keys collectively belong to a
single special user called ``node-init``.  You will not see such special users
listed in the UI, however.)  When a node asks for information about itself, the
OAuth key is what tells the metadata service which node that is.

Not all requests are authenticated in this way.  For instance, a node can
access the items under the enlistment subdirectory (see
:ref:`above <enlistment-tree>`) anonymously.  The metadata service will
identify the requesting node by its IP address.


API Operations
--------------

The MAAS metadata API supports a few non-GET operations.  These work just like
the ones on the main :ref:`region-controller API <region-controller-api>`, but they are meant to be invoked by
nodes.  The URL for these calls is ``/2013-03-01/``, and the operation name is
passed as a multipart form item called "op".  Other parameters are passed in
the same way.

The ``signal`` call notifies the region controler of the state of a
commissioning node.  The node sends running updates, as well as output produced
by the commissioning scripts, and finally completion information through this
call.

When a node is done installing, it may call POST operations ``netboot_on`` and
``netboot_off`` to instruct MAAS to enable or disable its network boot setting.
