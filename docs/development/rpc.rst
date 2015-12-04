.. -*- mode: rst -*-

RPC HOWTO
=========

MAAS contains an RPC mechanism such that every process in the region is
connected to every process in the cluster (strictly, every pserv
process). It's based on AMP_, specifically `Twisted's implementation`_.

.. _AMP:
  http://amp-protocol.net/

.. _Twisted's implementation:
  http://twistedmatrix.com/documents/current/core/howto/amp.html


Where do I start?
-----------------

Start in the :py:mod:`provisioningserver.rpc` package. The first two files to
look at are ``cluster.py`` and ``region.py``. This contain the
declarations of what commands are available on clusters and regions
respectively.

A new command could be declared like so::

  from provisioningserver.twisted.protocols import amp

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
:py:class:`provisioningserver.rpc.clusterserver.Cluster`. A method decorated
with ``@cluster.EatCheez.responder`` is the implementation of the
``EatCheez`` command. There's no trick to this, they're just plain old
functions. However:

* They only receive named parameters, so the arguments *must* match the
  names used in the command's ``arguments`` declaration.

* They *must* return a dict that matches the command's ``response``
  declaration.

* If the ``response`` declaration is empty they *must* still return an
  empty dict.

To implement a new command on the region, see the class
:py:class:`maasserver.rpc.regionserver.Region`. It works the same.


Making remote calls from the region to the cluster
--------------------------------------------------

There's a convenient API in :py:mod:`maasserver.rpc`:

* :py:func:`~maasserver.rpc.getClientFor` returns a client for calling
  remote functions against the cluster identified by a specified UUID.

* :py:func:`~maasserver.rpc.getAllClients` will return clients for all
  connections to cluster processes.

The clients returned are designed to be used in either the reactor
thread *or* in another thread; when called from the latter, a
:py:class:`crochet.EventualResult` will be returned.


Making remote calls from the cluster to the region
--------------------------------------------------

You need to get a handle to the ``rpc`` service that will have been
started by ``twistd``.

Probably the best way to do this is implement the behaviour you want as
a new service, start it up via same mechanism as the ``rpc`` service
(see :py:mod:`provisioningserver.plugin`, and pass over a reference.

Then call :py:func:`~provisioningserver.rpc.getClient`, and you will get
a client for calling into a region process. You're given a random
client.


Making multiple calls at the same time from outside the reactor
---------------------------------------------------------------

A utility function -- :py:func:`~maasserver.utils.async.gather` -- helps
here. An example::

  from functools import partial

  from maasserver.rpc import getAllClients
  from maasserver.utils import async
  from twisted.python.failure import Failure

  # Wrap those calls you want to make into no-argument callables, but
  # don't call them yet.
  calls = [
      partial(client, EatCheez)
      for client in getAllClients()
  ]

  # Use gather() to issue all the calls simultaneously and process the
  # results as they come in. Note that responses can be failures too.
  for response in async.gather(calls, timeout=10):
      if isinstance(response, Failure):
          pass  # Do something sensible with this.
      else:
          celebrate_a_cheesy_victory(response)

Responses can be processed as soon as they come in. Any responses not
received within ``timeout`` seconds will be discarded.


Miscellaneous advice
--------------------

* Don't hang onto client objects for long periods of time. It's okay for
  a sequence of operations, but don't keep one around as a global, for
  example; get a new one each time.

* It's a distributed system, and errors are going to be normal, so be
  prepared.


API
---


Controlling the event-loop in region controllers
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. automodule:: maasserver.eventloop


RPC declarations for region controllers
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. automodule:: provisioningserver.rpc.region


RPC implementation for region controllers
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. autoclass:: maasserver.rpc.regionservice.Region


RPC declarations for cluster controllers
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. automodule:: provisioningserver.rpc.cluster


RPC implementation for cluster controllers
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. autoclass:: provisioningserver.rpc.clusterservice.Cluster


Helpers
^^^^^^^

.. autofunction:: maasserver.rpc.getAllClients
.. autofunction:: maasserver.rpc.getClientFor
.. autofunction:: maasserver.utils.async.gather

.. automethod:: provisioningserver.rpc.clusterservice.ClusterClientService.getClient
