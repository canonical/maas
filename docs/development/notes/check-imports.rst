.. -*- mode: rst -*-

****************
Checking imports
****************


**2016-03-03, allenap**

``utilities/check-imports`` is a static import checker that replaces
``maasfascist``, which intercepted imports at runtime.

The latter sounds like it would be more effective, but it didn't work
out in practice. Working as an import hook means it could only ever
intercept the *first* import of a module. Often the code doing the
importing was core Django, as it pulled in applications. It was not
possible to, for example, impose a different policy on migrations,
because these only ever run after Django has imported the world.

``maasfascist`` was fiddly in other ways. When walking the stack, you
find some frames without associated modules (this seems to be new to
Python 3) or you find multiple frames belonging to importlib or modules
related to its workings. The code was getting unwieldy and slow. In
addition, the import hook API that ``maasfascist`` used had been updated
in Python 3, so there was work on the table to update it (Python 3 still
runs old hooks, but the old API is, AFAIK, already deprecated).

I decided to cut losses and switch to a static check. It won't detect
abuses of policy via ``exec()`` or ``importlib``, but we can deal with
those in review; they're not techniques we make much use of.

``check-imports`` examines the AST of every file for which policy has
been defined, extracting all imports. These are normalised into fully-
qualified names and tested against policy.

Policy is quite simple: sets of files are each associated with a
``Rule``. These are defined within ``utilities/check-imports`` itself.
For example::

  # The set of test-only files.
  Tests = files(
      "src/**/test_*.py",
      "src/**/testing/**/*.py",
      "src/**/testing.py")

  # The set of apiclient files.
  APIClient = files("src/apiclient/**/*.py")

  # See check-imports for the definitions of these:
  StandardLibraries = Pattern(...)
  TestingLibraries = Pattern(...)

  # A list of (files, rule) tuples that define the policy to be applied.
  # Below, the first tuple defines the policy that will be applied to
  # distributed apiclient code, the second is the policy for apiclient's
  # tests.
  checks = [
      (
          APIClient - Tests,
          Rule(
              Allow("apiclient|apiclient.**"),
              Allow("django.utils.**"),
              Allow("oauth.oauth"),
              Allow(StandardLibraries),
          ),
      ),
      (
          APIClient & Tests,
          Rule(
              Allow("apiclient|apiclient.**"),
              Allow("django.**"),
              Allow("oauth.oauth"),
              Allow("piston3|piston3.**"),
              Allow(StandardLibraries),
              Allow(TestingLibraries),
          ),
      ),
      ...
  ]

There are two possible *actions*: ``Allow`` and ``Deny``. The latter
isn't used in any policy so far, but that's because imports are denied
by default. Actions are initialised with patterns:

* ``Allow("foo.bar")`` allows for ``import foo.bar`` **or** ``from foo
  import bar`` but **not** for ``import foo.bar.baz``.

* ``Allow("foo.bar.*")`` allows for ``import foo.bar.baz`` **or** ``from
  foo.bar import bar``, but **not** for ``import foo.bar`` and **not**
  ``from foo.bar.baz import thing``, i.e. it allows for any name within
  ``foo.bar`` to be imported.

* ``Allow("foo.bar.**")`` allows for ``import foo.bar.baz`` **or**
  ``from foo.bar import bar`` **or** ``import foo.bar.alice.bob.carol``,
  i.e. it allows for any name or submodule of ``foo.bar`` to be
  imported.

* ``Allow("foo.bar|foo.bar.**")`` allows allows ``foo.bar`` **or** for
  any name or submodule of ``foo.bar`` to be imported.

* ``Allow(Pattern("foo"))`` is equivalent to ``Allow("foo")``. You can
  pre-create ``Pattern`` instances and ``Allow`` or ``Deny`` them as
  necessary.

Multiple patterns can be passed to ``Allow`` or ``Deny``, either as
separate strings — ``Allow("foo", "bar")`` — or combined using ``|`` as
above.

Any number of actions are wrapped up into a ``Rule``::

  rule = Rule(Allow("foo"), Allow("bar"))

Rules can also be combined using ``|``::

  rule = Rule(Allow("foo")) | Rule(Allow("bar"))

You'll see examples of this in ``check-imports``.

Having said all that, the best way to learn this is to find yourself at
the sharp end of ``check-import``'s policy and having to add the rule to
permit what you need.

I've already discovered `bug 1547874`_ and `bug 1547877`_ with
``check-imports``, but it should now *prevent* bugs like that.

.. _bug 1547874: https://bugs.launchpad.net/maas/+bug/1547874
.. _bug 1547877: https://bugs.launchpad.net/maas/+bug/1547877

Another goal for ``check-imports`` is to inhibit the use of application
code from within Django-native migrations, which I expect it to play out
something like: first, we replace all imports of application code in
existing (non-South) migrations with *copies* of the imported code;
second, we tighten up the import rules to prevent future migrations from
landing with application imports, so that we don't forget to copy code
in when generating new migrations.

``check-imports`` is called by `make lint` so it should become part of
your workflow without any change necessary.
