# Copyright 2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Configuration relating to concurrency in the region controller.

This module is intended as a place to define concurrency policies for code
running in the region controller. Typically this will take the form of a
Twisted concurrency primative, like `DeferredLock` or `DeferredSemaphore`.

"""

from twisted.internet.defer import DeferredSemaphore

#
# Limit web application and threaded websocket handler requests.
#
# These requests are distinct from other work going on within the region
# because they hold a database connection for their entire duration. If they
# then, for example, initiate external IO like RPC calls they will block but
# leave the database connection idle. Database connections are a limited
# resource so this is bad for concurrency.
#
# It can even lead to deadlocks. Previously the cluster called back to the
# region with `UpdateNodePowerState` with the result of a `PowerQuery` RPC
# call. Servicing `UpdateNodePowerState` required a database connection. When
# the region was busy and lots of RPC calls were being made from threads
# holding database connections, this could mean the `UpdateNodePowerState`
# calls waited for a free database connection with no hope of ever receiving
# one.
#
# This example was fixed by changing the handler for `PowerQuery`, but
# unfortunately this pattern is not confined to `PowerQuery`. It's also an
# easy pattern to inadvertently reproduce, a hard one to diagnose, and not the
# only way to create a deadlock.
#
# So we limit the number of requests that are driven from threaded code that
# holds a database connection. This means that these requests will never
# saturate the available database connections on their own. If we expect each
# to consume at most one additional database connection, for example via the
# `PowerQuery` example then we should still be safe.
#
# It is imperfect: a thread could consume multiple additional database
# connections for example. It is a stopgap. Ultimately we want to reduce or
# eliminate all RPC calls made while a database connection is being held.
#
webapp = DeferredSemaphore(4)
