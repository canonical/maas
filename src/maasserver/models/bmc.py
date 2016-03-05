# Copyright 2012-2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""BMC objects."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = [
    "BMC",
    ]

import re

from django.db import transaction
from django.db.models import (
    CharField,
    ForeignKey,
    PROTECT,
)
from django.db.models.signals import post_delete
from django.dispatch import receiver
from maasserver import DefaultMeta
from maasserver.enum import IPADDRESS_TYPE
from maasserver.fields import JSONObjectField
from maasserver.models.cleansave import CleanSave
from maasserver.models.staticipaddress import StaticIPAddress
from maasserver.models.subnet import Subnet
from maasserver.models.timestampedmodel import TimestampedModel
from provisioningserver.logger import get_maas_logger
from provisioningserver.power.schema import (
    POWER_FIELDS_BY_TYPE,
    POWER_PARAMETER_SCOPE,
    POWER_TYPE_PARAMETERS_BY_NAME,
)


maaslog = get_maas_logger("node")


class BMC(CleanSave, TimestampedModel):
    """A `BMC` represents an existing 'baseboard management controller'.  For
    practical purposes in MAAS, this is any addressable device that can control
    the power state of Nodes. The BMC associated with a Node is the one
    expected to control its power.

    Power parameters that apply to all nodes controlled by a BMC are stored
    here in the BMC. Those that are specific to different Nodes on the same BMC
    are stored in the Node model instances.

    :ivar ip_address: This `BMC`'s IP Address.
    :ivar power_type: The power type defines which type of BMC this is.
        Its value must match a power driver class name.
    :ivar power_parameters: Some JSON containing arbitrary parameters this
        BMC's power driver requires to function.
    :ivar objects: The :class:`BMCManager`.
    """

    class Meta(DefaultMeta):
        unique_together = ("power_type", "power_parameters", "ip_address")

    ip_address = ForeignKey(
        StaticIPAddress, default=None, blank=True, null=True, editable=False,
        on_delete=PROTECT)

    # The possible choices for this field depend on the power types advertised
    # by the rack controllers.  This needs to be populated on the fly, in
    # forms.py, each time the form to edit a node is instantiated.
    power_type = CharField(
        max_length=10, null=False, blank=True, default='')

    # JSON-encoded set of parameters for power control, limited to 32kiB when
    # encoded as JSON. These apply to all Nodes controlled by this BMC.
    power_parameters = JSONObjectField(
        max_length=(2 ** 15), blank=True, default='')

    def __unicode__(self):
        if self.ip_address:
            return "%s (%s)" % (self.id, self.ip_address)
        else:
            return self.id

    def clean_ip_from_power_parameters(self):
        """ If an IP address can be extracted from our power parameters, create
        or update our ip_address field and its subnet. """
        new_ip = BMC.extract_ip_address(self.power_type, self.power_parameters)
        old_ip = self.ip_address.ip if self.ip_address else None
        if new_ip != old_ip:
            if new_ip is None:
                # Set ip to None, save, then return the old ip.
                old_ip_address = self.ip_address
                self.ip_address = None
                return old_ip_address
            try:
                # Update or create StaticIPAddress.
                with transaction.atomic():
                    if self.ip_address:
                        self.ip_address.ip = new_ip
                        self.ip_address.save()
                        ip_address = self.ip_address
                    else:
                        ip_address = StaticIPAddress(
                            ip=new_ip, alloc_type=IPADDRESS_TYPE.STICKY)
                        ip_address.save()
                        self.ip_address = ip_address
            except Exception as error:
                maaslog.info(
                    "BMC could not save extracted IP "
                    "address '%s': '%s'", new_ip, error)
            else:
                # StaticIPAddress saved successfully - update the Subnet.
                subnet = Subnet.objects.get_best_subnet_for_ip(new_ip)
                if subnet is not None:
                    ip_address.subnet = subnet
                    ip_address.save()
        return None

    def clean(self, *args, **kwargs):
        super(BMC, self).clean(*args, **kwargs)
        self.old_ip_address = self.clean_ip_from_power_parameters()

    def save(self, *args, **kwargs):
        super(BMC, self).save(*args, **kwargs)
        if self.old_ip_address is not None:
            self.old_ip_address.delete()

    @staticmethod
    def scope_power_parameters(power_type, power_params):
        """Separate the global, bmc related power_parameters from the local,
        node-specific ones."""
        if not power_type:
            # If there is no power type, treat all params as node params.
            return ({}, power_params)
        power_fields = POWER_FIELDS_BY_TYPE.get(power_type)
        if not power_fields:
            # If there is no parameter info, treat all params as node params.
            return ({}, power_params)
        bmc_params = {}
        node_params = {}
        for param_name in power_params:
            power_field = power_fields.get(param_name)
            if (power_field and
                    power_field.get('scope') == POWER_PARAMETER_SCOPE.BMC):
                bmc_params[param_name] = power_params[param_name]
            else:
                node_params[param_name] = power_params[param_name]
        return (bmc_params, node_params)

    @staticmethod
    def extract_ip_address(power_type, power_parameters):
        """ Extract the ip_address from the power_parameters. If there is no
        power_type, no power_parameters, or no valid value provided in the
        power_address field, returns None. """
        if not power_type or not power_parameters:
            # Nothing to extract.
            return None
        power_type_parameters = POWER_TYPE_PARAMETERS_BY_NAME.get(power_type)
        if not power_type_parameters:
            maaslog.warning(
                "No POWER_TYPE_PARAMETERS for power type %s" % power_type)
            return None
        ip_extractor = power_type_parameters.get('ip_extractor')
        if not ip_extractor:
            maaslog.info(
                "No IP extractor configured for power type %s. "
                "IP will not be extracted." % power_type)
            return None
        field_value = power_parameters.get(ip_extractor.get('field_name'))
        if not field_value:
            maaslog.warning(
                "IP extractor field_value missing for %s" % power_type)
            return None
        extraction_pattern = ip_extractor.get('pattern')
        if not extraction_pattern:
            maaslog.warning(
                "IP extractor extraction_pattern missing for %s" % power_type)
            return None
        match = re.match(extraction_pattern, field_value)
        if match:
            return match.group('address')
        # no match found - return None
        return None

    def get_usable_rack_controllers(self, with_connection=True):
        """Return a list of `RackController`'s that have the ability to access
        this `BMC`."""
        ip_address = self.ip_address
        if ip_address is None or ip_address.ip is None or ip_address.ip == '':
            return set()

        # The BMC has a valid StaticIPAddress set. Make sure that the subnet
        # is correct for that BMC.
        subnet = Subnet.objects.get_best_subnet_for_ip(ip_address.ip)
        if subnet is not None and self.ip_address.subnet_id != subnet.id:
            self.ip_address.subnet = subnet
            self.ip_address.save()

        # Circular imports.
        from maasserver.models.node import RackController
        return RackController.objects.filter_by_url_accessible(
            ip_address.ip, with_connection=with_connection)

    def get_client_identifiers(self):
        """Return a list of indetifiers that can be used to get the
        `rpc.common.Client` for this `BMC`.

        :raise NoBMCAccessError: Raised when no rack controllers have access
            to this `BMC`.
        """
        rack_controllers = self.get_usable_rack_controllers()
        identifers = [
            controller.system_id
            for controller in rack_controllers
        ]
        return identifers


@receiver(post_delete)
def delete_bmc(sender, instance, **kwargs):
    """Clean up related ip_address when a BMC is deleted."""
    if sender == BMC:
        # Delete the related interfaces.
        if instance.ip_address is not None:
            instance.ip_address.delete()
