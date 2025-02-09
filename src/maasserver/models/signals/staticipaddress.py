# Copyright 2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Respond to staticipaddress changes."""

from django.core.exceptions import ObjectDoesNotExist
from django.db.models.signals import (
    post_delete,
    post_init,
    post_save,
    pre_delete,
    pre_save,
)

from maasserver.models import StaticIPAddress
from maasserver.utils.signals import SignalsManager
from provisioningserver.logger import LegacyLogger

log = LegacyLogger()
signals = SignalsManager()


def pre_delete_record_relations_on_delete(sender, instance, **kwargs):
    """Store the instance's bmc_set for use in post_delete.

    It is coerced to a set to force it to be evaluated here in the pre_delete
    handler. Otherwise, the call will be deferred until evaluated in
    post_delete, where the results will be invalid because the instance will be
    gone.

    This information is necessary so any BMC's using this deleted IP address
    can be called on in post_delete to make their own StaticIPAddresses.
    """
    instance.__previous_bmcs = set(instance.bmc_set.all())
    instance.__previous_dnsresources = set(instance.dnsresource_set.all())


signals.watch(
    pre_delete, pre_delete_record_relations_on_delete, sender=StaticIPAddress
)


def post_delete_remake_sip_for_bmc(sender, instance, **kwargs):
    """Now that the StaticIPAddress instance is gone, ask each BMC that was
    using it to make a new one.

    When a StaticIPAddress is deleted, any BMC models sharing it will
    automatically set their ip_address links to None. They are then recreated
    here in post_delete.
    """
    for bmc in instance.__previous_bmcs:
        # This BMC model instance was created in pre_delete and hasn't been
        # updated to reflect the just executed deletion. Set the ip_address to
        # None to replicate this. We can avoid the DB hit as we always want a
        # new StaticIPAddress instance to be created by save().
        bmc.ip_address = None
        # BMC.save() will extract and create a new IP from power_parameters.
        bmc.save()


signals.watch(
    post_delete, post_delete_remake_sip_for_bmc, sender=StaticIPAddress
)


def post_delete_clean_up_dns(sender, instance, **kwargs):
    """Now that the StaticIPAddress instance is gone, check if any related
    DNS records should be deleted.
    """
    for dnsrr in instance.__previous_dnsresources:
        if not dnsrr.ip_addresses.exists():
            dnsrr.delete()
            log.msg(
                "Removed orphan DNS record '%s' for deleted IP address '%s'."
                % (dnsrr.fqdn, instance.ip)
            )


signals.watch(post_delete, post_delete_clean_up_dns, sender=StaticIPAddress)


def post_init_store_previous_ip(sender, instance, **kwargs):
    """Store the pre_save IP address of the instance.

    This is used in post_save to detect if the IP address has been changed by
    that save.
    """
    instance.__previous_ip = instance.ip


signals.watch(post_init, post_init_store_previous_ip, sender=StaticIPAddress)


def pre_save_prevent_conflicts(sender, instance, **kwargs):
    """If this sip's IP address is about to be changed in the DB, check if any
    other sip instances are using this IP and delete them.

    After this, in post_save, we will cause any affected BMC instances to
    recreate their ip_address links, which should then point at this instance.
    To do this, we store them in instance.__bmcs_to_update.
    """
    instance.__bmcs_to_update = set()
    if instance.__previous_ip == instance.ip:
        # The IP address wasn't modified, nothing to do.
        return

    if instance.pk is not None:
        instance.__bmcs_to_update = set(instance.bmc_set.all())
    ips_to_delete = []

    # If any sip is using this address, delete it. Record in our instance any
    # BMCs using the doomed sip so we can update them later in post_save.
    conflicting_sip = StaticIPAddress.objects.filter(ip=instance.ip).first()
    if conflicting_sip is not None:
        for bmc in conflicting_sip.bmc_set.all():
            ips_to_delete.append(bmc.ip_address)
            instance.__bmcs_to_update.add(bmc)

    # Delete the conflicting IP's before the instance is saved.
    for ip in ips_to_delete:
        ip.bmc_set.clear()
        ip.delete()


signals.watch(pre_save, pre_save_prevent_conflicts, sender=StaticIPAddress)


def post_save_prevent_conflicts(sender, instance, created, **kwargs):
    """Fix up BMCs that had their SIP's nullified in pre_save.

    These BMCs were identified in pre_save and stored in the instance for
    reference in this handler.
    """
    instance.__previous_ip = instance.ip
    for bmc in instance.__bmcs_to_update:
        # Save the BMC so it can re-extract its IP from power_parameters.
        bmc.ip_address = None
        bmc.save()
    instance.__bmcs_to_update = set()


signals.watch(post_save, post_save_prevent_conflicts, sender=StaticIPAddress)


def post_save_check_range_utilization(sender, instance, created, **kwargs):
    # Be careful when checking for the subnet. In rare cases, such as a
    # cascading delete, Django can sometimes pass stale model objects into
    # signal handlers, which will raise unexpected DoesNotExist exceptions,
    # and/or otherwise invalidate foreign key fields.
    # See bug #1702527 for more details.
    try:
        if instance.subnet is None:
            return
    except ObjectDoesNotExist:
        return
    instance.subnet.update_allocation_notification()


def post_delete_check_range_utilization(sender, instance, **kwargs):
    # Be careful when checking for the subnet. In rare cases, such as a
    # cascading delete, Django can sometimes pass stale model objects into
    # signal handlers, which will raise unexpected DoesNotExist exceptions,
    # and/or otherwise invalidate foreign key fields.
    # See bug #1702527 for more details.
    try:
        if instance.subnet is None:
            return
    except ObjectDoesNotExist:
        return
    instance.subnet.update_allocation_notification()


signals.watch(
    post_save, post_save_check_range_utilization, sender=StaticIPAddress
)
signals.watch(
    post_delete, post_delete_check_range_utilization, sender=StaticIPAddress
)


# Enable all signals by default.
signals.enable()
