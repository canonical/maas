# Copyright 2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Respond to DNSResource changes."""

from django.db.models.signals import m2m_changed, post_delete, post_save
from netaddr import IPAddress

from maascommon.enums.dns import DnsUpdateAction
from maasserver.models import (
    Config,
    DNSPublication,
    DNSResource,
    StaticIPAddress,
)
from maasserver.utils.signals import SignalsManager

signals = SignalsManager()


def post_created_dns_publication(sender, instance, created, **kwargs):
    if created:
        domain_name = instance.domain.name
        DNSPublication.objects.create_for_config_update(
            source=f"zone {domain_name} added resource {instance.name}",
            action=DnsUpdateAction.RELOAD,
        )


def post_delete_dns_publication(sender, instance, **kwargs):
    domain_name = instance.domain.name
    DNSPublication.objects.create_for_config_update(
        source=f"zone {domain_name} removed resource {instance.name}",
        action=DnsUpdateAction.RELOAD,
    )


def updated_fields(instance, old_values, **kwargs):
    [old_domain_id, old_name, old_address_ttl] = old_values
    changes = []
    if old_name != instance.name or old_address_ttl != instance.address_ttl:
        changes.append(f"updated resource {instance.name}")
    if old_domain_id != instance.domain_id:
        changes.append(
            f"resource {instance.name} moved to {instance.domain.name}"
        )
    if changes:
        DNSPublication.objects.create_for_config_update(
            source=f"zone {instance.domain.name} changes: {', '.join(changes)}",
            action=DnsUpdateAction.RELOAD,
        )


def _resolve_ttl(dnsrr):
    default_ttl = Config.objects.get_config("default_dns_ttl")
    return dnsrr.address_ttl or dnsrr.domain.ttl or default_ttl


def dnsresource_ip_addresses_changed(
    sender, instance, action, reverse, model, pk_set, **kwargs
):
    # Only act on forward (DNSResource) side.
    if not isinstance(instance, DNSResource):
        return
    if model is not StaticIPAddress:
        return
    if action not in ("post_add", "post_remove"):
        return
    if not pk_set:
        return

    dnsrr = instance
    domain = dnsrr.domain
    ttl = _resolve_ttl(dnsrr)

    # Fetch affected IPs.
    for sip in StaticIPAddress.objects.filter(pk__in=pk_set):
        if not sip.ip:
            continue
        ip_str = str(sip.ip).strip()
        if not ip_str:
            continue
        rtype = "A" if IPAddress(ip_str).version == 4 else "AAAA"

        if action == "post_add":
            # link
            DNSPublication.objects.create_for_config_update(
                source=f"ip {ip_str} linked to resource {dnsrr.name or 'NULL'} on zone {domain.name}",
                action=DnsUpdateAction.INSERT,
                zone=domain.name,
                label=dnsrr.name or "@",
                ttl=ttl,
                rtype=rtype,
                answer=ip_str,
            )
        elif action == "post_remove":
            # unlink
            DNSPublication.objects.create_for_config_update(
                source=f"ip {ip_str} unlinked from resource {dnsrr.name or 'NULL'} on zone {domain.name}",
                action=DnsUpdateAction.DELETE,
                zone=domain.name,
                label=dnsrr.name or "@",
                ttl=ttl,
                rtype=rtype,
                answer=ip_str,
            )


signals.watch(post_save, post_created_dns_publication, sender=DNSResource)
signals.watch(post_delete, post_delete_dns_publication, sender=DNSResource)
signals.watch_fields(
    updated_fields,
    DNSResource,
    ["domain_id", "name", "address_ttl"],
    delete=False,
)
signals.watch(
    m2m_changed,
    dnsresource_ip_addresses_changed,
    DNSResource.ip_addresses.through,
)

# Enable all signals by default.
signals.enable()
