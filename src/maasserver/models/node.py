# Copyright 2012-2014 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Node objects."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = [
    "NODE_TRANSITIONS",
    "Node",
    ]

from itertools import (
    chain,
    imap,
    islice,
    repeat,
    )
import random
import re
from string import whitespace
from uuid import uuid1

import celery
from django.contrib.auth.models import User
from django.core.exceptions import (
    PermissionDenied,
    ValidationError,
    )
from django.db.models import (
    BooleanField,
    CharField,
    ForeignKey,
    IntegerField,
    Manager,
    ManyToManyField,
    Q,
    SET_DEFAULT,
    TextField,
    )
from django.shortcuts import get_object_or_404
import djorm_pgarray.fields
from maasserver import DefaultMeta
from maasserver.enum import (
    NODE_BOOT,
    NODE_BOOT_CHOICES,
    NODE_PERMISSION,
    NODE_STATUS,
    NODE_STATUS_CHOICES,
    NODE_STATUS_CHOICES_DICT,
    NODEGROUPINTERFACE_MANAGEMENT,
    )
from maasserver.exceptions import (
    NodeStateViolation,
    StaticIPAddressTypeClash,
    )
from maasserver.fields import (
    JSONObjectField,
    MAC,
    )
from maasserver.models.cleansave import CleanSave
from maasserver.models.config import Config
from maasserver.models.dhcplease import DHCPLease
from maasserver.models.licensekey import LicenseKey
from maasserver.models.staticipaddress import (
    StaticIPAddress,
    StaticIPAddressExhaustion,
    )
from maasserver.models.tag import Tag
from maasserver.models.timestampedmodel import TimestampedModel
from maasserver.models.zone import Zone
from maasserver.utils import (
    get_db_state,
    strip_domain,
    )
from piston.models import Token
from provisioningserver.drivers.osystem import OperatingSystemRegistry
from provisioningserver.logger import get_maas_logger
from provisioningserver.tasks import (
    add_new_dhcp_host_map,
    power_off,
    power_on,
    remove_dhcp_host_map,
    )


maaslog = get_maas_logger("node")


def generate_node_system_id():
    return 'node-%s' % uuid1()


# Information about valid node status transitions.
# The format is:
# {
#  old_status1: [
#      new_status11,
#      new_status12,
#      new_status13,
#      ],
# ...
# }
#
NODE_TRANSITIONS = {
    None: [
        NODE_STATUS.DECLARED,
        NODE_STATUS.MISSING,
        NODE_STATUS.RETIRED,
        ],
    NODE_STATUS.DECLARED: [
        NODE_STATUS.COMMISSIONING,
        NODE_STATUS.MISSING,
        NODE_STATUS.READY,
        NODE_STATUS.RETIRED,
        NODE_STATUS.BROKEN,
        ],
    NODE_STATUS.COMMISSIONING: [
        NODE_STATUS.FAILED_TESTS,
        NODE_STATUS.READY,
        NODE_STATUS.RETIRED,
        NODE_STATUS.MISSING,
        NODE_STATUS.DECLARED,
        NODE_STATUS.BROKEN,
        ],
    NODE_STATUS.FAILED_TESTS: [
        NODE_STATUS.COMMISSIONING,
        NODE_STATUS.MISSING,
        NODE_STATUS.RETIRED,
        NODE_STATUS.BROKEN,
        ],
    NODE_STATUS.READY: [
        NODE_STATUS.COMMISSIONING,
        NODE_STATUS.ALLOCATED,
        NODE_STATUS.RESERVED,
        NODE_STATUS.RETIRED,
        NODE_STATUS.MISSING,
        NODE_STATUS.BROKEN,
        ],
    NODE_STATUS.RESERVED: [
        NODE_STATUS.READY,
        NODE_STATUS.ALLOCATED,
        NODE_STATUS.RETIRED,
        NODE_STATUS.MISSING,
        NODE_STATUS.BROKEN,
        ],
    NODE_STATUS.ALLOCATED: [
        NODE_STATUS.READY,
        NODE_STATUS.RETIRED,
        NODE_STATUS.MISSING,
        NODE_STATUS.BROKEN,
        ],
    NODE_STATUS.MISSING: [
        NODE_STATUS.DECLARED,
        NODE_STATUS.READY,
        NODE_STATUS.ALLOCATED,
        NODE_STATUS.COMMISSIONING,
        NODE_STATUS.BROKEN,
        ],
    NODE_STATUS.RETIRED: [
        NODE_STATUS.DECLARED,
        NODE_STATUS.READY,
        NODE_STATUS.MISSING,
        NODE_STATUS.BROKEN,
        ],
    NODE_STATUS.BROKEN: [
        NODE_STATUS.COMMISSIONING,
        NODE_STATUS.READY,
        ],
    }


class UnknownPowerType(Exception):
    """Raised when a node has an unknown power type."""


def validate_hostname(hostname):
    """Validator for hostnames.

    :param hostname: Input value for a host name.  May include domain.
    :raise ValidationError: If the hostname is not valid according to RFCs 952
        and 1123.
    """
    # Valid characters within a hostname label: ASCII letters, ASCII digits,
    # hyphens, and underscores.  Not all are always valid.
    # Technically we could write all of this as a single regex, but it's not
    # very good for code maintenance.
    label_chars = re.compile('[a-zA-Z0-9_-]*$')

    if len(hostname) > 255:
        raise ValidationError(
            "Hostname is too long.  Maximum allowed is 255 characters.")
    # A hostname consists of "labels" separated by dots.
    labels = hostname.split('.')
    if '_' in labels[0]:
        # The host label cannot contain underscores; the rest of the name can.
        raise ValidationError(
            "Host label cannot contain underscore: %r." % labels[0])
    for label in labels:
        if len(label) == 0:
            raise ValidationError("Hostname contains empty name.")
        if len(label) > 63:
            raise ValidationError(
                "Name is too long: %r.  Maximum allowed is 63 characters."
                % label)
        if label.startswith('-') or label.endswith('-'):
            raise ValidationError(
                "Name cannot start or end with hyphen: %r." % label)
        if not label_chars.match(label):
            raise ValidationError(
                "Name contains disallowed characters: %r." % label)


class NodeManager(Manager):
    """A utility to manage the collection of Nodes."""

    def filter_by_ids(self, query, ids=None):
        """Filter `query` result set by system_id values.

        :param query: A QuerySet of Nodes.
        :type query: django.db.models.query.QuerySet_
        :param ids: Optional set of ids to filter by.  If given, nodes whose
            system_ids are not in `ids` will be ignored.
        :type param_ids: Sequence
        :return: A filtered version of `query`.

        .. _django.db.models.query.QuerySet: https://docs.djangoproject.com/
           en/dev/ref/models/querysets/

        """
        if ids is None:
            return query
        else:
            return query.filter(system_id__in=ids)

    def _filter_visible_nodes(self, nodes, user, perm):
        """Filter a `Node` query depending on user permissions.

        :param nodes: A `Node` query set.
        :param user: The user making the request; the filtering is based on
            their privileges.
        :param perm: Type of access requested.  For example, a user may be
            allowed to view some nodes that they are not allowed to edit.
        :type perm: `NODE_PERMISSION`
        :return: A version of `node` that is filtered to include only those
            nodes that `user` is allowed to access.
        """
        if user.is_superuser:
            # Admin is allowed to see all nodes.
            return nodes
        elif perm == NODE_PERMISSION.VIEW:
            return nodes.filter(Q(owner__isnull=True) | Q(owner=user))
        elif perm == NODE_PERMISSION.EDIT:
            return nodes.filter(owner=user)
        elif perm == NODE_PERMISSION.ADMIN:
            return nodes.none()
        else:
            raise NotImplementedError(
                "Invalid permission check (invalid permission name: %s)." %
                perm)

    def get_nodes(self, user, perm, ids=None, from_nodes=None):
        """Fetch Nodes on which the User_ has the given permission.

        Warning: there could be a lot of nodes!  Keep scale in mind when
        calling this, and watch performance in general.  Prefetch related
        data where appropriate.

        :param user: The user that should be used in the permission check.
        :type user: User_
        :param perm: The permission to check.
        :type perm: a permission string from NODE_PERMISSION
        :param ids: If given, limit result to nodes with these system_ids.
        :type ids: Sequence.
        :param from_nodes: Optionally, restrict the answer to these nodes.
        :type from_nodes: Query set of `Node`.

        .. _User: https://
           docs.djangoproject.com/en/dev/topics/auth/
           #django.contrib.auth.models.User

        """
        if from_nodes is None:
            from_nodes = self.all()
        nodes = self._filter_visible_nodes(from_nodes, user, perm)
        return self.filter_by_ids(nodes, ids)

    def get_allocated_visible_nodes(self, token, ids):
        """Fetch Nodes that were allocated to the User_/oauth token.

        :param user: The user whose nodes to fetch
        :type user: User_
        :param token: The OAuth token associated with the Nodes.
        :type token: piston.models.Token.
        :param ids: Optional set of IDs to filter by. If given, nodes whose
            system_ids are not in `ids` will be ignored.
        :type param_ids: Sequence

        .. _User: https://
           docs.djangoproject.com/en/dev/topics/auth/
           #django.contrib.auth.models.User
        """
        if ids is None:
            nodes = self.filter(token=token)
        else:
            nodes = self.filter(token=token, system_id__in=ids)
        return nodes

    def get_node_or_404(self, system_id, user, perm):
        """Fetch a `Node` by system_id.  Raise exceptions if no `Node` with
        this system_id exist or if the provided user has not the required
        permission on this `Node`.

        :param name: The system_id.
        :type name: string
        :param user: The user that should be used in the permission check.
        :type user: django.contrib.auth.models.User
        :param perm: The permission to assert that the user has on the node.
        :type perm: unicode
        :raises: django.http.Http404_,
            :class:`maasserver.exceptions.PermissionDenied`.

        .. _django.http.Http404: https://
           docs.djangoproject.com/en/dev/topics/http/views/
           #the-http404-exception
        """
        node = get_object_or_404(Node, system_id=system_id)
        if user.has_perm(perm, node):
            return node
        else:
            raise PermissionDenied()

    def get_available_nodes_for_acquisition(self, for_user):
        """Find the nodes that can be acquired by the given user.

        :param for_user: The user who is to acquire the node.
        :type for_user: :class:`django.contrib.auth.models.User`
        :return: Those nodes which can be acquired by the user.
        :rtype: `django.db.models.query.QuerySet`
        """
        available_nodes = self.get_nodes(for_user, NODE_PERMISSION.VIEW)
        return available_nodes.filter(status=NODE_STATUS.READY)

    def stop_nodes(self, ids, by_user, stop_mode='hard'):
        """Request on given user's behalf that the given nodes be shut down.

        Shutdown is only requested for nodes that the user has ownership
        privileges for; any other nodes in the request are ignored.

        :param ids: The `system_id` values for nodes to be shut down.
        :type ids: Sequence
        :param by_user: Requesting user.
        :type by_user: User_
        :param stop_mode: Power off mode - usually 'soft' or 'hard'.
        :type stop_mode: unicode
        :return: Those Nodes for which shutdown was actually requested.
        :rtype: list
        """
        maaslog.debug("Stopping node(s): %s", ids)
        nodes = self.get_nodes(by_user, NODE_PERMISSION.EDIT, ids=ids)
        processed_nodes = []
        for node in nodes:
            power_params = node.get_effective_power_parameters()
            try:
                node_power_type = node.get_effective_power_type()
            except UnknownPowerType:
                # Skip the rest of the loop to avoid creating a power
                # event for a node that we can't power down.
                maaslog.warning(
                    "Node %s (%s) has an unknown power type. Not creating "
                    "power down event.", node.hostname, node.system_id)
                continue
            power_params['power_off_mode'] = stop_mode
            # WAKE_ON_LAN does not support poweroff.
            if node_power_type != 'ether_wake':
                maaslog.info(
                    "Asking cluster to power off node: %s (%s)",
                    node.hostname, node.system_id)
                power_off.apply_async(
                    queue=node.work_queue, args=[node_power_type],
                    kwargs=power_params)
            processed_nodes.append(node)
        return processed_nodes

    def start_nodes(self, ids, by_user, user_data=None):
        """Request on given user's behalf that the given nodes be started up.

        Power-on is only requested for nodes that the user has ownership
        privileges for; any other nodes in the request are ignored.

        Nodes are also ignored if they don't have a valid power type
        configured.

        :param ids: The `system_id` values for nodes to be started.
        :type ids: Sequence
        :param by_user: Requesting user.
        :type by_user: User_
        :param user_data: Optional blob of user-data to be made available to
            the nodes through the metadata service.  If not given, any
            previous user data is used.
        :type user_data: unicode
        :return: Those Nodes for which power-on was actually requested.
        :rtype: list
        """
        maaslog.debug("Starting nodes: %s", ids)
        # Avoid circular imports.
        from metadataserver.models import NodeUserData

        nodes = self.get_nodes(by_user, NODE_PERMISSION.EDIT, ids=ids)
        for node in nodes:
            NodeUserData.objects.set_user_data(node, user_data)
        processed_nodes = []
        for node in nodes:
            maaslog.info(
                "Attempting start up of %s (%s)", node.hostname,
                node.system_id)
            power_params = node.get_effective_power_parameters()
            try:
                node_power_type = node.get_effective_power_type()
            except UnknownPowerType:
                # Skip the rest of the loop to avoid creating a power
                # event for a node that we can't power up.
                maaslog.warning(
                    "Node %s (%s) has an unknown power type. Not creating "
                    "power up event.", node.hostname, node.system_id)
                continue
            if node_power_type == 'ether_wake':
                mac = power_params.get('mac_address')
                do_start = (mac != '' and mac is not None)
            else:
                do_start = True
            if do_start:
                tasks = []
                try:
                    if node.status == NODE_STATUS.ALLOCATED:
                        tasks.extend(node.claim_static_ips())
                except StaticIPAddressExhaustion:
                    maaslog.error(
                        "Node %s (%s): Unable to allocate static IP due to "
                        "address exhaustion.", node.hostname, node.system_id)
                    # XXX 2014-06-17 bigjools bug=1330762
                    # This function is supposed to start all the nodes
                    # it can, but gives no way to return errors about
                    # the ones it can't.  So just fail the lot for now,
                    # pending a redesign of the API.
                    #
                    # XXX 2014-06-17 bigjools bug=1330765
                    # If any of this fails it needs to release the
                    # static IPs back to the pool.  As part of the robustness
                    # work coming up, it also needs to inform the user.
                    raise

                task = power_on.si(node_power_type, **power_params)
                task.set(queue=node.work_queue)
                tasks.append(task)
                chained_tasks = celery.chain(tasks)
                maaslog.debug(
                    "Asking cluster to power on %s (%s)", node.hostname,
                    node.system_id)
                chained_tasks.apply_async()
                processed_nodes.append(node)
        return processed_nodes


# Non-ambiguous characters (i.e. without 'ilousvz1250').
non_ambiguous_characters = imap(
    random.choice, repeat('abcdefghjkmnpqrtwxy346789'))


def generate_hostname(size):
    """Generate a hostname using only non-ambiguous characters."""
    return "".join(islice(non_ambiguous_characters, size))


def patch_pgarray_types():
    """Monkey-patch incompatibility with recent versions of `djorm_pgarray`.

    An upstream commit in `djorm_pgarray` on 2013-07-21 effectively limits
    arrays to a fixed set of types.  An attempt to create an `ArrayField` of
    any other type results in the error "TypeError: invalid postgreSQL type."
    We have been getting that error with python-djorm-ext-pgarray 0.8, the
    first Ubuntu-packaged version, but not with 0.6.

    This function monkey-patches the set of supported types, adding macaddr.

    Upstream bug: https://github.com/niwibe/djorm-ext-pgarray/issues/19
    """
    # TYPES maps PostgreSQL type names to their Django casters.  The error
    # happens when using a postgres type name that is not in this dict.
    #
    # Older versions did not have TYPES, and worked out of the box.
    types_dict = getattr(djorm_pgarray.fields, 'TYPES', None)
    if types_dict is not None and 'macaddr' not in types_dict:
        djorm_pgarray.fields.TYPES['macaddr'] = MAC


# Monkey-patch djorm_pgarray's types list to support MAC.
patch_pgarray_types()


class Node(CleanSave, TimestampedModel):
    """A `Node` represents a physical machine used by the MAAS Server.

    :ivar system_id: The unique identifier for this `Node`.
        (e.g. 'node-41eba45e-4cfa-11e1-a052-00225f89f211').
    :ivar hostname: This `Node`'s hostname.  Must conform to RFCs 952 and 1123.
    :ivar status: This `Node`'s status. See the vocabulary
        :class:`NODE_STATUS`.
    :ivar error_description: A human-readable description of why a node is
        marked broken.  Only meaningful when the node is in the state 'BROKEN'.
    :ivar owner: This `Node`'s owner if it's in use, None otherwise.
    :ivar boot_type: This `Node`'s booting method. See the vocabulary
        :class:`NODE_BOOT`.
    :ivar osystem: This `Node`'s booting operating system, if it's blank then
        the default_osystem will be used.
    :ivar distro_series: This `Node`'s booting distro series, if
        it's blank then the default_distro_series will be used.
    :ivar power_type: The power type that determines how this
        node will be powered on. Its value must match a power driver template
        name.
    :ivar nodegroup: The `NodeGroup` this `Node` belongs to.
    :ivar tags: The list of :class:`Tag`s associated with this `Node`.
    :ivar objects: The :class:`NodeManager`.

    """

    class Meta(DefaultMeta):
        """Needed for South to recognize this model."""

    system_id = CharField(
        max_length=41, unique=True, default=generate_node_system_id,
        editable=False)

    hostname = CharField(
        max_length=255, default='', blank=True, unique=True,
        validators=[validate_hostname])

    status = IntegerField(
        max_length=10, choices=NODE_STATUS_CHOICES, editable=False,
        default=NODE_STATUS.DEFAULT)

    owner = ForeignKey(
        User, default=None, blank=True, null=True, editable=False)

    boot_type = CharField(
        max_length=20, choices=NODE_BOOT_CHOICES, default=NODE_BOOT.FASTPATH)

    osystem = CharField(
        max_length=20, blank=True, default='')

    distro_series = CharField(
        max_length=20, blank=True, default='')

    architecture = CharField(max_length=31, blank=False)

    routers = djorm_pgarray.fields.ArrayField(dbtype="macaddr")

    agent_name = CharField(max_length=255, default='', blank=True, null=True)

    error_description = TextField(blank=True, default='', editable=False)

    zone = ForeignKey(
        Zone, verbose_name="Physical zone",
        default=Zone.objects.get_default_zone, editable=True, db_index=True,
        on_delete=SET_DEFAULT)

    # Juju expects the following standard constraints, which are stored here
    # as a basic optimisation over querying the lshw output.
    cpu_count = IntegerField(default=0)
    memory = IntegerField(default=0)
    storage = IntegerField(default=0)

    # For strings, Django insists on abusing the empty string ("blank")
    # to mean "none."
    # The possible choices for this field depend on the power types
    # advertised by the clusters.  This needs to be populated on the fly,
    # in forms.py, each time the form to edit a node is instantiated.
    power_type = CharField(
        max_length=10, null=False, blank=True, default='')

    # JSON-encoded set of parameters for power control.
    power_parameters = JSONObjectField(blank=True, default="")

    token = ForeignKey(
        Token, db_index=True, null=True, editable=False, unique=False)

    error = CharField(max_length=255, blank=True, default='')

    netboot = BooleanField(default=True)

    license_key = CharField(max_length=30, null=True, blank=True)

    # This field can't be null, but we can't enforce that in the
    # database schema because we can only create the default value from
    # a complete schema, after schema migration.  We can't use custom
    # model validation either, because the node forms need to set their
    # default values *after* saving the form (with commit=False), which
    # incurs validation before the default values are set.
    # So all we can do is set blank=False, and make the field editable
    # to cajole Django out of skipping it during "model" (actually model
    # form) validation.
    nodegroup = ForeignKey(
        'maasserver.NodeGroup', editable=True, null=True, blank=False)

    tags = ManyToManyField(Tag)

    objects = NodeManager()

    def __unicode__(self):
        if self.hostname:
            return "%s (%s)" % (self.system_id, self.fqdn)
        else:
            return self.system_id

    @property
    def fqdn(self):
        """Fully qualified domain name for this node.

        If MAAS manages DNS for this node, the domain part of the
        hostname (if present), is replaced by the domain configured
        on the cluster controller.
        If not, simply return the node's hostname.
        """
        if self.nodegroup.manages_dns():
            # If the hostname field contains a domain, strip it.
            hostname = strip_domain(self.hostname)
            # Build the FQDN by using the hostname and nodegroup.name
            # as the domain name.
            return '%s.%s' % (hostname, self.nodegroup.name)
        else:
            return self.hostname

    def claim_static_ips(self):
        """Assign AUTO static IPs for our MACs and return a list of
        Celery tasks that need executing.  If nothing needs executing,
        the empty list is returned.

        Each MAC on the node that is connected to a managed cluster
        interface will get an IP.

        This operation is atomic; if claiming an IP on a particular MAC fails
        then none of the MACs will get an IP and StaticIPAddressExhaustion
        is raised.
        """
        try:
            tasks = self._create_tasks_for_static_ips()
        except StaticIPAddressExhaustion:
            StaticIPAddress.objects.deallocate_by_node(self)
            raise

        # Update the DNS zone with the new static IP info as necessary.
        from maasserver.dns import change_dns_zones
        change_dns_zones([self.nodegroup])
        return tasks

    def _create_hostmap_task(self, mac, sip):
        # This is creating a list of celery 'Signatures' which will be
        # chained together later.  Normally the result of each
        # chained task is passed to the next, but we don't want that
        # here.  We can avoid it by making the Signatures
        # "immutable", and this is done with the "si()" call on the
        # task, which produces an immutable Signature.
        # See docs.celeryproject.org/en/latest/userguide/canvas.html
        dhcp_key = self.nodegroup.dhcp_key
        mapping = {sip.ip: mac.mac_address.get_raw()}
        # XXX See bug 1039362 regarding server_address.
        dhcp_task = add_new_dhcp_host_map.si(
            mappings=mapping, server_address='127.0.0.1',
            shared_key=dhcp_key)
        dhcp_task.set(queue=self.work_queue)
        return dhcp_task

    def _create_tasks_for_static_ips(self):
        tasks = []
        # Get a new AUTO static IP for each MAC on a managed interface.
        macs = self.mac_addresses_on_managed_interfaces()
        for mac in macs:
            try:
                sip = mac.claim_static_ip()
            except StaticIPAddressTypeClash:
                # There's already a non-AUTO IP, so nothing to do.
                continue
            # "sip" may be None if the static range is not yet
            # defined, which will be the case when migrating from older
            # versions of the code.  If it is None we just ignore this
            # MAC.
            if sip is not None:
                tasks.append(self._create_hostmap_task(mac, sip))
                maaslog.info(
                    "Claimed static IP %s on %s for %s (%s)", sip.ip,
                    mac.mac_address.get_raw(), self.hostname, self.system_id)
        if len(tasks) > 0:
            # Delete any existing dynamic maps as the first task.  This
            # is a belt and braces approach to deal with legacy code
            # that previously used dynamic IPs for hosts.
            del_existing = self._build_dynamic_host_map_deletion_task()
            if del_existing is not None:
                # del_existing is a chain so does not need an explicit
                # queue to be set as each subtask will have one.
                tasks.insert(0, del_existing)
        return tasks

    def ip_addresses(self):
        """IP addresses allocated to this node.

        Return the current IP addresses for this Node, or the empty
        list if there are none.
        """
        # The static IP addresses are assigned/removed when a node is
        # allocated/deallocated.
        # The dynamic IP addresses are used by enlisting or commissioning
        # nodes.  This information is re-built periodically based on the
        # content of the DHCP lease file, the DB mappings can thus contain
        # outdated information for a short time.  They are returned here
        # for backward-compatiblity reasons (the static IP addresses were
        # introduced after the dynamic IP addresses) as only the static
        # mappings are guaranteed to be, well, static.
        static_ips = self.static_ip_addresses()
        if len(static_ips) != 0:
            return static_ips
        else:
            return self.dynamic_ip_addresses()

    def static_ip_addresses(self):
        """Static IP addresses allocated to this node."""
        # If the macaddresses and the ips have been prefetched (a la
        # nodes = nodes.prefetch_related('macaddress_set__ip_addresses')),
        # use the cache.
        mac_cache = self.macaddress_set.all()._result_cache
        can_use_cache = (
            mac_cache is not None and
            (
                len(mac_cache) == 0
                or
                (
                    len(mac_cache) > 0 and
                    # If the first MAC has its IP addresses cached, assume
                    # we can use the cache for all the MACs.
                    mac_cache[0].ip_addresses.all()._result_cache is not None
                )
            )
        )
        if can_use_cache:
            # The cache is populated: return the static IP addresses of all the
            # node's MAC addresses.
            macs = self.macaddress_set.all()
            node_ip_addresses = [
                [ipaddr.ip for ipaddr in mac.ip_addresses.all()]
                for mac in macs
            ]
            return list(chain(*node_ip_addresses))
        else:
            return StaticIPAddress.objects.filter(
                macaddress__node=self).values_list('ip', flat=True)

    def dynamic_ip_addresses(self):
        """Dynamic IP addresses allocated to this node."""
        macs = [mac.mac_address for mac in self.macaddress_set.all()]
        dhcpleases_qs = self.nodegroup.dhcplease_set.all()
        if dhcpleases_qs._result_cache is not None:
            # If the dhcp lease set has been pre-fetched: use it to
            # extract the IP addresses associated with the nodes' MAC
            # addresses.
            return [lease.ip for lease in dhcpleases_qs if lease.mac in macs]
        else:
            query = dhcpleases_qs.filter(mac__in=macs)
            return query.values_list('ip', flat=True)

    def mac_addresses_on_managed_interfaces(self):
        """Return MACAddresses for this node that have a managed cluster
        interface."""
        # Avoid circular imports
        from maasserver.models import MACAddress
        unmanaged = NODEGROUPINTERFACE_MANAGEMENT.UNMANAGED
        return MACAddress.objects.filter(
            node=self, cluster_interface__isnull=False).exclude(
            cluster_interface__management=unmanaged)

    def tag_names(self):
        # We don't use self.tags.values_list here because this does not
        # take advantage of the cache.
        return [tag.name for tag in self.tags.all()]

    def clean_status(self):
        """Check a node's status transition against the node-status FSM."""
        old_status = get_db_state(self, 'status')
        if self.status == old_status:
            # No transition is always a safe transition.
            pass
        elif self.status in NODE_TRANSITIONS.get(old_status, ()):
            # Valid transition.
            maaslog.debug(
                "Transition status from %s to %s for node %s (%s)", old_status,
                self.status, self.hostname, self.system_id)
            pass
        else:
            # Transition not permitted.
            error_text = "Invalid transition: %s -> %s." % (
                NODE_STATUS_CHOICES_DICT.get(old_status, "Unknown"),
                NODE_STATUS_CHOICES_DICT.get(self.status, "Unknown"),
                )
            raise NodeStateViolation(error_text)

    def clean(self, *args, **kwargs):
        super(Node, self).clean(*args, **kwargs)
        self.clean_status()

    def display_status(self):
        """Return status text as displayed to the user.

        The UI representation is taken from NODE_STATUS_CHOICES_DICT and may
        interpolate the variable "owner" to reflect the username of the node's
        current owner, if any.
        """
        status_text = NODE_STATUS_CHOICES_DICT[self.status]
        if self.status == NODE_STATUS.ALLOCATED:
            # The User is represented as its username in interpolation.
            # Don't just say self.owner.username here, or there will be
            # trouble with unowned nodes!
            return "%s to %s" % (status_text, self.owner)
        else:
            return status_text

    def add_mac_address(self, mac_address):
        """Add a new MAC address to this `Node`.

        :param mac_address: The MAC address to be added.
        :type mac_address: unicode
        :raises: django.core.exceptions.ValidationError_

        .. _django.core.exceptions.ValidationError: https://
           docs.djangoproject.com/en/dev/ref/exceptions/
           #django.core.exceptions.ValidationError
        """
        # Avoid circular imports
        from maasserver.models import MACAddress

        mac = MACAddress(mac_address=mac_address, node=self)
        mac.save()
        return mac

    def remove_mac_address(self, mac_address):
        """Remove a MAC address from this `Node`.

        :param mac_address: The MAC address to be removed.
        :type mac_address: string

        """
        # Avoid circular imports
        from maasserver.models import MACAddress

        mac = MACAddress.objects.get(mac_address=mac_address, node=self)
        if mac:
            mac.delete()

    def accept_enlistment(self, user):
        """Accept this node's (anonymous) enlistment.

        This call makes sense only on a node in Declared state, i.e. one that
        has been anonymously enlisted and is now waiting for a MAAS user to
        accept that enlistment as authentic.  Calling it on a node that is in
        Ready or Commissioning state, however, is not an error -- it probably
        just means that somebody else has beaten you to it.

        :return: This node if it has made the transition from Declared, or
            None if it was already in an accepted state.
        """
        accepted_states = [NODE_STATUS.READY, NODE_STATUS.COMMISSIONING]
        if self.status in accepted_states:
            return None
        if self.status != NODE_STATUS.DECLARED:
            raise NodeStateViolation(
                "Cannot accept node enlistment: node %s is in state %s."
                % (self.system_id, NODE_STATUS_CHOICES_DICT[self.status]))

        self.start_commissioning(user)
        return self

    def start_commissioning(self, user):
        """Install OS and self-test a new node."""
        # Avoid circular imports.
        from metadataserver.commissioning.user_data import generate_user_data
        from metadataserver.models import NodeCommissionResult

        commissioning_user_data = generate_user_data(nodegroup=self.nodegroup)
        NodeCommissionResult.objects.clear_results(self)
        self.status = NODE_STATUS.COMMISSIONING
        self.save()
        # The commissioning profile is handled in start_nodes.
        maaslog.info(
            "Starting commissioning for %s (%s)", self.hostname,
            self.system_id)
        Node.objects.start_nodes(
            [self.system_id], user, user_data=commissioning_user_data)

    def abort_commissioning(self, user):
        """Power off a commissioning node and set its status to 'declared'."""
        if self.status != NODE_STATUS.COMMISSIONING:
            raise NodeStateViolation(
                "Cannot abort commissioning of a non-commissioning node: "
                "node %s is in state %s."
                % (self.system_id, NODE_STATUS_CHOICES_DICT[self.status]))
        maaslog.info(
            "Aborting commissioning for %s (%s)", self.hostname,
            self.system_id)
        stopped_node = Node.objects.stop_nodes([self.system_id], user)
        if len(stopped_node) == 1:
            self.status = NODE_STATUS.DECLARED
            self.save()

    def delete(self):
        # Allocated nodes can't be deleted.
        if self.status == NODE_STATUS.ALLOCATED:
            raise NodeStateViolation(
                "Cannot delete node %s: node is in state %s."
                % (self.system_id, NODE_STATUS_CHOICES_DICT[self.status]))
        maaslog.info("Deleting node %s (%s)", self.hostname, self.system_id)
        # Delete any dynamic host maps in the DHCP server.  This is only
        # here to cope with legacy code that used to create these, the
        # current code does not.
        self._delete_dynamic_host_maps()

        # Delete all remaining static IPs.
        static_ips = StaticIPAddress.objects.delete_by_node(self)
        self.delete_static_host_maps(static_ips)

        # Delete the related mac addresses.
        # The DHCPLease objects corresponding to these MACs will be deleted
        # as well. See maasserver/models/dhcplease:delete_lease().
        self.macaddress_set.all().delete()

        super(Node, self).delete()

    def delete_static_host_maps(self, for_ips):
        """Delete any host maps for static IPs allocated to this node.

        :param for_ips: Delete the maps for these IP addresses only.
        """
        tasks = []
        for ip in for_ips:
            task = remove_dhcp_host_map.si(
                ip_address=ip, server_address="127.0.0.1",
                omapi_key=self.nodegroup.dhcp_key)
            task.set(queue=self.work_queue)
            tasks.append(task)
        if len(tasks) > 0:
            maaslog.info(
                "Asking cluster to delete static host maps for %s (%s)",
                self.hostname, self.system_id)
            chain = celery.chain(tasks)
            chain.apply_async()

    def _build_dynamic_host_map_deletion_task(self):
        """Create a chained celery task that will delete this node's
        dynamic dhcp host maps.

        Host maps in the DHCP server that are as a result of StaticIPAddresses
        are not deleted here as these get deleted when nodes are released
        (for AUTO types) or from a separate user-driven action.

        Return None if there is nothing to delete.
        """
        nodegroup = self.nodegroup
        if len(nodegroup.get_managed_interfaces()) == 0:
            return None

        macs = self.macaddress_set.values_list('mac_address', flat=True)
        static_ips = StaticIPAddress.objects.filter(
            macaddress__mac_address__in=macs).values_list("ip", flat=True)
        # See [1] below for a comment about this use of list():
        leases = DHCPLease.objects.filter(
            mac__in=macs, nodegroup=nodegroup).exclude(
            ip__in=list(static_ips))
        tasks = []
        for lease in leases:
            # XXX See bug 1039362 regarding server_address
            task_kwargs = dict(
                ip_address=lease.ip,
                server_address="127.0.0.1",
                omapi_key=nodegroup.dhcp_key)
            task = remove_dhcp_host_map.si(**task_kwargs)
            task.set(queue=self.work_queue)
            tasks.append(task)
        if len(tasks) > 0:
            return celery.chain(tasks)
        return None

        # [1]
        # Django has a bug (I know, you're shocked, right?) where it
        # casts the outer part of the IN query to a string (from inet
        # type) but fails to cast the result of the subselect arising
        # from the ValuesQuerySet that values_list() produces. The
        # result of that is that you get a Postgres ProgrammingError
        # because of the type mismatch.  This bug is avoided by
        # listifying the static_ips which vastly simplifies the generated
        # SQL as it avoids the subselect.

    def _delete_dynamic_host_maps(self):
        """If any DHCPLeases exist for this node, remove any associated
        host maps."""
        chain = self._build_dynamic_host_map_deletion_task()
        if chain is not None:
            chain.apply_async()

    def set_random_hostname(self):
        """Set 5 character `hostname` using non-ambiguous characters.

        Using 5 letters from the set 'abcdefghjkmnpqrtwxy346789' we get
        9,765,625 combinations (pow(25, 5)).

        Note that having a hostname starting with a number is perfectly
        valid, see
        http://en.wikipedia.org/wiki/Hostname#Restrictions_on_valid_host_names
        """
        domain = Config.objects.get_config("enlistment_domain")
        domain = domain.strip("." + whitespace)
        while True:
            new_hostname = generate_hostname(5)
            if len(domain) > 0:
                self.hostname = "%s.%s" % (new_hostname, domain)
            else:
                self.hostname = "%s" % new_hostname
            try:
                self.save()
            except ValidationError:
                pass
            else:
                break

    def get_effective_power_type(self):
        """Get power-type to use for this node.

        If no power type has been set for the node, raise
        UnknownPowerType.
        """
        if self.power_type == '':
            raise UnknownPowerType("Node power type is unconfigured")
        return self.power_type

    def get_primary_mac(self):
        """Return the primary :class:`MACAddress` for this node."""
        macs = self.macaddress_set.order_by('created')[:1]
        if len(macs) > 0:
            return macs[0]
        else:
            return None

    def get_effective_kernel_options(self):
        """Determine any special kernel parameters for this node.

        :return: (tag, kernel_options)
            tag is a Tag object or None. If None, the kernel_options came from
            the global setting.
            kernel_options, a string indicating extra kernel_options that
            should be used when booting this node. May be None if no tags match
            and no global setting has been configured.
        """
        # First, see if there are any tags associated with this node that has a
        # custom kernel parameter
        tags = self.tags.filter(kernel_opts__isnull=False)
        tags = tags.order_by('name')
        for tag in tags:
            if tag.kernel_opts != '':
                return tag, tag.kernel_opts
        global_value = Config.objects.get_config('kernel_opts')
        return None, global_value

    @property
    def work_queue(self):
        """The name of the queue for tasks specific to this node."""
        return self.nodegroup.work_queue

    def get_osystem(self):
        """Return the operating system to install that node."""
        use_default_osystem = (self.osystem is None or self.osystem == '')
        if use_default_osystem:
            return Config.objects.get_config('default_osystem')
        else:
            return self.osystem

    def get_distro_series(self):
        """Return the distro series to install that node."""
        use_default_osystem = (
            self.osystem is None or
            self.osystem == '')
        use_default_distro_series = (
            self.distro_series is None or
            self.distro_series == '')
        if use_default_osystem and use_default_distro_series:
            return Config.objects.get_config('default_distro_series')
        elif use_default_distro_series:
            osystem = OperatingSystemRegistry[self.osystem]
            return osystem.get_default_release()
        else:
            return self.distro_series

    def get_effective_license_key(self):
        """Return effective license key.

        This returns the license key that should be used during the
        installation of the operating system for this node. This method first
        checks to see if the node has a specific license key set, if not then
        the license key registry is checked, if neither exists for this node or
        the booting operating system and release combination then an empty
        string is returned. An empty string can mean two things, one the
        operating system does not require a license key, or the installation
        media already has the license key builtin.
        """
        use_global_license_key = (
            self.license_key is None or
            self.license_key == '')
        if use_global_license_key:
            osystem = self.get_osystem()
            distro_series = self.get_distro_series()
            try:
                return LicenseKey.objects.get_license_key(
                    osystem, distro_series)
            except LicenseKey.DoesNotExist:
                return ''
        else:
            return self.license_key

    def get_effective_power_parameters(self):
        """Return effective power parameters, including any defaults."""
        if self.power_parameters:
            power_params = self.power_parameters.copy()
        else:
            # An empty power_parameters comes out as an empty unicode string!
            power_params = {}

        power_params.setdefault('system_id', self.system_id)
        # TODO: We should not be sending these paths to the templates;
        # the templates ought to know which tool to use themselves.
        power_params.setdefault('fence_cdu', '/usr/sbin/fence_cdu')
        power_params.setdefault('ipmipower', '/usr/sbin/ipmipower')
        power_params.setdefault('ipmitool', '/usr/bin/ipmitool')
        power_params.setdefault(
            'ipmi_chassis_config', '/usr/sbin/ipmi-chassis-config')
        power_params.setdefault('ipmi_config', 'ipmi.conf')
        # TODO: /end of paths that templates should know.
        # TODO: This default ought to be in the virsh template.
        if self.power_type == "virsh":
            power_params.setdefault(
                'power_address', 'qemu://localhost/system')
        else:
            power_params.setdefault('power_address', "")
        power_params.setdefault('username', '')
        power_params.setdefault('power_id', self.system_id)
        power_params.setdefault('power_driver', '')
        power_params.setdefault('power_pass', '')
        power_params.setdefault('power_off_mode', '')

        # The "mac" parameter defaults to the node's primary MAC
        # address, but only if not already set.
        if 'mac_address' not in power_params:
            primary_mac = self.get_primary_mac()
            if primary_mac is not None:
                mac = primary_mac.mac_address.get_raw()
                power_params['mac_address'] = mac
        return power_params

    def acquire(self, user, token=None, agent_name=''):
        """Mark commissioned node as acquired by the given user and token."""
        assert self.owner is None
        assert token is None or token.user == user
        self.status = NODE_STATUS.ALLOCATED
        self.owner = user
        self.agent_name = agent_name
        self.token = token
        self.save()
        maaslog.info(
            "Node %s (%s) allocated to user %s", self.hostname, self.system_id,
            user.username)

    def release(self):
        """Mark allocated or reserved node as available again and power off."""
        maaslog.info("Releasing node %s (%s)", self.hostname, self.system_id)
        Node.objects.stop_nodes([self.system_id], self.owner)
        deallocated_ips = StaticIPAddress.objects.deallocate_by_node(self)
        self.delete_static_host_maps(deallocated_ips)
        from maasserver.dns import change_dns_zones
        change_dns_zones([self.nodegroup])
        self.status = NODE_STATUS.READY
        self.owner = None
        self.token = None
        self.agent_name = ''
        self.set_netboot()
        self.osystem = ''
        self.distro_series = ''
        self.license_key = ''
        self.save()

    def set_netboot(self, on=True):
        """Set netboot on or off."""
        maaslog.debug(
            "Turning on netboot for node %s (%s)", self.hostname,
            self.system_id)
        self.netboot = on
        self.save()

    def split_arch(self):
        """Return architecture and subarchitecture, as a tuple."""
        arch, subarch = self.architecture.split('/')
        return (arch, subarch)

    def mark_broken(self, error_description):
        """Mark this node as 'BROKEN'.

        If the node is allocated, release it first.
        """
        maaslog.info(
            "Marking node broken: %s (%s)", self.hostname, self.system_id)
        if self.status == NODE_STATUS.ALLOCATED:
            self.release()
        self.status = NODE_STATUS.BROKEN
        self.error_description = error_description
        self.save()

    def mark_fixed(self):
        """Mark a broken node as fixed and change its state to 'READY'."""
        if self.status != NODE_STATUS.BROKEN:
            raise NodeStateViolation(
                "Can't mark a non-broken node as 'Ready'.")
        maaslog.info(
            "Marking node fixed: %s (%s)", self.hostname, self.system_id)
        self.status = NODE_STATUS.READY
        self.error_description = ''
        self.save()
