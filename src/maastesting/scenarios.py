# Copyright 2012-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Adapting `testscenarios` to work with MAAS."""

import testscenarios


class WithScenarios(testscenarios.WithScenarios):
    """Variant of testscenarios_' that provides ``__call__``.

    Some sadistic `TestCase` implementations (cough, Django, cough) treat
    ``__call__`` as something other than a synonym for ``run``. This means
    that testscenarios_' ``WithScenarios``, which customises ``run`` only,
    does not work correctly.

    If you're using the `maastesting.noseplug.Scenarios` plugin with Nose
    (``--with-scenarios``) then this won't do anything because scenarios will
    have already been expanded. This remains here for use with other test
    runners.

    .. testscenarios_: https://launchpad.net/testscenarios
    """

    def __call__(self, result=None):
        if self._get_scenarios():
            for test in testscenarios.generate_scenarios(self):
                test.__call__(result)
        else:
            super().__call__(result)
