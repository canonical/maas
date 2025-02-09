# Copyright 2015-2021 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""BMC objects."""

from collections import defaultdict
from functools import partial
import re
from statistics import mean

from django.contrib.postgres.fields import ArrayField
from django.contrib.postgres.indexes import HashIndex
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.validators import MinValueValidator
from django.db import transaction
from django.db.models import (
    BigIntegerField,
    BooleanField,
    CASCADE,
    CharField,
    FloatField,
    ForeignKey,
    IntegerField,
    JSONField,
    Manager,
    ManyToManyField,
    PROTECT,
    SET_DEFAULT,
    SET_NULL,
    TextField,
)
from django.db.models.query import QuerySet
from django.shortcuts import get_object_or_404
from netaddr import AddrFormatError, IPAddress
import petname
from twisted.internet.defer import inlineCallbacks

from maasserver.clusterrpc.pods import decompose_machine
from maasserver.enum import (
    BMC_TYPE,
    BMC_TYPE_CHOICES,
    INTERFACE_TYPE,
    IPADDRESS_TYPE,
    NODE_STATUS,
    NODE_TYPE,
)
from maasserver.exceptions import PodProblem
from maasserver.models.blockdevice import BlockDevice
from maasserver.models.cleansave import CleanSave
from maasserver.models.fabric import Fabric
from maasserver.models.interface import PhysicalInterface, VLANInterface
from maasserver.models.node import get_default_zone, Machine, Node
from maasserver.models.physicalblockdevice import PhysicalBlockDevice
from maasserver.models.podhints import PodHints
from maasserver.models.podstoragepool import PodStoragePool
from maasserver.models.resourcepool import ResourcePool
from maasserver.models.staticipaddress import StaticIPAddress
from maasserver.models.subnet import Subnet
from maasserver.models.tag import Tag
from maasserver.models.timestampedmodel import TimestampedModel
from maasserver.models.vlan import VLAN
from maasserver.models.zone import Zone
from maasserver.permissions import PodPermission
from maasserver.rpc import getAllClients, getClientFromIdentifiers
from maasserver.utils.orm import transactional
from maasserver.utils.threads import deferToDatabase
from metadataserver.enum import RESULT_TYPE
from provisioningserver.drivers import SETTING_SCOPE
from provisioningserver.drivers.pod import (
    DiscoveredPodHints,
    InterfaceAttachType,
)
from provisioningserver.drivers.power.registry import (
    PowerDriverRegistry,
    sanitise_power_parameters,
)
from provisioningserver.enum import MACVLAN_MODE_CHOICES
from provisioningserver.logger import get_maas_logger
from provisioningserver.utils.constraints import LabeledConstraintMap
from provisioningserver.utils.network import get_ifname_for_label
from provisioningserver.utils.twisted import asynchronous

maaslog = get_maas_logger("node")
podlog = get_maas_logger("pod")


def get_requested_ips(requested_machine):
    """Creates a map of requested IP addresses, given a RequestedMachine."""
    if requested_machine is not None:
        requested_ips = {
            interface.ifname: interface.requested_ips
            for interface in requested_machine.interfaces
            if (
                interface.ifname is not None
                and len(interface.requested_ips) > 0
            )
        }
    else:
        requested_ips = {}
    return requested_ips


def get_ip_modes(requested_machine):
    """Creates a map of requested IP modes, given a RequestedMachine."""
    if requested_machine is not None:
        ip_modes = {
            interface.ifname: interface.ip_mode
            for interface in requested_machine.interfaces
            if (interface.ifname is not None and interface.ip_mode is not None)
        }
    else:
        ip_modes = {}
    return ip_modes


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


class BaseBMCManager(Manager):
    """A utility to manage the collection of BMCs."""

    extra_filters = {}

    def get_queryset(self):
        queryset = QuerySet(self.model, using=self._db)
        return queryset.filter(**self.extra_filters)


class BMCManager(BaseBMCManager):
    """Manager for `BMC` not `Pod`'s."""

    extra_filters = {"bmc_type": BMC_TYPE.BMC}


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

    bmcs = BMCManager()

    bmc_type = IntegerField(
        choices=BMC_TYPE_CHOICES, editable=False, default=BMC_TYPE.DEFAULT
    )

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

    # Rack controllers that have access to the BMC by routing instead of
    # having direct layer 2 access.
    routable_rack_controllers = ManyToManyField(
        "RackController",
        blank=True,
        editable=True,
        through="BMCRoutableRackControllerRelationship",
        related_name="routable_bmcs",
    )

    # Name of the pod.
    name = CharField(max_length=255, default="", blank=True, unique=False)

    version = TextField(default="", blank=True)

    # Architectures this pod supports.
    architectures = ArrayField(
        TextField(), blank=True, null=True, default=list
    )

    # Pod capabilities.
    capabilities = ArrayField(TextField(), blank=True, null=True, default=list)

    # Number of cores in the pod.
    cores = IntegerField(blank=False, null=False, default=0)

    # Fastest CPU in the pod (MHz).
    cpu_speed = IntegerField(blank=False, null=False, default=0)

    # Total memory in the pod (XXX: units?).
    memory = IntegerField(blank=False, null=False, default=0)

    # Total storage available in the pod (bytes).
    local_storage = BigIntegerField(blank=False, null=False, default=0)

    # Resource pool for this pod.
    pool = ForeignKey(
        ResourcePool,
        default=None,
        null=True,
        blank=True,
        editable=True,
        on_delete=PROTECT,
    )

    # Physical zone this pod is in.
    zone = ForeignKey(
        Zone,
        verbose_name="Physical zone",
        default=get_default_zone,
        editable=True,
        db_index=True,
        on_delete=SET_DEFAULT,
    )

    # Tags for this pod.
    tags = ArrayField(TextField(), blank=True, null=True, default=list)

    # CPU over-commit ratio.
    cpu_over_commit_ratio = FloatField(
        default=1, validators=[MinValueValidator(0)]
    )

    # Memory over-commit ratio.
    memory_over_commit_ratio = FloatField(
        default=1, validators=[MinValueValidator(0)]
    )

    # Default storage pool for the pod.
    default_storage_pool = ForeignKey(
        PodStoragePool,
        null=True,
        blank=True,
        related_name="+",
        on_delete=SET_NULL,
    )

    # Default MACVLAN mode for the pod.
    # This is used as the default macvlan mode when a user wants
    # to create a macvlan interface for a VM.
    default_macvlan_mode = CharField(
        max_length=32,
        null=True,
        blank=True,
        default=None,
        choices=MACVLAN_MODE_CHOICES,
    )

    created_with_trust_password = BooleanField(
        null=True,
        default=None,
        editable=False,
    )
    created_with_maas_generated_cert = BooleanField(
        null=True,
        default=None,
        editable=False,
    )
    created_with_cert_expiration_days = IntegerField(
        null=True,
        default=None,
        editable=False,
    )
    created_by_commissioning = BooleanField(
        # We allow None, since before 3.2 we didn't track this, and we
        # don't know whether the BMC was created manually or
        # automatically by commissioning.
        null=True,
        default=False,
        editable=False,
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

    def as_pod(self):
        """Return a reference to self that behaves as a `Pod`."""
        return self._as(Pod)

    _as_self = {BMC_TYPE.BMC: as_bmc, BMC_TYPE.POD: as_pod}

    def as_self(self):
        """Return a reference to self that behaves as its own type."""
        return self._as_self[self.bmc_type](self)

    def delete(self):
        """Delete this BMC."""
        maaslog.info("%s: Deleting BMC", self)
        from maasserver.secrets import SecretManager

        SecretManager().delete_all_object_secrets(self.as_bmc())
        super().delete()

    def save(self, *args, **kwargs):
        """Save this BMC."""
        super().save(*args, **kwargs)
        # We let name be blank for the initial save, but fix it before the
        # save completes.  This is because set_random_name() operates by
        # trying to re-save the BMC with a random hostname, and retrying until
        # there is no conflict.
        if self.name == "":
            self.set_random_name()

    def set_random_name(self):
        """Set a random `name`."""
        while True:
            self.name = petname.Generate(2, "-")
            try:
                self.save()
            except ValidationError:
                pass
            else:
                break

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


class PodManager(BaseBMCManager):
    """Manager for `Pod` not `BMC`'s."""

    extra_filters = {"bmc_type": BMC_TYPE.POD}

    def get_pods(self, user, perm):
        """Fetch `ResourcePool`'s on which the User_ has the given permission.

        :param user: The user that should be used in the permission check.
        :type user: User_
        :param perm: Type of access requested.
        :type perm: `PodPermission`

        .. _User: https://
           docs.djangoproject.com/en/dev/topics/auth/
           #django.contrib.auth.models.User

        """
        # Circular imports.
        from maasserver.rbac import rbac

        if rbac.is_enabled():
            if perm == PodPermission.view:
                fetched = rbac.get_resource_pool_ids(
                    user.username, "view", "view-all"
                )
                pool_ids = set(fetched["view"] + fetched["view-all"])
                return self.filter(pool_id__in=pool_ids)
            elif perm == PodPermission.edit or perm == PodPermission.compose:
                return self.filter(
                    pool_id__in=rbac.get_resource_pool_ids(
                        user.username, "admin-machines"
                    )["admin-machines"]
                )
            elif perm == PodPermission.dynamic_compose:
                fetched = rbac.get_resource_pool_ids(
                    user.username, "deploy-machines", "admin-machines"
                )
                pool_ids = set(
                    fetched["deploy-machines"] + fetched["admin-machines"]
                )
                return self.filter(pool_id__in=pool_ids)
            else:
                raise ValueError("Unknown perm: %s", perm)
        return self.all()

    def get_pod_or_404(self, id, user, perm, **kwargs):
        """Fetch a `Pod` by id.  Raise exceptions if no `Pod` with
        this system_id exist or if the provided user has not the required
        permission on this `Pod`.

        :param id: The id.
        :type id: int
        :param user: The user that should be used in the permission check.
        :type user: django.contrib.auth.models.User
        :param perm: The permission to assert that the user has on the node.
        :type perm: `PodPermission`
        :raises: django.http.Http404_,
            :class:`maasserver.exceptions.PermissionDenied`.

        .. _django.http.Http404: https://
           docs.djangoproject.com/en/dev/topics/http/views/
           #the-http404-exception
        """
        kwargs.update(self.extra_filters)
        pod = get_object_or_404(self.model, id=id, **kwargs)
        if user.has_perm(perm, pod):
            return pod
        else:
            raise PermissionDenied()


def create_pod(**kwargs):
    power_type = kwargs.get("power_type")
    power_parameters = kwargs.get("power_parameters", {})

    power_parameters, secrets = sanitise_power_parameters(
        power_type, power_parameters
    )
    kwargs["power_parameters"] = power_parameters

    pod = Pod.objects.create(**kwargs)

    if secrets:
        from maasserver.secrets import SecretManager

        SecretManager().set_composite_secret(
            "power-parameters", secrets, obj=pod.as_bmc()
        )
    return pod


class Pod(BMC):
    """A `Pod` represents a `BMC` that controls multiple machines."""

    class Meta:
        proxy = True

    objects = PodManager()

    _machine_name_re = re.compile(r"[a-z][a-z0-9-]+$", flags=re.I)

    def __str__(self):
        if self.name:
            return f"{self.name} ({self.id})"
        else:
            return super().__str__()

    def __init__(self, *args, **kwargs):
        if not args:
            kwargs["bmc_type"] = BMC_TYPE.POD
            if "pool" not in kwargs:
                kwargs["pool"] = (
                    ResourcePool.objects.get_default_resource_pool()
                )
        super().__init__(*args, **kwargs)

    def clean(self):
        super().clean()
        if self.pool is None:
            raise ValidationError("A pod needs to have a pool")

    @property
    def tracked_project(self) -> str:
        """Return the project tracked by the Pod, or empty string."""
        return self.get_power_parameters().get("project", "")

    @property
    def host(self):
        node = self.hints.nodes.first()
        if node:
            return node
        elif self.ip_address is not None:
            interface = self.ip_address.get_interface()
            if interface is not None:
                return interface.node_config.node
        else:
            return None

    @property
    def cluster(self):
        """shortcut to the cluster (if any)"""
        return self.hints.cluster

    def sync_hints(self, discovered_hints, cluster=None):
        """Sync the hints with `discovered_hints`."""

        def update_hint(
            hints: PodHints, discovered: DiscoveredPodHints, attr: str
        ) -> bool:
            new_val = getattr(discovered, attr)
            if new_val != DiscoveredPodHints.UNDEFINED and new_val != getattr(
                hints, attr
            ):
                setattr(hints, attr, new_val)
                return True
            return False

        changed = False
        try:
            hints = self.hints
        except PodHints.DoesNotExist:
            hints = self.hints = PodHints()
            changed = True
        for a in ["cores", "cpu_speed", "memory", "local_storage"]:
            changed |= update_hint(hints, discovered_hints, a)
        if cluster is not None and hints.cluster != cluster:
            hints.cluster = cluster
            changed = True
        if changed:
            hints.save()

    def add_tag(self, tag):
        """Add tag to Pod."""
        if tag not in self.tags:
            self.tags = self.tags + [tag]

    def remove_tag(self, tag):
        """Remove tag from Pod."""
        if tag in self.tags:
            tags = self.tags.copy()
            tags.remove(tag)
            self.tags = tags

    def check_over_commit_ratios(self, requested_cores, requested_memory):
        """Checks that requested cpu cores and memory are within the
        currently available resources capped by the overcommit ratios."""
        from maasserver.models.virtualmachine import get_vm_host_used_resources

        message = ""
        used_resources = get_vm_host_used_resources(self)
        over_commit_cores = self.cores * self.cpu_over_commit_ratio
        potential_cores = used_resources.cores + requested_cores
        over_commit_memory = self.memory * self.memory_over_commit_ratio
        potential_memory = used_resources.total_memory + requested_memory
        if (over_commit_cores - potential_cores) < 0:
            message = (
                "CPU overcommit ratio is %s and there are %s "
                "available resources; %s requested."
                % (
                    self.cpu_over_commit_ratio,
                    (self.cores - used_resources.cores),
                    requested_cores,
                )
            )
        if (over_commit_memory - potential_memory) < 0:
            message += (
                "Memory overcommit ratio is %s and there are %s "
                "available resources; %s requested."
                % (
                    self.memory_over_commit_ratio,
                    (self.memory - used_resources.total_memory),
                    requested_memory,
                )
            )
        return message

    def _find_existing_machine(self, discovered_machine, mac_machine_map):
        """Find a `Machine` in `mac_machine_map` based on the interface MAC
        addresses from `discovered_machine`."""
        for interface in discovered_machine.interfaces:
            if interface.mac_address in mac_machine_map:
                return mac_machine_map[interface.mac_address]
        return None

    def _get_storage_pool_by_id(self, pool_id):
        """Get the `PodStoragePool` base on the `pool_id`."""
        # Finding storage pool in python instead of using the database, so
        # preloaded data is used. This prevents un-needed database queries.
        for pool in self.storage_pools.all():
            if pool.pool_id == pool_id:
                return pool

    def _create_physical_block_device(self, discovered_bd, machine, name=None):
        """Create's a new `PhysicalBlockDevice` for `machine`."""
        if name is None:
            name = machine.get_next_block_device_name()
        model = discovered_bd.model
        serial = discovered_bd.serial
        if model is None:
            model = ""
        if serial is None:
            serial = ""
        storage_pool = None
        if discovered_bd.storage_pool:
            storage_pool = self._get_storage_pool_by_id(
                discovered_bd.storage_pool
            )

        block_device = PhysicalBlockDevice.objects.create(
            node_config=machine.current_config,
            numa_node=machine.default_numanode,
            name=name,
            id_path=discovered_bd.id_path,
            model=model,
            serial=serial,
            size=discovered_bd.size,
            block_size=discovered_bd.block_size,
            tags=discovered_bd.tags,
        )
        self._sync_vm_disk(block_device, storage_pool=storage_pool)
        return block_device

    def _create_interface(self, discovered_nic, machine, name=None):
        """Create's a new physical `Interface` for `machine`."""
        # XXX blake_r 2017-03-09: At the moment just connect the boot interface
        # to the VLAN where DHCP is running, unless none is running then
        # connect it to the default VLAN. All remaining interfaces will stay
        # disconnected.
        vlan = None
        if discovered_nic.boot:
            vlan = VLAN.objects.filter(dhcp_on=True).order_by("id").first()
            if vlan is None:
                vlan = Fabric.objects.get_default_fabric().get_default_vlan()
        if name is None:
            name = machine.get_next_ifname()
        nic, created = PhysicalInterface.objects.get_or_create(
            mac_address=discovered_nic.mac_address,
            defaults={
                "name": name,
                "node_config": machine.current_config,
                "numa_node": machine.default_numanode,
                "tags": discovered_nic.tags,
                "vlan": vlan,
            },
        )
        if not created:
            podlog.warning(
                f"{self.name}: interface with MAC address "
                f"{discovered_nic.mac_address} was discovered on "
                f"machine {machine.hostname} and was moved "
                f"from {nic.node_config.node.hostname}."
            )
            nic.name = name
            nic.node_config = machine.current_config
            nic.tags = discovered_nic.tags
            nic.vlan = vlan
            nic.ip_addresses.all().delete()
            nic.save()
        return nic

    def create_machine(
        self,
        discovered_machine,
        commissioning_user,
        skip_commissioning=False,
        dynamic=False,
        interfaces=None,
        requested_machine=None,
        **kwargs,
    ):
        """Create's a `Machine` from `discovered_machines` for this pod."""
        status = NODE_STATUS.READY if skip_commissioning else NODE_STATUS.NEW

        # Check to see if discovered machine's hostname is legal and unique.
        if discovered_machine.hostname:
            if Node.objects.filter(
                hostname=discovered_machine.hostname
            ).exists() or not self._machine_name_re.match(
                discovered_machine.hostname
            ):
                discovered_machine.hostname = None

        # Set the zone for the machine.
        # This allows machines to be created in the Pod
        # with a zone other than the zone of the Pod.
        zone = kwargs.pop("zone", None)
        if zone is None:
            zone = self.zone
        pool = kwargs.pop("pool", None)
        if pool is None:
            pool = self.pool

        if interfaces is not None:
            assert isinstance(interfaces, LabeledConstraintMap)

        requested_ips = get_requested_ips(requested_machine)
        ip_modes = get_ip_modes(requested_machine)

        # Create the machine.
        machine = Machine(
            hostname=discovered_machine.hostname,
            architecture=discovered_machine.architecture,
            status=status,
            cpu_count=discovered_machine.cores,
            cpu_speed=discovered_machine.cpu_speed,
            memory=discovered_machine.memory,
            power_state=discovered_machine.power_state,
            dynamic=dynamic,
            pool=pool,
            parent=self.host,
            zone=zone,
            bios_boot_method=discovered_machine.bios_boot_method,
            **kwargs,
        )
        machine.bmc = self
        machine.set_instance_power_parameters(
            discovered_machine.power_parameters
        )
        if not machine.hostname:
            machine.set_random_hostname()
        machine.save()

        self._sync_vm(discovered_machine, machine)
        self._sync_tags(discovered_machine, machine)
        self._assign_storage(machine, discovered_machine, skip_commissioning)
        created_interfaces = self._assign_interfaces(
            machine, discovered_machine, interfaces, skip_commissioning
        )
        self._assign_ip_addresses(
            discovered_machine, created_interfaces, requested_ips, ip_modes
        )

        boot_interface = machine.get_boot_interface()
        if boot_interface and boot_interface.mac_address is None:
            skip_commissioning = True

        # New machines get commission started immediately unless skipped.
        if not skip_commissioning:
            skip_networking = False
            # If an interfaces constraint was specified, don't reset the
            # networking parameters. (Instead, allow them to be set based on
            # what was requested in the constraints string.)
            if interfaces is not None and len(interfaces) > 0:
                skip_networking = True
            machine.start_commissioning(
                commissioning_user, skip_networking=skip_networking
            )

        return machine

    def _assign_ip_addresses(
        self, discovered_machine, created_interfaces, allocated_ips, ip_modes
    ):
        # We need a second pass here to configure interfaces that the above
        # function call would otherwise change.
        if self.host is not None:
            self._update_vlans_based_on_pod_host(
                created_interfaces, discovered_machine
            )
        # Allocate any IP addresses the user requested.
        for interface in created_interfaces:
            if interface.name in allocated_ips:
                # Replace any pre-configured addresses with what the user
                # has requested.
                interface.ip_addresses.clear()
                for address in allocated_ips[interface.name]:
                    ip_address = StaticIPAddress.objects.allocate_new(
                        requested_address=address
                    )
                    # The VLAN of the interface might be inconsistent with the
                    # subnet's VLAN, if the pod doesn't have a host and MAAS
                    # guessed incorrectly in an earlier step. So trust the
                    # user's input here.
                    if interface.vlan != ip_address.subnet.vlan:
                        interface.vlan = ip_address.subnet.vlan
                        interface.save()
                    ip_address.save()
                    interface.ip_addresses.add(ip_address)
            if interface.name in ip_modes:
                mode = ip_modes[interface.name]
                if mode == "unconfigured":
                    for address in interface.ip_addresses.all():
                        # User requested an unconfigured interface; change
                        # the AUTO that was created to a STICKY and ensure
                        # the IP address is cleared out.
                        address.alloc_type = IPADDRESS_TYPE.STICKY
                        address.ip = None
                        address.save()

    def _assign_interfaces(
        self,
        machine,
        discovered_machine,
        interface_constraints,
        skip_commissioning,
    ):
        # Enumerating the LabeledConstraintMap of interfaces will yield the
        # name of each interface, in the same order that they will exist
        # on the hypervisor. (This is a fortunate coincidence, since
        # dictionaries in Python 3.6+ preserve insertion order.)
        if interface_constraints is not None:
            interface_names = [
                get_ifname_for_label(label) for label in interface_constraints
            ]
        else:
            interface_names = []
        if len(discovered_machine.interfaces) > len(interface_names):
            # The lists should never have different lengths, but use default
            # names for all interfaces to avoid conflicts, just in case.
            # (This also happens if no interface labels were supplied.)
            interface_names = [
                "eth%d" % i for i in range(len(discovered_machine.interfaces))
            ]
        # Create the discovered interface and set the default networking
        # configuration.
        created_interfaces = []
        for idx, discovered_nic in enumerate(discovered_machine.interfaces):
            interface = self._create_interface(
                discovered_nic, machine, name=interface_names[idx]
            )
            created_interfaces.append(interface)
            if discovered_nic.boot:
                machine.boot_interface = interface
                machine.save(update_fields=["boot_interface"])
        if skip_commissioning:
            machine.set_initial_networking_configuration()
        return created_interfaces

    def _assign_storage(self, machine, discovered_machine, skip_commissioning):
        # Create the discovered block devices and set the initial storage
        # layout for the machine.
        for idx, discovered_bd in enumerate(discovered_machine.block_devices):
            try:
                self._create_physical_block_device(
                    discovered_bd,
                    machine,
                    name=BlockDevice._get_block_name_from_idx(idx),
                )
            except Exception:
                if skip_commissioning:
                    # Commissioning is not being performed for this
                    # machine. When not performing commissioning it is
                    # required for all physical block devices be created,
                    # otherwise this is allowed to fail as commissioning
                    # will discover this information.
                    raise
        if skip_commissioning:
            machine.set_default_storage_layout()

    def _sync_tags(self, discovered_machine, machine):
        tags = []
        for tag_name in set(discovered_machine.tags + self.tags):
            tag, _ = Tag.objects.get_or_create(name=tag_name)
            tags.append(tag)
        machine.tags.set(tags)

    def _update_vlans_based_on_pod_host(
        self, created_interfaces, discovered_machine
    ):
        """Matches up newly-created interfaces with interfaces on the pod.host,
        given a list of interfaces that were created for the machine, and
        the DiscoveredMachine object.
        """
        # Circular imports.
        from maasserver.models import Interface

        interfaces = {
            interface.name: interface
            for interface in Interface.objects.all_interfaces_parents_first(
                self.host
            )
        }
        for idx, discovered_nic in enumerate(discovered_machine.interfaces):
            if discovered_nic.attach_type in (
                InterfaceAttachType.BRIDGE,
                InterfaceAttachType.MACVLAN,
                InterfaceAttachType.SRIOV,
            ):
                host_attach_interface = interfaces.get(
                    discovered_nic.attach_name, None
                )
                if (
                    discovered_nic.attach_type == InterfaceAttachType.SRIOV
                    and discovered_nic.vid
                ):
                    try:
                        host_attach_interface = VLANInterface.objects.get(
                            parent_relationships__parent=host_attach_interface,
                            vlan__vid=discovered_nic.vid,
                            type=INTERFACE_TYPE.VLAN,
                        )
                    except VLANInterface.DoesNotExist:
                        host_attach_interface = None
                if host_attach_interface is not None:
                    # If we get to this point, we found the interface the
                    # the VM has been attached to. Update the VLAN (but
                    # only if necessary).
                    host_vlan = host_attach_interface.vlan
                    interface = created_interfaces[idx]
                    if host_vlan != interface.vlan:
                        interface.vlan = host_vlan
                        interface.save()
                    if not interface.ip_addresses.exists():
                        interface.force_auto_or_dhcp_link()
                    continue

    def _sync_machine(self, discovered_machine, existing_machine):
        """Sync's the information from `discovered_machine` to update
        `existing_machine`."""
        # Log if the machine is moving under a pod or being moved from
        # a different pod.
        if existing_machine.bmc_id != self.id:
            if (
                existing_machine.bmc_id is None
                or existing_machine.bmc.bmc_type == BMC_TYPE.BMC
            ):
                podlog.warning(
                    "%s: %s has been moved under the pod, previously "
                    "it was not part of any pod."
                    % (self.name, existing_machine.hostname)
                )
            else:
                podlog.warning(
                    "%s: %s has been moved under the pod, previously "
                    "it was part of pod %s."
                    % (
                        self.name,
                        existing_machine.hostname,
                        existing_machine.bmc.name,
                    )
                )
            existing_machine.bmc = self

        # Sync power state and parameters for this machine always.
        existing_machine.power_state = discovered_machine.power_state
        existing_machine.set_instance_power_parameters(
            discovered_machine.power_parameters
        )
        existing_machine.cpu_count = discovered_machine.cores
        existing_machine.memory = discovered_machine.memory

        self._sync_vm(discovered_machine, existing_machine)

        # If this machine is not composed on allocation we skip syncing all the
        # remaining information because MAAS commissioning will discover this
        # information. Any changes on the MAAS in the pod for pre-existing and
        # manual require the machine to be re-commissioned.
        if not existing_machine.dynamic:
            existing_machine.save()
            return

        # Sync machine instance values.
        # We are skipping hostname syncing so that any changes to the
        # hostname in MAAS are not overwritten.
        existing_machine.architecture = discovered_machine.architecture
        existing_machine.cpu_speed = discovered_machine.cpu_speed
        existing_machine.save()

        self._sync_tags(discovered_machine, existing_machine)
        self._sync_block_devices(discovered_machine, existing_machine)
        self._sync_interfaces(discovered_machine, existing_machine)

    def _sync_vm(self, discovered_machine, machine):
        from maasserver.models.virtualmachine import VirtualMachine

        vm = getattr(machine, "virtualmachine", None)
        if not vm:
            vm, _ = VirtualMachine.objects.get_or_create(
                identifier=machine.instance_name,
                project=self.tracked_project,
                bmc=self,
            )
            vm.machine = machine
        vm.memory = discovered_machine.memory
        vm.hugepages_backed = discovered_machine.hugepages_backed
        vm.pinned_cores = discovered_machine.pinned_cores
        vm.unpinned_cores = (
            0 if discovered_machine.pinned_cores else discovered_machine.cores
        )
        vm.save()
        self._sync_vm_interfaces(vm, discovered_machine)
        return vm

    def _sync_vm_interfaces(self, vm, discovered_machine):
        from maasserver.models.virtualmachine import VirtualMachineInterface

        host_interfaces = {}
        if self.host:
            host_interfaces = {
                interface.name: interface
                for interface in self.host.current_config.interface_set.all()
            }

        iface_ids = set()
        existing_vm_ifaces = {
            iface.mac_address: iface
            for iface in VirtualMachineInterface.objects_current_config.filter(
                vm=vm
            ).all()
        }
        for discovered_interface in discovered_machine.interfaces:
            if discovered_interface.mac_address:
                iface = existing_vm_ifaces.get(
                    discovered_interface.mac_address
                )
            else:
                iface = None
            if iface is None:
                iface = VirtualMachineInterface.objects.create(
                    vm=vm,
                    mac_address=discovered_interface.mac_address,
                    attachment_type=discovered_interface.attach_type,
                )

            iface_ids.add(iface.id)

            iface.attachment_type = discovered_interface.attach_type
            iface.host_interface = host_interfaces.get(
                discovered_interface.attach_name
            )
            iface.save()
        VirtualMachineInterface.objects_current_config.filter(vm=vm).exclude(
            id__in=iface_ids
        ).delete()

    def _sync_vm_disk(self, block_device, storage_pool=None):
        """Ensure a VirtualMachineDisk exists and is updated for a block device."""
        from maasserver.models.virtualmachine import VirtualMachineDisk

        vmdisk = getattr(block_device, "vmdisk", None)
        if vmdisk:
            vmdisk.size = block_device.size
            vmdisk.storage_pool = storage_pool
            vmdisk.save()
        else:
            vmdisk = VirtualMachineDisk.objects.create(
                name=block_device.name,
                vm=block_device.node_config.node.virtualmachine,
                size=block_device.size,
                backing_pool=storage_pool,
                block_device=block_device,
            )
        return vmdisk

    def _sync_block_devices(self, discovered_machine, existing_machine):
        """Sync the `block_devices` to the `existing_machine`."""
        block_devices = discovered_machine.block_devices
        model_mapping = {
            f"{block_device.model}/{block_device.serial}": block_device
            for block_device in block_devices
            if block_device.model and block_device.serial
        }
        path_mapping = {
            block_device.id_path: block_device
            for block_device in block_devices
            if not block_device.model or not block_device.serial
        }
        existing_block_devices = map(
            lambda bd: bd.actual_instance,
            existing_machine.current_config.blockdevice_set.all(),
        )
        disks_to_delete = []
        for block_device in existing_block_devices:
            if isinstance(block_device, PhysicalBlockDevice):
                if block_device.model and block_device.serial:
                    key = f"{block_device.model}/{block_device.serial}"
                    if key in model_mapping:
                        self._sync_block_device(
                            model_mapping.pop(key), block_device
                        )
                    else:
                        disks_to_delete.append(block_device.id)
                else:
                    if block_device.id_path in path_mapping:
                        self._sync_block_device(
                            path_mapping.pop(block_device.id_path),
                            block_device,
                        )
                    else:
                        disks_to_delete.append(block_device.id)

        if disks_to_delete:
            from maasserver.models.virtualmachine import VirtualMachineDisk

            VirtualMachineDisk.objects.filter(
                block_device__id__in=disks_to_delete
            ).delete()
            BlockDevice.objects.filter(id__in=disks_to_delete).delete()

        for _, discovered_block_device in model_mapping.items():
            self._create_physical_block_device(
                discovered_block_device, existing_machine
            )
        for _, discovered_block_device in path_mapping.items():
            self._create_physical_block_device(
                discovered_block_device, existing_machine
            )

    def _sync_block_device(self, discovered_bd, existing_bd):
        """Sync the `discovered_bd` with the `existing_bd`.

        The model, serial, id_path, and target is not handled here because if
        either changed then no way of matching between an existing block
        device is possible.
        """
        existing_bd.size = discovered_bd.size
        existing_bd.block_size = discovered_bd.block_size
        existing_bd.tags = discovered_bd.tags

        storage_pool = None
        if discovered_bd.storage_pool:
            storage_pool = self._get_storage_pool_by_id(
                discovered_bd.storage_pool
            )

        self._sync_vm_disk(existing_bd, storage_pool=storage_pool)
        existing_bd.save()

    def _sync_interfaces(self, discovered_machine, existing_machine):
        """Sync the `interfaces` to the `existing_machine`."""
        mac_mapping = {
            nic.mac_address: nic for nic in discovered_machine.interfaces
        }
        # interface_set has been preloaded so filtering is done locally.
        physical_interfaces = [
            nic
            for nic in existing_machine.current_config.interface_set.all()
            if nic.type == INTERFACE_TYPE.PHYSICAL
        ]
        for existing_nic in physical_interfaces:
            if existing_nic.mac_address in mac_mapping:
                discovered_nic = mac_mapping.pop(existing_nic.mac_address)
                self._sync_interface(discovered_nic, existing_nic)
                if discovered_nic.boot:
                    existing_machine.boot_interface = existing_nic
                    existing_machine.save(update_fields=["boot_interface"])
            else:
                existing_nic.delete()
        for _, discovered_nic in mac_mapping.items():
            interface = self._create_interface(
                discovered_nic, existing_machine
            )
            if discovered_nic.boot:
                existing_machine.boot_interface = interface
                existing_machine.save(update_fields=["boot_interface"])

    def _sync_interface(self, discovered_nic, existing_interface):
        """Sync the `discovered_nic` with the `existing_interface`.

        The MAC address is not handled here because if the MAC address has
        changed then no way of matching between an existing interface is
        possible.
        """
        # XXX blake_r 2016-12-20: At the moment only update the tags on the
        # interface. This needs to be improved to sync the connected VLAN. At
        # the moment we do not override what is set, allowing users to adjust
        # the VLAN if discovery is not identifying it correctly.
        existing_interface.tags = discovered_nic.tags
        existing_interface.save()

    def _cluster_location_match(self, discovered_machine):
        return (
            discovered_machine.location is None
            or discovered_machine.location == self.name
        )

    def sync_machines(self, discovered_machines, commissioning_user):
        """Sync the machines on this pod from `discovered_machines`."""
        tracked_machines = []
        discovered_by_project = defaultdict(list)
        # if a project is specified for the Pod, only track (i.e. create
        # machines for) VMs in that project, but sync VirtualMachine objects
        # across all projects
        if self.tracked_project:
            for discovered_machine in discovered_machines:
                if not self._cluster_location_match(discovered_machine):
                    continue
                machine_project = discovered_machine.power_parameters.get(
                    "project", ""
                )
                discovered_by_project[machine_project].append(
                    discovered_machine
                )
                if machine_project == self.tracked_project:
                    tracked_machines.append(discovered_machine)
        else:
            tracked_machines = [
                machine
                for machine in discovered_machines
                if self._cluster_location_match(machine)
            ]
            discovered_by_project[""] = discovered_machines

        from maasserver.models.virtualmachine import (
            VirtualMachine,
            VirtualMachineDisk,
        )

        # delete all VMs in projects that are no longer found (either
        # they're empty or have been removed)
        VirtualMachine.objects.filter(bmc=self).exclude(
            project__in=discovered_by_project
        ).delete()

        for project, discovered in discovered_by_project.items():
            vm_names = [machine.instance_name for machine in discovered]
            VirtualMachine.objects.filter(bmc=self, project=project).exclude(
                identifier__in=vm_names
            ).delete()
            for discovered_vm in discovered:
                vm, _ = VirtualMachine.objects.update_or_create(
                    identifier=discovered_vm.instance_name,
                    project=project,
                    bmc=self,
                    defaults={
                        "memory": discovered_vm.memory,
                        "hugepages_backed": discovered_vm.hugepages_backed,
                        "pinned_cores": discovered_vm.pinned_cores,
                        "unpinned_cores": (
                            0
                            if discovered_vm.pinned_cores
                            else discovered_vm.cores
                        ),
                    },
                )
                existing_disks = []
                for idx, device in enumerate(discovered_vm.block_devices):
                    vmdisk, _ = VirtualMachineDisk.objects.update_or_create(
                        name=f"vd{idx}",
                        vm=vm,
                        defaults={
                            "size": device.size,
                            "backing_pool": self._get_storage_pool_by_id(
                                device.storage_pool
                            ),
                        },
                    )
                    existing_disks.append(vmdisk.id)
                # delete any other disk
                VirtualMachineDisk.objects.filter(vm=vm).exclude(
                    id__in=existing_disks
                ).delete()

        all_macs = [
            interface.mac_address
            for machine in tracked_machines
            for interface in machine.interfaces
        ]
        existing_machines = list(
            Node.objects.filter(
                current_config__interface__mac_address__in=all_macs
            )
            .prefetch_related("current_config__interface_set")
            .prefetch_related(
                "current_config__blockdevice_set__physicalblockdevice"
            )
            .prefetch_related(
                "current_config__blockdevice_set__virtualblockdevice"
            )
            .prefetch_related("virtualmachine")
            .distinct()
        )
        machines = {
            machine.id: machine
            for machine in Node.objects.filter(bmc__id=self.id)
        }
        mac_machine_map = {
            interface.mac_address: machine
            for machine in existing_machines
            for interface in machine.current_config.interface_set.all()
        }
        for discovered_machine in tracked_machines:
            existing_machine = self._find_existing_machine(
                discovered_machine, mac_machine_map
            )
            if existing_machine is None:
                new_machine = self.create_machine(
                    discovered_machine, commissioning_user
                )
                podlog.info(
                    "%s: discovered new machine: %s"
                    % (self.name, new_machine.hostname)
                )
            else:
                self._sync_machine(discovered_machine, existing_machine)
                existing_machines.remove(existing_machine)
                machines.pop(existing_machine.id, None)
        for _, remove_machine in machines.items():
            remove_machine.delete()
            podlog.warning(
                "%s: machine %s no longer exists and was deleted."
                % (self.name, remove_machine.hostname)
            )

    def sync_storage_pools(self, discovered_storage_pools):
        """Sync the storage pools for the pod."""
        storage_pools_by_id = {
            pool.pool_id: pool for pool in self.storage_pools.all()
        }
        possible_default = None
        upgrade_default_pool = self.get_power_parameters().get(
            "default_storage_pool"
        )
        for discovered_pool in discovered_storage_pools:
            pool = storage_pools_by_id.pop(discovered_pool.id, None)
            if pool:
                pool.name = discovered_pool.name
                pool.pool_type = discovered_pool.type
                pool.path = discovered_pool.path
                pool.storage = discovered_pool.storage
                pool.save()
            else:
                pool = PodStoragePool.objects.create(
                    pod=self,
                    pool_id=discovered_pool.id,
                    name=discovered_pool.name,
                    pool_type=discovered_pool.type,
                    path=discovered_pool.path,
                    storage=discovered_pool.storage,
                )
                podlog.info(
                    "%s: discovered new storage pool: %s"
                    % (self.name, discovered_pool.name)
                )
            if possible_default is None:
                possible_default = pool
            if (
                upgrade_default_pool is not None
                and upgrade_default_pool == pool.name
            ):
                possible_default = pool
        if not self.default_storage_pool and possible_default:
            self.default_storage_pool = possible_default
            if upgrade_default_pool is not None:
                self.power_parameters = self.get_power_parameters().copy()
                self.power_parameters.pop("default_storage_pool", None)
            self.save()
        elif self.default_storage_pool in storage_pools_by_id.values():
            self.default_storage_pool = possible_default
            self.save()
        for _, pool in storage_pools_by_id.items():
            pool.delete()
            podlog.warning(
                "%s: storage pool %s no longer exists and was deleted."
                % (self.name, pool.name)
            )

    def sync(self, discovered_pod, commissioning_user, cluster=None):
        """Sync the pod and machines from the `discovered_pod`.

        This method ensures consistency with what is discovered by a pod
        driver and what is known to MAAS in the data model. Any machines,
        interfaces, and/or block devices that do not match the
        `discovered_pod` values will be removed.
        """
        pod_power_parameters = self.get_power_parameters()
        if self.power_type == "lxd" and "password" in pod_power_parameters:
            # ensure LXD trust_password is removed if it's there
            #
            # XXX copy and replace the whole attribute as the CleanSave base
            # class tracks which attributes to update on save via __setattr__,
            # so changing the value of the dict doesn't cause it to be updated.
            power_params = pod_power_parameters.copy()
            del power_params["password"]
            self.set_power_parameters(power_params)
        self.version = discovered_pod.version
        self.architectures = discovered_pod.architectures
        if not self.name or cluster is not None and discovered_pod.name:
            self.name = discovered_pod.name
        self.capabilities = discovered_pod.capabilities
        if discovered_pod.cores != -1:
            self.cores = discovered_pod.cores
        if discovered_pod.cpu_speed != -1:
            self.cpu_speed = discovered_pod.cpu_speed
        if discovered_pod.memory != -1:
            self.memory = discovered_pod.memory
        if discovered_pod.local_storage != -1:
            self.local_storage = discovered_pod.local_storage
        self.tags = list(set(self.tags).union(discovered_pod.tags))
        self.save()
        self.sync_hints(discovered_pod.hints, cluster=cluster)
        self.sync_storage_pools(discovered_pod.storage_pools)
        self.sync_machines(discovered_pod.machines, commissioning_user)
        if discovered_pod.mac_addresses:
            node = (
                Node.objects.filter(
                    current_config__interface__mac_address__in=discovered_pod.mac_addresses
                )
                .distinct()
                .first()
            )
            if not node:
                node = Node.objects.create(
                    hostname=self.name,
                    architecture=self.architectures[0],
                    dynamic=True,
                    status=NODE_STATUS.DEPLOYED,
                    owner=commissioning_user,
                )
                for mac_address in discovered_pod.mac_addresses:
                    node.add_physical_interface(mac_address)

            update = {}
            if node.is_device:
                update["node_type"] = NODE_TYPE.MACHINE
            if not node.current_commissioning_script_set:
                from maasserver.models import ScriptSet

                # ScriptResults will be created on upload.
                update["current_commissioning_script_set"] = (
                    ScriptSet.objects.create(
                        node=node, result_type=RESULT_TYPE.COMMISSIONING
                    )
                )
            if node.status != NODE_STATUS.DEPLOYED:
                update["status"] = NODE_STATUS.DEPLOYED
            if update:
                # Use update to allow transitioning from NEW to DEPLOYED.
                Node.objects.filter(system_id=node.system_id).update(**update)
            self.hints.nodes.add(node)
        podlog.info("%s: finished syncing discovered information" % self.name)

    def sync_hints_from_nodes(self):
        """Sync the hints based on discovered data from associated nodes."""
        try:
            hints = self.hints
        except PodHints.DoesNotExist:
            hints = self.hints = PodHints()
        self.cores = hints.cores = 0
        self.cpu_speed = hints.cpu_speed = 0
        self.memory = hints.memory = 0
        cpu_speeds = []
        # Set the hints for the Pod to the total amount for all nodes in a
        # cluster.
        for node in hints.nodes.all().prefetch_related(
            "numanode_set", "current_config__blockdevice_set"
        ):
            for numa in node.numanode_set.all():
                hints.cores += len(numa.cores)
                self.cores += len(numa.cores)
                hints.memory += numa.memory
                self.memory += numa.memory
            if node.cpu_speed != 0:
                cpu_speeds.append(node.cpu_speed)
        self.cpu_speed = hints.cpu_speed = (
            mean(cpu_speeds) if cpu_speeds else 0
        )
        hints.save()
        self.save()

    def delete(self, *args, **kwargs):
        raise AttributeError(
            "Use `async_delete` instead. Deleting a Pod takes "
            "an asynchronous action."
        )

    def delete_and_wait(self, decompose=False):
        """Block the current thread while waiting for the pod to be deleted.

        This must not be called from a deferToDatabase thread; use the
        async_delete() method instead.
        """
        # Calculate the wait time based on the number of none pre-existing
        # machines. We allow maximum of 60 seconds per machine plus 60 seconds
        # for the pod.
        pod = self.as_pod()
        machine_wait = 0
        if decompose:
            machine_wait = Machine.objects.filter(bmc=pod).count() * 60
        pod.async_delete(decompose=decompose).wait(machine_wait + 60)

    @asynchronous
    def async_delete(self, decompose=False, delete_peers=True):
        """Delete a pod asynchronously.

        If `decompose` is True, any machine in the pod will be decomposed
        before it is removed from the database.  If there are any errors during
        decomposition, the deletion of the machine and ultimately the pod are
        not stopped.

        """

        @transactional
        def gather_clients_and_machines(pod):
            machine_details = [
                (machine.id, machine.get_power_parameters())
                for machine in Machine.objects.filter(
                    bmc__id=pod.id
                ).select_related("bmc")
            ]
            return (
                pod.id,
                pod.name,
                pod.power_type,
                pod.get_client_identifiers(),
                machine_details,
            )

        @inlineCallbacks
        def decompose_machines(result):
            (
                pod_id,
                pod_name,
                pod_type,
                client_idents,
                machine_details,
            ) = result
            decomposed_ids = []
            for machine_id, parameters in machine_details:
                decomposed_ids.append(machine_id)
                # Get a new client for every decompose because we might lose
                # a connection to a rack during this operation.
                client = yield getClientFromIdentifiers(client_idents)
                try:
                    yield decompose_machine(
                        client,
                        pod_type,
                        parameters,
                        pod_id=pod_id,
                        name=pod_name,
                    )
                except PodProblem:
                    # Catch all errors and continue.
                    break
            return pod_id, decomposed_ids

        def get_pod_and_machine_ids(result):
            (
                pod_id,
                pod_name,
                pod_type,
                client_idents,
                machine_details,
            ) = result
            return pod_id, [
                machine_id for machine_id, parameters in machine_details
            ]

        @transactional
        def perform_deletion(result):
            pod_id, decomposed_ids = result
            for machine in Machine.objects.filter(id__in=decomposed_ids):
                # Clear BMC (aka. this pod) so the signal handler does not
                # try to decompose it. Its already been decomposed.
                machine.bmc = None
                machine.delete()

            pod_node = self.hints.nodes.first()
            if (
                pod_node is not None
                and not pod_node.is_controller
                and pod_node.should_be_dynamically_deleted()
            ):
                pod_node.delete()
            # Update bmc types for any matches.  Only delete the BMC
            # when no controllers are using the same BMC.
            from maasserver.models.node import RackController

            racks_with_matching_bmc = list(
                RackController.objects.filter(bmc__id=pod_id)
            )
            if racks_with_matching_bmc:
                for rack in racks_with_matching_bmc:
                    rack.bmc.bmc_type = BMC_TYPE.BMC
                    rack.bmc.save()
            else:
                # Call delete by bypassing the override that prevents its call.
                pod = Pod.objects.get(id=pod_id)
                BMC.delete(pod)

        @transactional
        def _check_for_cluster_delete():
            return delete_peers and self.cluster is not None

        d = deferToDatabase(_check_for_cluster_delete)

        def build_delete_callback_chain(clustered_delete):
            # if this vmhost belongs to a cluster, drive the process from there
            if clustered_delete:
                return self.cluster.async_delete(decompose)
            # Don't catch any errors here they are raised to the caller.
            d = deferToDatabase(gather_clients_and_machines, self)
            d.addCallback(
                decompose_machines if decompose else get_pod_and_machine_ids
            )
            d.addCallback(partial(deferToDatabase, perform_deletion))
            return d

        d.addCallback(build_delete_callback_chain)

        return d


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
