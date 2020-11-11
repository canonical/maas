# Copyright 2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Testing helpers for dealing with signals."""

from fixtures import Fixture

from maasserver.models import signals


class SignalsDisabled(Fixture):
    """Disable all signals managed by `SignalsManager`.

    By convention, modules imported into `maasserver.models.signals` ought to
    have a ``signals`` attribute which is an instance of `SignalsManager`.
    """

    managers = {
        name: getattr(signals, name).signals for name in signals.__all__
    }

    def __init__(self, *disable):
        """Initialise a new `SignalsDisabled` fixture.

        :param disable: The signal managers to disable. Can be specified as
            names of managers or as `SignalsManager` instances. If no managers
            are specified, ALL managers will be disabled. If the manager is
            already disabled it will not be enabled at clean-up.
        """
        super().__init__()
        if len(disable) == 0:
            self.disable = self.managers.values()
        else:
            self.disable = {
                self.managers[d] if isinstance(d, str) else d for d in disable
            }

    def setUp(self):
        super().setUp()
        for manager in self.disable:
            if manager.enabled:
                self.addCleanup(manager.enable)
                manager.disable()
