# Copyright 2020 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

import re

from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, RegexValidator
from django.db.models import (
    CASCADE,
    CharField,
    ForeignKey,
    IntegerField,
    OneToOneField,
    PositiveIntegerField,
)

from maasserver.enum import NODE_DEVICE_BUS, NODE_DEVICE_BUS_CHOICES
from maasserver.models.cleansave import CleanSave
from maasserver.models.timestampedmodel import TimestampedModel
from metadataserver.enum import HARDWARE_TYPE, HARDWARE_TYPE_CHOICES

# PCIE and USB vendor and product ids are represented as a 2 byte hex string
DEVICE_ID_REGEX = re.compile(r"^[\da-f]{4}$", re.I)
BDF_REGEX = re.compile(
    r"^(?P<domain>[\da-f]+:)?"
    r"(?P<bus>[\da-f]+):"
    r"(?P<device>[\da-f]+)[.]"
    r"(?P<function>[\da-f]+)"
    r"(@(?P<extension>.*))?$",
    re.I,
)


def translate_bus(bus):
    if isinstance(bus, int) or bus.isdigit():
        bus = int(bus)
        for id, _ in NODE_DEVICE_BUS_CHOICES:
            if bus == id:
                return bus
        raise ValidationError("Invalid bus numeric value!")
    elif bus in ["PCIE", "pcie"]:
        return NODE_DEVICE_BUS.PCIE
    elif bus in ["USB", "usb"]:
        return NODE_DEVICE_BUS.USB
    else:
        raise ValidationError("Bus must be PCIE or USB!")


class NodeDevice(CleanSave, TimestampedModel):
    class Meta:
        unique_together = [
            ("node", "bus_number", "device_number", "pci_address")
        ]

    bus = IntegerField(choices=NODE_DEVICE_BUS_CHOICES, editable=False)

    hardware_type = IntegerField(
        choices=HARDWARE_TYPE_CHOICES, default=HARDWARE_TYPE.NODE
    )

    node = ForeignKey(
        "Node", related_name="node_devices", on_delete=CASCADE, editable=False
    )

    numa_node = ForeignKey(
        "NUMANode", related_name="node_devices", on_delete=CASCADE
    )

    # Only used if the NodeDevice is a PhysicalBlockDevice directly attached
    # to a bus(e.g NVMe)
    physical_blockdevice = OneToOneField(
        "PhysicalBlockDevice",
        related_name="node_device",
        editable=False,
        blank=True,
        null=True,
        on_delete=CASCADE,
    )

    physical_interface = OneToOneField(
        "PhysicalInterface",
        related_name="node_device",
        editable=False,
        blank=True,
        null=True,
        on_delete=CASCADE,
    )

    # Vendor and product IDs are defined in the hardware and never change
    vendor_id = CharField(
        max_length=4,
        validators=[
            RegexValidator(DEVICE_ID_REGEX, "Must be an 8 byte hex value")
        ],
        blank=False,
        null=False,
        editable=False,
    )

    product_id = CharField(
        max_length=4,
        validators=[
            RegexValidator(DEVICE_ID_REGEX, "Must be an 8 byte hex value")
        ],
        blank=False,
        null=False,
        editable=False,
    )

    # Vendor and product names come from a database which is shipped with
    # Ubuntu. This can change as the database learns about new devices.
    # PCIE: https://pci-ids.ucw.cz/
    # USB: http://www.linux-usb.org/usb-ids.html
    vendor_name = CharField(max_length=256, blank=True, null=False)

    product_name = CharField(max_length=256, blank=True, null=False)

    # The driver detected during commissioning
    commissioning_driver = CharField(max_length=256, blank=True, null=False)

    # Both PCIE and USB bus types have a bus_number and device_number but only
    # PCIE devices have a pci_address. LXD directly provides the bus device
    # number for USB devices but MAAS has to parse it from the pci_address
    # for PCIE devices.
    bus_number = PositiveIntegerField(
        validators=[MaxValueValidator(2 ** 16)], blank=False, null=False
    )

    device_number = PositiveIntegerField(
        validators=[MaxValueValidator(2 ** 16)], blank=False, null=False
    )

    # The PCI address is expressed in BDF notation
    # https://wiki.xenproject.org/wiki/Bus:Device.Function_(BDF)_Notation
    pci_address = CharField(
        max_length=64,
        validators=[RegexValidator(BDF_REGEX, "Must use BDF notation")],
        blank=True,
        null=True,
    )

    def __str__(self):
        ret = f"{self.vendor_id}:{self.product_id}"
        if self.vendor_name or self.product_name:
            ret = f"{ret} -"
        if self.vendor_name:
            ret = f"{ret} {self.vendor_name}"
        if self.product_name:
            ret = f"{ret} {self.product_name}"
        return ret

    @property
    def is_pcie(self):
        return self.bus == NODE_DEVICE_BUS.PCIE

    @property
    def is_usb(self):
        return self.bus == NODE_DEVICE_BUS.USB

    def save(self, *args, **kwargs):
        if self.is_pcie and None in (self.bus_number, self.device_number):
            m = BDF_REGEX.search(self.pci_address)
            self.bus_number = int(m.group("bus"), 16)
            self.device_number = int(m.group("device"), 16)
            if "update_fields" in kwargs:
                kwargs["update_fields"] += ["bus_number", "device_number"]
        if self.is_usb and self.pci_address is not None:
            raise ValidationError(
                {"pci_address": ["Cannot be set on a USB device!"]}
            )
        return super().save(*args, **kwargs)
