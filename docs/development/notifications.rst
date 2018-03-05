Notifications
=============

When you need to inform or warn users, administrators, or a specific
user about something that has happened or is happening, consider using
notifications. These can be created by code running in the region or via
the Web API if you're an administrator.

Tell all users that MAAS is on fire:

  >>> from maasserver.models.notification import Notification

  >>> Notification.objects.create_error_for_users("MAAS is on fire.")
  <Notification ERROR user=None users=True admins=True 'MAAS is ...>

Warn all admins that MAAS is taking on water:

  >>> Notification.objects.create_warning_for_admins(
  ...     "MAAS is taking on water.")
  <Notification WARNING user=None users=False admins=True ...>

Tell a specific user that they've won the lottery:

  >>> from maasserver.testing.factory import factory
  >>> user = factory.make_User()

  >>> Notification.objects.create_success_for_user(
  ...     "Congratulations {name}! You've won €10 in the lottery!",
  ...     user=user, context={"name": user.username})
  <Notification SUCCESS user='...' users=False admins=False ...>


Context
-------

A notification's ``context`` is a dict — saved into the database as JSON
— that gets interpolated into the message (new-style, not %-based).
What's its purpose?

  >>> Notification.objects.create_warning_for_admins(
  ...     "Disk space is low; only {amount:0.2f} GiB remaining.",
  ...     context={"amount": 1.3}, ident="disk-space-warning")
  <Notification WARNING user=None users=False admins=True 'Disk space ...'>

Later:

  >>> ds_warning = Notification.objects.get(ident="disk-space-warning")
  >>> ds_warning.context = {"amount": 0.8}
  >>> ds_warning.save()

This will update the message, live, in the browser, but will not show it
again to people that have dismissed it already.

This could be done by just changing the message! True, but the context
does give a convenient location for context of all kinds; it does not
have to be consumed by the message:

  >>> ii_warning = Notification.objects.create_warning_for_users(
  ...     "Image import from {url} has failed.",
  ...     ident="import:http://foobar.example.com/",
  ...     context={
  ...         "url": "http://foobar.example.com/",
  ...         "failures": ["2016-02-14 13:58:37"],
  ...     })

Later, after another failure:

  >>> ii_warning = Notification.objects.get(
  ...     ident="import:http://foobar.example.com/")
  >>> ii_warning.context = {
  ...      "url": "http://foobar.example.com/",
  ...      "failures": ["2016-02-14 13:58:37", "2016-02-14 16:58:02"],
  ...      "count": 2,
  ...      "hours": 3,
  ... }
  >>> ii_warning.message = (
  ...     "Image import from {url} has failed {count} times "
  ...     "in the last {hours} hours.")
  >>> ii_warning.save()
  >>> ii_warning.render()
  'Image import from http://foobar.example.com/ has
   failed 2 times in the last 3 hours.'


Rendering and HTML
------------------

As you can see, rendering the message and context should be done with
the ``render`` method:

  >>> ds_warning.render()
  'Disk space is low; only 0.80 GiB remaining.'

Why?

Notifications are primarily for a browser environment and so some
limited amount of HTML is tolerated — it's sanitised by AngularJS in the
UI so nothing fancy will get through.

The ``render`` method knows about this and allows HTML content in the
*message* through, but escapes the *context*:

  >>> ds_warning.message = "Hello <em>{name}</em>!"
  >>> ds_warning.context = {"name": "<script>nasty();</script>"}
  >>> ds_warning.render()
  'Hello <em>&lt;script&gt;nasty();&lt;/script&gt;</em>!'


Creating notifications
----------------------

There are many methods to create notifications


For a specific user:
^^^^^^^^^^^^^^^^^^^^

  >>> Notification.objects.create_error_for_user("abc", user)
  <Notification ERROR user='...' users=False admins=False 'abc'>
  >>> Notification.objects.create_warning_for_user("abc", user)
  <Notification WARNING user='...' users=False admins=False 'abc'>
  >>> Notification.objects.create_success_for_user("abc", user)
  <Notification SUCCESS user='...' users=False admins=False 'abc'>
  >>> Notification.objects.create_info_for_user("abc", user)
  <Notification INFO user='...' users=False admins=False 'abc'>


For all users:
^^^^^^^^^^^^^^

  >>> Notification.objects.create_error_for_users("abc")
  <Notification ERROR user=None users=True admins=True 'abc'>
  >>> Notification.objects.create_warning_for_users("abc")
  <Notification WARNING user=None users=True admins=True 'abc'>
  >>> Notification.objects.create_success_for_users("abc")
  <Notification SUCCESS user=None users=True admins=True 'abc'>
  >>> Notification.objects.create_info_for_users("abc")
  <Notification INFO user=None users=True admins=True 'abc'>

These methods create notifications that are visible to both users and
admins:

  >>> notification = Notification.objects.create_info_for_users("abc")
  >>> notification.users
  True
  >>> notification.admins
  True


For administrators:
^^^^^^^^^^^^^^^^^^^

  >>> Notification.objects.create_error_for_admins("abc")
  <Notification ERROR user=None users=False admins=True 'abc'>
  >>> Notification.objects.create_warning_for_admins("abc")
  <Notification WARNING user=None users=False admins=True 'abc'>
  >>> Notification.objects.create_success_for_admins("abc")
  <Notification SUCCESS user=None users=False admins=True 'abc'>
  >>> Notification.objects.create_info_for_admins("abc")
  <Notification INFO user=None users=False admins=True 'abc'>


For users and **not** administrators:
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Using the test factory, or by creating a ``Notification`` directly, it's
possible to create a notification that's only for users and not for
admins:

  >>> notification = factory.make_Notification(users=True, admins=False)
  >>> admin = factory.make_admin()
  >>> notification.is_relevant_to(admin)
  False

This isn't explicitly catered for in the model API. If you find a need
for this use case, adapt ``NotificationManager`` to accommodate it.


Finding notifications
---------------------

Finding notifications that are both:

- relevant to a particular user, and

- have not been dismissed by that user

should be done with ``find_for_user``:

  >>> list(Notification.objects.find_for_user(user))
  [<Notification ...]


Well-formed messages
--------------------

If you use HTML, don't forget to close tags and otherwise respect all
the proper rules of HTML.

Finally, punctuation. Don't forget to end notification messages with a
full-stop or exclamation mark!
