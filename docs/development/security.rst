Fixing security-related issues in MAAS
======================================

The critical thing to remember is that details of the bug *must not
leak* before a package exists in the Ubuntu archive that fixes it.
Only then can details be unembargoed.

Here's a list, in order, of things we should do.

#. The initiator will be a security bug that is filed. Ensure that the
   bug is flagged as a security vulnerability, and is thusly
   **private**.

#. Notify the `Ubuntu Security Team`_ and subscribe them to the bug.

#. Discuss a fix for the bug in private, **not** public IRC channels!

#. When a fix has been decided, work out where it needs to land. It
   could be only trunk, or all of the released branches.

#. Make an empty branch from each release series and push up to LP.
   Mark the branch as *private security* **before** you then push up
   any revisions to it.

#. It's possible that the branch could be *public security* but better
   safe than sorry! The `Ubuntu Security Team`_ may advise.

#. Do a merge proposal as normal; it should remain private due to the
   private branch.

#. When finished, **do not** land the branch. Notify the `Ubuntu
   Server Team`_ and the `Ubuntu Security Team`_ that there is a patch
   available on the merge proposal (and subscribe the security team to
   it).

#. When they notify that the package(s) has/have been published to the
   archive, the branch(es) can now land on our upstream.


.. _Ubuntu Security Team: https://launchpad.net/~ubuntu-security

.. _Ubuntu Server Team: https://launchpad.net/~ubuntu-server
