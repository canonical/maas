# Copyright 2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""FanNetwork objects."""


from django.core.exceptions import PermissionDenied, ValidationError
from django.core.validators import RegexValidator
from django.db.models import (
    CharField,
    Manager,
    NullBooleanField,
    PositiveIntegerField,
)
from django.shortcuts import get_object_or_404
from netaddr import IPNetwork

from maasserver import DefaultMeta
from maasserver.fields import IPv4CIDRField, MODEL_NAME_VALIDATOR
from maasserver.models.cleansave import CleanSave
from maasserver.models.timestampedmodel import TimestampedModel

FANNETWORK_BRIDGE_VALIDATOR = RegexValidator(r"^[\w\-_]+$")


class FanNetworkManager(Manager):
    """Manager for :class:`FanNetwork` model."""

    def get_fannetwork_or_404(self, id, user, perm):
        """Fetch a `FanNetwork` by its id.  Raise exceptions if no
        `FanNetwork` with this id exist or if the provided user has not the
         required permission to access this `FanNetwork`.

        :param id: The fannetwork_id.
        :type id: int
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
        fannetwork = get_object_or_404(self.model, id=id)
        if user.has_perm(perm, fannetwork):
            return fannetwork
        else:
            raise PermissionDenied()


class FanNetwork(CleanSave, TimestampedModel):
    """A `FanNetwork`.

    :ivar name: The short-human-identifiable name for this fannetwork.
    :ivar objects: An instance of the class :class:`FanNetworkManager`.
    """

    class Meta(DefaultMeta):
        """Needed for South to recognize this model."""

        verbose_name = "Fan Network"
        verbose_name_plural = "Fan Networks"

    objects = FanNetworkManager()

    # required fields
    name = CharField(
        max_length=256,
        unique=True,
        editable=True,
        help_text="Name of the fan network",
        validators=[MODEL_NAME_VALIDATOR],
    )

    overlay = IPv4CIDRField(
        blank=False, unique=True, editable=True, null=False
    )

    underlay = IPv4CIDRField(
        blank=False, unique=True, editable=True, null=False
    )

    # optional fields
    dhcp = NullBooleanField(blank=True, unique=False, editable=True, null=True)

    host_reserve = PositiveIntegerField(
        default=1, blank=True, unique=False, editable=True, null=True
    )

    bridge = CharField(
        blank=True,
        editable=True,
        max_length=255,
        null=True,
        help_text="If specified, this bridge name is used on the hosts",
        validators=[FANNETWORK_BRIDGE_VALIDATOR],
    )

    off = NullBooleanField(
        default=False,
        unique=False,
        editable=True,
        null=True,
        blank=True,
        help_text="Create the configuration, but mark it as 'off'",
    )

    def __str__(self):
        return "name=%s underlay=%s overlay=%s" % (
            self.name,
            self.underlay,
            self.overlay,
        )

    def clean_overlay(self):
        if self.overlay is None or self.overlay == "":
            return
        if self.underlay is None or self.underlay == "":
            return
        overlay_prefix = IPNetwork(self.overlay).prefixlen
        underlay_prefix = IPNetwork(self.underlay).prefixlen
        slice_bits = underlay_prefix - overlay_prefix
        if slice_bits <= 2:
            raise ValidationError(
                {"overlay": ["Overlay network is too small for underlay."]}
            )
        elif slice_bits >= 30:
            raise ValidationError(
                {"overlay": ["Overlay network is too big for underlay."]}
            )
        # by this point, we know that overlay is bigger.  Make sure that it
        # does not contain the underlay network.
        if self.underlay in self.overlay:
            raise ValidationError(
                {"overlay": ["Overlay network contains underlay network."]}
            )

    def clean_host_reserve(self):
        if self.overlay is None or self.overlay == "":
            return
        if self.underlay is None or self.underlay == "":
            return
        overlay_prefix = IPNetwork(self.overlay).prefixlen
        underlay_prefix = IPNetwork(self.underlay).prefixlen
        slice_bits = underlay_prefix - overlay_prefix
        if self.host_reserve < 1:
            raise ValidationError({"host_reserve": ["Minimum value is 1"]})
        # The docs talk about 250 being the max host_reserve for a /8 slice.
        if self.host_reserve > (1 << slice_bits) - 6:
            raise ValidationError(
                {
                    "host_reserve": [
                        "Value is too large for the overlay network."
                    ]
                }
            )

    def clean(self, *args, **kwargs):
        super().clean(*args, **kwargs)
        self.clean_overlay()
        self.clean_host_reserve()
