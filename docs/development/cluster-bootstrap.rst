Bootstrapping a cluster
=======================


Considerations
--------------

A new cluster needs to register itself with the region. At the same
moment that it's accepted by the region, the region starts configuring
it via RPC, so we need an RPC connection open when registering.

Before a cluster is accepted, we want to restrict the available RPC
calls to a small set, both on the region and the cluster.

Before a cluster is accepted, we also do not want to start some services
on the cluster, like lease uploads, DHCP scanning, and so forth, because
the region will reject interaction from them.


Start-up procedure
------------------

This procedure will be followed by existing clusters and new clusters
alike:

#. Cluster starts.

#. If shared secret not available, shutdown, **DONE**.

#. ``ClusterClientService`` starts.

#. Services other than log and oops are **not** started.

#. Wait for a connection to the region to become available.

#. Do not allow any RPC calls other than ``Identify`` and ``Authenticate``.

#. Call ``Identify``.

#. Call ``Authenticate``.

   - On success, continue.

   - On failure, shutdown, **DONE**.

#. Permit all other RPC calls.

   - This allows for side-effects from calling ``Register`` next, like DHCP
     configuration.

#. Call ``Register``. Region accepts cluster.

#. Start all services.

#. **DONE**.


Work items
----------

#. **DONE:** Add ``Authenticate`` RPC call.

#. **DONE:** Add ``Register`` RPC call.

#. **DONE:** Command-line to install shared-secret.

#. **DONE:** Check for shared-secret during start-up (packaging change too?).

#. Perform ``Authenticate`` handshake.

#. Perform ``Register`` handshake.

#. Mechanism to limit available RPC calls.

#. Mechanism to defer start-up of "full" services.
