# Copyright 2015-2026 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""BMC objects."""

import re

from django.contrib.postgres.indexes import HashIndex
from django.db import transaction
from django.db.models import (
    BooleanField,
    CASCADE,
    CharField,
    ForeignKey,
    JSONField,
    Manager,
    ManyToManyField,
    SET_NULL,
)
from netaddr import AddrFormatError, IPAddress

from maasserver.enum import IPADDRESS_TYPE
from maasserver.models.cleansave import CleanSave
from maasserver.models.staticipaddress import StaticIPAddress
from maasserver.models.subnet import Subnet
from maasserver.models.timestampedmodel import TimestampedModel
from maasserver.rpc import getAllClients
from provisioningserver.drivers import SETTING_SCOPE
from provisioningserver.drivers.power.registry import (
    PowerDriverRegistry,
    sanitise_power_parameters,
)
from provisioningserver.logger import get_maas_logger

maaslog = get_maas_logger("node")


def create_bmc(**kwargs):
    power_type = kwargs.get("power_type")
    power_parameters = kwargs.get("power_parameters", {})

    power_parameters, secrets = sanitise_power_parameters(
        power_type, power_parameters
    )
    kwargs["power_parameters"] = power_parameters

    bmc = BMC.objects.create(**kwargs)

    if secrets:
        from maasserver.secrets import SecretManager

        SecretManager().set_composite_secret(
            "power-parameters", secrets, obj=bmc.as_bmc()
        )
    return bmc


def get_or_create_bmc(**kwargs):
    power_type = kwargs.get("power_type")
    power_parameters = kwargs.get("power_parameters", {})

    power_parameters, secrets = sanitise_power_parameters(
        power_type, power_parameters
    )
    kwargs["power_parameters"] = power_parameters

    bmc, created = BMC.objects.get_or_create(**kwargs)

    if created and secrets:
        from maasserver.secrets import SecretManager

        SecretManager().set_composite_secret(
            "power-parameters", secrets, obj=bmc.as_bmc()
        )

    return bmc, created


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

    class Meta:
        # power_type and power_parameters have indexes in addition of the
        # combined unique one as the unique one uses MD5 hash of the content
        # and would not be used for queries looking for exact content. Here we
        # use a HASH index to get around the size limitation on the content of
        # the indexed object
        indexes = [HashIndex(fields=["power_parameters"])]

    objects = Manager()

    ip_address = ForeignKey(
        StaticIPAddress,
        default=None,
        blank=True,
        null=True,
        editable=False,
        on_delete=SET_NULL,
    )

    # The possible choices for this field depend on the power types advertised
    # by the rack controllers.  This needs to be populated on the fly, in
    # forms.py, each time the form to edit a node is instantiated.
    power_type = CharField(
        max_length=10, null=False, blank=True, default="", db_index=True
    )

    # JSON-encoded set of parameters for power control, limited to 32kiB when
    # encoded as JSON. These apply to all Nodes controlled by this BMC.
    power_parameters = JSONField(max_length=(2**15), blank=True, default=str)

    created_by_commissioning = BooleanField(
        # We allow None, since before 3.2 we didn't track this, and we
        # don't know whether the BMC was created manually or
        # automatically by commissioning.
        null=True,
        default=False,
        editable=False,
    )

    # Rack controllers that have access to the BMC by routing instead of
    # having direct layer 2 access.
    routable_rack_controllers = ManyToManyField(
        "RackController",
        blank=True,
        editable=True,
        through="BMCRoutableRackControllerRelationship",
        related_name="routable_bmcs",
    )

    def __str__(self):
        return "{} ({})".format(
            self.id,
            self.ip_address if self.ip_address else "No IP",
        )

    def _as(self, model):
        """Create a `model` that shares underlying storage with `self`.

        In other words, the newly returned object will be an instance of
        `model` and its `__dict__` will be `self.__dict__`. Not a copy, but a
        reference to, so that changes to one will be reflected in the other.
        """
        new = object.__new__(model)
        new.__dict__ = self.__dict__
        return new

    def as_bmc(self):
        """Return a reference to self that behaves as a `BMC`."""
        return self._as(BMC)

    def as_self(self):
        """Return a reference to self that behaves as its own type."""
        return self.as_bmc()

    def delete(self):
        """Delete this BMC."""
        maaslog.info("%s: Deleting BMC", self)
        from maasserver.secrets import SecretManager

        SecretManager().delete_all_object_secrets(self.as_bmc())
        super().delete()

    def save(self, *args, **kwargs):
        """Save this BMC."""
        super().save(*args, **kwargs)

    def get_power_parameters(self):
        from maasserver.secrets import SecretManager

        power_parameters = self.power_parameters or {}
        return {
            **power_parameters,
            **SecretManager().get_composite_secret(
                "power-parameters", obj=self.as_bmc(), default={}
            ),
        }

    def set_power_parameters(self, power_parameters):
        power_parameters, secrets = sanitise_power_parameters(
            self.power_type, power_parameters
        )

        if secrets:
            from maasserver.secrets import SecretManager

            SecretManager().set_composite_secret(
                "power-parameters", secrets, obj=self.as_bmc()
            )
        self.power_parameters = power_parameters

    def clean(self):
        """Update our ip_address if the address extracted from our power
        parameters has changed."""
        new_ip = BMC.extract_ip_address(
            self.power_type, self.get_power_parameters()
        )
        current_ip = None if self.ip_address is None else self.ip_address.ip
        if new_ip != current_ip:
            if not new_ip:
                self.ip_address = None
            else:
                # Update or create a StaticIPAddress for the new IP.
                try:
                    # This atomic block ensures that an exception within will
                    # roll back only this block's DB changes. This allows us to
                    # swallow exceptions in here and keep all changes made
                    # before or after this block is executed.
                    with transaction.atomic():
                        subnet = Subnet.objects.get_best_subnet_for_ip(new_ip)
                        (self.ip_address, _) = StaticIPAddress.objects.exclude(
                            alloc_type=IPADDRESS_TYPE.DISCOVERED
                        ).get_or_create(
                            ip=new_ip,
                            defaults={
                                "alloc_type": IPADDRESS_TYPE.STICKY,
                                "subnet": subnet,
                            },
                        )
                except Exception as error:
                    maaslog.info(
                        "BMC could not save extracted IP address '%s': '%s'",
                        new_ip,
                        error,
                    )
                    raise error

    @staticmethod
    def scope_power_parameters(power_type, power_params):
        """Separate the global, bmc related power_parameters from the local,
        node-specific ones."""
        if not power_type:
            # If there is no power type, treat all params as node params.
            return (False, {}, power_params)
        power_driver = PowerDriverRegistry.get_item(power_type)
        if power_driver is None:
            # If there is no power driver, treat all params as node params.
            return (False, {}, power_params)
        power_fields = power_driver.settings
        if not power_fields:
            # If there is no parameter info, treat all params as node params.
            return (False, {}, power_params)
        bmc_params = {}
        node_params = {}
        for param_name in power_params:
            power_field = power_driver.get_setting(param_name)
            if power_field and power_field.get("scope") == SETTING_SCOPE.BMC:
                bmc_params[param_name] = power_params[param_name]
            else:
                node_params[param_name] = power_params[param_name]
        return (power_driver.chassis, bmc_params, node_params)

    @staticmethod
    def extract_ip_address(power_type, power_parameters):
        """Extract the ip_address from the power_parameters. If there is no
        power_type, no power_parameters, or no valid value provided in the
        power_address field, returns None."""
        if not power_type or not power_parameters:
            # Nothing to extract.
            return None
        power_driver = PowerDriverRegistry.get_item(power_type)
        if power_driver is None:
            maaslog.warning("No power driver for power type %s" % power_type)
            return None
        power_type_parameters = power_driver.settings
        if not power_type_parameters:
            maaslog.warning(
                "No power driver settings for power type %s" % power_type
            )
            return None
        ip_extractor = power_driver.ip_extractor
        if not ip_extractor:
            maaslog.info(
                "No IP extractor configured for power type %s. "
                "IP will not be extracted." % power_type
            )
            return None
        field_value = power_parameters.get(ip_extractor.get("field_name"))
        if not field_value:
            maaslog.warning(
                "IP extractor field_value missing for %s" % power_type
            )
            return None
        extraction_pattern = ip_extractor.get("pattern")
        if not extraction_pattern:
            maaslog.warning(
                "IP extractor extraction_pattern missing for %s" % power_type
            )
            return None
        match = re.match(extraction_pattern, field_value)
        if match:
            ip = match.group("address")
            # If we have a bracketed address, assume it's IPv6, and strip the
            # brackets.
            if ip.startswith("[") and ip.endswith("]"):
                ip = ip[1:-1]
            if ip == "":
                return ip
            # self.clean() attempts to map the return value of this method to
            # a subnet. If the user gives an FQDN or hostname the mapping fails
            # when Subnet.objects.get_best_subnet_for_ip() is called and an
            # exception is raised as an IP is expected. If the BMC does not
            # have an IP address MAAS will fall back on sending power requests
            # to all connected rack controllers.
            try:
                IPAddress(ip)
            except AddrFormatError:
                maaslog.info(
                    "BMC uses FQDN, power action will be sent to all "
                    "rack controllers"
                )
                return None
            else:
                return ip
        # no match found - return None
        return None

    def get_layer2_usable_rack_controllers(self, with_connection=True):
        """Return a list of `RackController`'s that have the ability to access
        this `BMC` directly through a layer 2 connection."""
        ip_address = self.ip_address
        if ip_address is None or ip_address.ip is None or ip_address.ip == "":
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
            ip_address.ip, with_connection=with_connection
        )

    def get_routable_usable_rack_controllers(self, with_connection=True):
        """Return a list of `RackController`'s that have the ability to access
        this `BMC` through a route on the rack controller."""
        routable_racks = [
            relationship.rack_controller
            for relationship in (
                self.routable_rack_relationships.all().select_related(
                    "rack_controller"
                )
            )
            if relationship.routable
        ]
        if with_connection:
            conn_rack_ids = [client.ident for client in getAllClients()]
            return [
                rack
                for rack in routable_racks
                if rack.system_id in conn_rack_ids
            ]
        else:
            return routable_racks

    def get_usable_rack_controllers(self, with_connection=True):
        """Return a list of `RackController`'s that have the ability to access
        this `BMC` either using layer2 or routable if no layer2 are available.
        """
        racks = self.get_layer2_usable_rack_controllers(
            with_connection=with_connection
        )
        if len(racks) == 0:
            # No layer2 routable rack controllers. Use routable rack
            # controllers.
            racks = self.get_routable_usable_rack_controllers(
                with_connection=with_connection
            )
        return racks

    def get_client_identifiers(self):
        """Return a list of identifiers that can be used to get the
        `rpc.common.Client` for this `BMC`.

        :raise NoBMCAccessError: Raised when no rack controllers have access
            to this `BMC`.
        """
        rack_controllers = self.get_usable_rack_controllers()
        identifers = [controller.system_id for controller in rack_controllers]
        return identifers

    def is_accessible(self):
        """If the BMC is accessible by at least one rack controller."""
        racks = self.get_usable_rack_controllers(with_connection=True)
        return len(racks) > 0

    def update_routable_racks(
        self, routable_racks_ids, non_routable_racks_ids
    ):
        """Set the `routable_rack_controllers` relationship to the new
        information."""
        BMCRoutableRackControllerRelationship.objects.filter(
            bmc=self.as_bmc()
        ).delete()
        self._create_racks_relationship(routable_racks_ids, True)
        self._create_racks_relationship(non_routable_racks_ids, False)

    def _create_racks_relationship(self, rack_ids, routable):
        """Create `BMCRoutableRackControllerRelationship` for list of
        `rack_ids` and wether they are `routable`."""
        # Circular imports.
        from maasserver.models.node import RackController

        for rack_id in rack_ids:
            rack = None
            try:
                rack = RackController.objects.get(system_id=rack_id)
            except RackController.DoesNotExist:
                # Possible it was delete before this call, but very very rare.
                continue
            BMCRoutableRackControllerRelationship(
                bmc=self, rack_controller=rack, routable=routable
            ).save()


class BMCRoutableRackControllerRelationship(CleanSave, TimestampedModel):
    """Records the link routable status of a BMC from a RackController.

    When a BMC is first created all rack controllers are check to see which
    have access to the BMC through a route (not directly connected).
    Periodically this information is updated for every rack controller when
    it asks the region controller for the machines it needs to power check.

    The `updated` field is used to track the last time this information was
    updated and if the rack controller should check its routable status
    again. A link will be created between every `BMC` and `RackController` in
    this table to record the last time it was checked and if it was `routable`
    or not.
    """

    bmc = ForeignKey(
        BMC, related_name="routable_rack_relationships", on_delete=CASCADE
    )
    rack_controller = ForeignKey(
        "RackController",
        related_name="routable_bmc_relationships",
        on_delete=CASCADE,
    )
    routable = BooleanField()
