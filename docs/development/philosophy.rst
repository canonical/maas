------------------
Philosophy of MAAS
------------------

This is a declaration of what we’re aiming for while designing and
developing MAAS. We may fall short in many regards right now, but this
is where we’re heading. Each fix, enhancement, and feature is
conceived and built with these principles in mind.

It is concise and to the point. If in doubt about including something,
don’t, or talk about it first. Think of it as a reference point for
the core development team, as well as a starting point for external
contributors.


Feedback loops
--------------

When MAAS modifies an external system there should be a feedback loop
so it can know the actual state of the external system, take periodic
or continuous action to converge the external system towards its
notion of truth, and notice when there are problems influencing the
external system.

For example, when sending out a command to boot a machine from the
network, MAAS should know that (a) the machine has actually powered
on, and (b) that it has obtained boot instructions from the TFTP
server.


UI
---

It should be possible to decompose all operations in the UI down to
API calls.

The UI need not have the same granularity as the API.

The UI should never do something that is not possible in the API
unless it is entirely specific to its medium (i.e. HTTP + browser).

Addendum: though the UI should be decomposable down to API calls, it
does not need to be implemented as such (even though it would be great
if it was).


.. TODO
   ----
   Security
   Persistence
   Testing
