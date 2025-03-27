#  Copyright 2025 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).
from maasserver.models import Config, Controller


def update_interface_monitoring(network_discovery_config_value):
    """Updates the global state of interface monitoring."""
    # This is not really ideal, since we don't actually know if any of these
    # configuration options actually changed. Also, this function may be called
    # more than once (for each global setting) when the form is submitted, no
    # matter if anything changed or not. (But a little repitition for the sake
    # of simpler code is a good tradeoff for now, given that there will be a
    # relatively small number of Controller interfaces.
    discovery_config = Config.objects.get_network_discovery_config_from_value(
        network_discovery_config_value
    )
    # We only care about Controller objects, since only Controllers run the
    # networks monitoring service.
    for controller in Controller.objects.all():
        controller.update_discovery_state(discovery_config)
