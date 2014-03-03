.. -*- mode: rst -*-

RPC HOWTO
=========

MAAS contains an RPC mechanism such that every process in the region is
connected to every process in the cluster (strictly, every pserv
process). It's based on AMP_, specifically `Twisted's implementation`_

.. _AMP:
  http://amp-protocol.net/

.. _Twisted's implementation:
  http://twistedmatrix.com/documents/current/core/howto/amp.html


Where do I start?
-----------------

Start in the ``provisioningserver.rpc`` package. The first two files to
look at are ``cluster.py`` and ``region.py``. This contain the
declarations of what commands are available on clusters and regions
respectively.

A simple new command could be declared like so::

  from twisted.protocols import amp

  class EatCheez(amp.Command):
      arguments = [
          (b"name", amp.Unicode()),
          (b"origin", amp.Unicode()),
      ]
      response = [
          (b"rating", amp.Integer()),
      ]

It's also possible to map exceptions across the wire using an ``errors``
attribute; see the docs or code for more information.

Note that byte-strings are used for parameter names. Twisted gets quite
fussy about this, so remember to do it.


Implementing commands
---------------------

To implement a new command on the cluster, see the class
``provisioningserver.rpc.clusterserver.Cluster``. A method decorated
with ``@cluster.EatCheez.responder`` is the implementation of the
``EatCheez`` command. There's no trick to this, they're just plain old
functions. However:

* They only receive named parameters, so the arguments *must* match the
  names used in the command's ``arguments`` declaration.

* They *must* return a dict that matches the command's ``response``
  declararation.

* If the ``response`` declaration is empty they *must* still return an
  empty dict.

To implement a new command on the region, see the class
``maasserver.rpc.regionserver.Region``. It works the same.


Making remote calls from the region to the cluster
--------------------------------------------------

There's a convenient API in ``maasserver.rpc``:

* ``getClientFor(uuid)`` returns a client for calling remote functions
  against the cluster identified by the specified UUID.

* ``getAllClients()`` will return clients for all connections cluster
  processes.


Making remote calls from the cluster to the region
--------------------------------------------------

You need to get a handle to the ``rpc`` service that will have been
started by ``twistd``.

Probably the best way to do this is implement the behaviour you want as
a new service, start it up via same mechanism as the ``rpc`` service
(see ``provisioningserver.plugin``, and pass over a reference.

Then call ``getClient()``, and you will get a client for calling into a
region process. You're given a random client.


Miscellaneous advice
--------------------

* Don't hang onto client objects for long periods of time. It's okay for
  a sequence of operations, but don't keep one around as a global, for
  example; get a new one each time.

* It's a distributed system; errors are going to be normal, so be
  prepared.
