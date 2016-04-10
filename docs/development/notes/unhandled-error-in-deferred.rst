.. -*- mode: rst -*-

***************************
Unhandled error in Deferred
***************************


**2016-03-16, allenap**

Last night I saw an *Unhandled error in Deferred* message when running
``bin/test.rack`` and it took me a while to figure it out. I managed to
track it down to the following code::

    def test_chassis_type_unknown_logs_error_to_maaslog(self):
        fake_error = factory.make_name('error')
        self.patch(clusterservice, 'maaslog')
        mock_deferToThread = self.patch_autospec(
            clusterservice, 'deferToThread')
        mock_deferToThread.return_value = fail(Exception(fake_error))
        ...

What's the matter with that? That's not obviously problematic.

``fail(an_exception)`` creates a Deferred that's itching to call an
errback with the given error. In this test nothing was ever calling the
mocked ``deferToThread``, so no errback was ever called, and Twisted
complained about it when the Deferred was garbage collected.

``deferToThread`` was mocked here as belt-n-braces: if the method under
test did not follow the expected execution path this mock would prevent
real work being done in a thread.

In this case I felt it was safe to omit it:

.. code-block:: udiff

       def test_chassis_type_unknown_logs_error_to_maaslog(self):
  -        fake_error = factory.make_name('error')
           self.patch(clusterservice, 'maaslog')
  -        mock_deferToThread = self.patch_autospec(
  -            clusterservice, 'deferToThread')
  -        mock_deferToThread.return_value = fail(Exception(fake_error))

but I could have fixed it like so:

.. code-block:: udiff

       def test_chassis_type_unknown_logs_error_to_maaslog(self):
  -        fake_error = factory.make_name('error')
  +        fake_error = factory.make_exception()
           self.patch(clusterservice, 'maaslog')
           mock_deferToThread = self.patch_autospec(
               clusterservice, 'deferToThread')
  -        mock_deferToThread.return_value = fail(Exception(fake_error))
  +        mock_deferToThread.side_effect = lambda: fail(fake_error)

or:

.. code-block:: udiff

  ...
  -        mock_deferToThread.return_value = fail(Exception(fake_error))
  +        mock_deferToThread.side_effect = always_fail_with(fake_error)

Either way, no Deferred would be created in an error state unless there
is a consumer for it. An *Unhandled error* warning seen after that would
be a legitimate bug.
