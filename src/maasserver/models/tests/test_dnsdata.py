# Copyright 2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).


import random
import re

from django.core.exceptions import PermissionDenied, ValidationError

from maasserver.models.config import Config
from maasserver.models.dnsdata import DNSData, HostnameRRsetMapping
from maasserver.models.domain import Domain
from maasserver.models.node import Node
from maasserver.permissions import NodePermission
from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASServerTestCase

# duplicated from dnsdata.py so as to not export them
INVALID_CNAME_MSG = "Invalid CNAME: Should be '<server>'."
INVALID_MX_MSG = (
    "Invalid MX: Should be '<preference> <server>'."
    " Range for preference is 0-65535."
)
INVALID_SRV_MSG = (
    "Invalid SRV: Should be '<priority> <weight> <port> <server>'."
    " Range for priority, weight, and port are 0-65536."
)
INVALID_SSHFP_MSG = (
    "Invalid SSHFP: Should be '<algorithm> <fptype> <fingerprint>'."
)
CNAME_AND_OTHER_MSG = (
    "CNAME records for a name cannot coexist with non-CNAME records."
)
MULTI_CNAME_MSG = "Only one CNAME can be associated with a name."


class TestDNSDataManagerGetDNSDataOr404(MAASServerTestCase):
    def test_user_view_returns_dnsdata(self):
        user = factory.make_User()
        dnsdata = factory.make_DNSData()
        self.assertEqual(
            dnsdata,
            DNSData.objects.get_dnsdata_or_404(
                dnsdata.id, user, NodePermission.view
            ),
        )

    def test_user_edit_raises_PermissionError(self):
        user = factory.make_User()
        dnsdata = factory.make_DNSData()
        self.assertRaises(
            PermissionDenied,
            DNSData.objects.get_dnsdata_or_404,
            dnsdata.id,
            user,
            NodePermission.edit,
        )

    def test_user_admin_raises_PermissionError(self):
        user = factory.make_User()
        dnsdata = factory.make_DNSData()
        self.assertRaises(
            PermissionDenied,
            DNSData.objects.get_dnsdata_or_404,
            dnsdata.id,
            user,
            NodePermission.admin,
        )

    def test_admin_view_returns_dnsdata(self):
        admin = factory.make_admin()
        dnsdata = factory.make_DNSData()
        self.assertEqual(
            dnsdata,
            DNSData.objects.get_dnsdata_or_404(
                dnsdata.id, admin, NodePermission.view
            ),
        )

    def test_admin_edit_returns_dnsdata(self):
        admin = factory.make_admin()
        dnsdata = factory.make_DNSData()
        self.assertEqual(
            dnsdata,
            DNSData.objects.get_dnsdata_or_404(
                dnsdata.id, admin, NodePermission.edit
            ),
        )

    def test_admin_admin_returns_dnsdata(self):
        admin = factory.make_admin()
        dnsdata = factory.make_DNSData()
        self.assertEqual(
            dnsdata,
            DNSData.objects.get_dnsdata_or_404(
                dnsdata.id, admin, NodePermission.admin
            ),
        )


class TestDNSData(MAASServerTestCase):
    def test_creates_dnsdata(self):
        name = factory.make_name("name")
        domain = factory.make_Domain()
        dnsdata = factory.make_DNSData(name=name, domain=domain)
        from_db = DNSData.objects.get(dnsresource__name=name)
        self.assertEqual(
            (from_db.dnsresource.name, from_db.id), (name, dnsdata.id)
        )

    # The following tests intentionally pass in a lowercase rrtype,
    # which will be upshifted in the creation of the DNSData record.
    def test_creates_cname(self):
        name = factory.make_name("name")
        dnsdata = factory.make_DNSData(rrtype="cname", name=name)
        from_db = DNSData.objects.get(dnsresource__name=name)
        self.assertEqual((from_db.id, from_db.rrtype), (dnsdata.id, "CNAME"))

    def test_creates_cname_with_underscore(self):
        name = factory.make_name("na_me")
        dnsdata = factory.make_DNSData(rrtype="cname", name=name)
        from_db = DNSData.objects.get(dnsresource__name=name)
        self.assertEqual((from_db.id, from_db.rrtype), (dnsdata.id, "CNAME"))

    def test_rejects_bad_cname_target(self):
        target = factory.make_name("na*e")
        dnsresource = factory.make_DNSResource(no_ip_addresses=True)
        dnsdata = DNSData(
            dnsresource=dnsresource, rrtype="CNAME", rrdata=target
        )
        with self.assertRaisesRegex(
            ValidationError,
            re.escape("{'__all__': [\"%s\"]}" % INVALID_CNAME_MSG),
        ):
            dnsdata.save()

    def test_rejects_bad_srv(self):
        self.assertRaises(
            ValidationError, factory.make_DNSData, rrtype="SRV", rrdata=""
        )

    def test_rejects_bad_sshfp_record(self):
        dnsresource = factory.make_DNSResource(no_ip_addresses=True)
        dnsdata = DNSData(
            dnsresource=dnsresource, rrtype="SSHFP", rrdata="wrong data"
        )
        with self.assertRaisesRegex(
            ValidationError,
            re.escape("{'__all__': [\"%s\"]}" % INVALID_SSHFP_MSG),
        ):
            dnsdata.save()

    def test_creates_mx(self):
        name = factory.make_name("name")
        dnsdata = factory.make_DNSData(rrtype="mx", name=name)
        from_db = DNSData.objects.get(dnsresource__name=name)
        self.assertEqual((from_db.id, from_db.rrtype), (dnsdata.id, "MX"))

    def test_creates_ns(self):
        name = factory.make_name("name")
        dnsdata = factory.make_DNSData(rrtype="ns", name=name)
        from_db = DNSData.objects.get(dnsresource__name=name)
        self.assertEqual((from_db.id, from_db.rrtype), (dnsdata.id, "NS"))

    def test_creates_srv(self):
        service = factory.make_name(size=5)
        proto = factory.make_name(size=5)
        name = factory.make_name("name")
        target = factory.make_name("name")
        srv_name = f"_{service}._{proto}.{name}"
        data = "%d %d %d %s" % (
            random.randint(0, 65535),
            random.randint(0, 65535),
            random.randint(1, 65535),
            target,
        )
        dnsdata = factory.make_DNSData(
            rrtype="srv", rrdata=data, name=srv_name
        )
        from_db = DNSData.objects.get(dnsresource__name=srv_name)
        self.assertEqual(
            (
                from_db.dnsresource.name,
                from_db.id,
                from_db.rrtype,
                from_db.rrdata,
            ),
            (srv_name, dnsdata.id, "SRV", data),
        )

    def test_creates_txt(self):
        name = factory.make_name("name")
        dnsdata = factory.make_DNSData(rrtype="txt", name=name)
        from_db = DNSData.objects.get(dnsresource__name=name)
        self.assertEqual((from_db.id, from_db.rrtype), (dnsdata.id, "TXT"))

    def test_rejects_cname_with_address(self):
        name = factory.make_name("name")
        target = factory.make_name("target")
        domain = factory.make_Domain()
        dnsrr = factory.make_DNSResource(name=name, domain=domain)
        dnsrr.save()
        dnsdata = DNSData(dnsresource=dnsrr, rrtype="CNAME", rrdata=target)
        with self.assertRaisesRegex(
            ValidationError,
            re.escape("{'__all__': ['%s']}" % CNAME_AND_OTHER_MSG),
        ):
            dnsdata.save()

    def test_rejects_cname_with_other_data(self):
        name = factory.make_name("name")
        target = factory.make_name("target")
        domain = factory.make_Domain()
        rrtype = random.choice(["MX", "NS", "TXT"])
        dnsrr = factory.make_DNSData(
            name=name, domain=domain, no_ip_addresses=True, rrtype=rrtype
        ).dnsresource
        dnsdata = DNSData(dnsresource=dnsrr, rrtype="CNAME", rrdata=target)
        with self.assertRaisesRegex(
            ValidationError,
            re.escape("{'__all__': ['%s']}" % CNAME_AND_OTHER_MSG),
        ):
            dnsdata.save()

    def test_allows_multiple_records_unless_cname(self):
        dnsdata = factory.make_DNSData(no_ip_addresses=True)
        if dnsdata.rrtype == "CNAME":
            with self.assertRaisesRegex(
                ValidationError,
                re.escape("{'__all__': ['%s']}" % MULTI_CNAME_MSG),
            ):
                factory.make_DNSData(
                    dnsresource=dnsdata.dnsresource, rrtype="CNAME"
                )
        else:
            factory.make_DNSData(
                dnsresource=dnsdata.dnsresource, rrtype=dnsdata.rrtype
            )
            self.assertEqual(
                2,
                DNSData.objects.filter(
                    dnsresource=dnsdata.dnsresource
                ).count(),
            )


class TestDNSDataMapping(MAASServerTestCase):
    """Tests for get_hostname_dnsdata_mapping()."""

    def make_mapping(self, dnsresource, raw_ttl=False):
        if dnsresource.name == "@" and dnsresource.domain.name.find(".") >= 0:
            h_name, d_name = dnsresource.domain.name.split(".", 1)
            nodes = Node.objects.filter(hostname=h_name, domain__name=d_name)
        else:
            h_name = dnsresource.name
            # Yes, dnsrr.name='@' and domain.name='maas' hits this, and we find
            # nothing, which is what we need to find.
            nodes = Node.objects.filter(
                hostname=h_name, domain=dnsresource.domain
            )
        if nodes.exists():
            node = nodes.first()
            system_id = node.system_id
            node_type = node.node_type
        else:
            system_id = None
            node_type = None
        mapping = HostnameRRsetMapping(
            system_id=system_id,
            node_type=node_type,
            dnsresource_id=dnsresource.id,
        )
        for data in dnsresource.dnsdata_set.all():
            if raw_ttl or data.ttl is not None:
                ttl = data.ttl
            elif dnsresource.domain.ttl is not None:
                ttl = dnsresource.domain.ttl
            else:
                ttl = Config.objects.get_config("default_dns_ttl")
            mapping.rrset.add((ttl, data.rrtype, data.rrdata, data.id))
        return {dnsresource.name: mapping}

    def test_get_hostname_dnsdata_mapping_returns_mapping(self):
        domain = Domain.objects.get_default_domain()
        expected_mapping = {}
        # Create 3 labels with 0-5 resources each, verify that they
        # Come back correctly.
        for _ in range(3):
            name = factory.make_name("label")
            dnsrr = factory.make_DNSResource(
                name=name, domain=domain, no_ip_addresses=True
            )
            for count in range(random.randint(1, 5)):  # noqa: B007
                factory.make_DNSData(dnsresource=dnsrr, ip_addresses=True)
            expected_mapping.update(self.make_mapping(dnsrr))
        # Add one resource to the domain which has no data, so it should not be
        # in the returned mapping.
        factory.make_DNSResource(domain=domain, no_ip_addresses=True)
        actual = DNSData.objects.get_hostname_dnsdata_mapping(domain)
        self.assertEqual(expected_mapping, actual)

    def test_get_hostname_dnsdata_mapping_includes_node_owner_id(self):
        domain = Domain.objects.get_default_domain()
        user = factory.make_User()
        node_name = factory.make_name("node")
        factory.make_Node_with_Interface_on_Subnet(
            hostname=node_name, domain=domain, owner=user
        )
        dnsrr = factory.make_DNSResource(domain=domain, name=node_name)
        factory.make_DNSData(dnsresource=dnsrr, ip_addresses=True)
        mapping = DNSData.objects.get_hostname_dnsdata_mapping(domain)
        self.assertEqual(mapping[node_name].user_id, user.id)

    def test_get_hostname_dnsdata_mapping_returns_mapping_at_domain(self):
        parent = Domain.objects.get_default_domain()
        name = factory.make_name("node")
        d_name = f"{name}.{parent.name}"
        domain = factory.make_Domain(name=d_name)
        expected_mapping = {}
        # Make a node that is at the top of the domain, and a couple others.
        dnsrr = factory.make_DNSResource(
            name="@", domain=domain, no_ip_addresses=True
        )
        factory.make_DNSData(dnsresource=dnsrr, ip_addresses=True)
        factory.make_Node_with_Interface_on_Subnet(
            hostname=name, domain=parent
        )
        expected_mapping.update(self.make_mapping(dnsrr))
        # Add one resource to the domain which has no data, so it should not be
        # in the returned mapping.
        factory.make_DNSResource(domain=domain, no_ip_addresses=True)
        actual = DNSData.objects.get_hostname_dnsdata_mapping(domain)
        self.assertEqual(expected_mapping, actual)
        # We are done with dnsrr from the child domain's perspective, make it
        # look like it would if it were in the parent domain.
        dnsrr.name = name
        dnsrr.domain = parent
        expected_parent = self.make_mapping(dnsrr)
        actual_parent = DNSData.objects.get_hostname_dnsdata_mapping(parent)
        self.assertEqual(expected_parent, actual_parent)

    def test_get_hostname_dnsdata_mapping_handles_ttl(self):
        # We create 2 domains, one with a ttl, one withoout.
        # Within each domain, create an RRset with and without ttl.
        global_ttl = random.randint(1, 99)
        Config.objects.set_config("default_dns_ttl", global_ttl)
        domains = [
            factory.make_Domain(),
            factory.make_Domain(ttl=random.randint(100, 199)),
        ]
        for dom in domains:
            factory.make_DNSData(domain=dom)
            factory.make_DNSData(domain=dom, ttl=random.randint(200, 299))
            expected_mapping = {}
            for dnsrr in dom.dnsresource_set.all():
                expected_mapping.update(self.make_mapping(dnsrr))
            actual = DNSData.objects.get_hostname_dnsdata_mapping(dom)
            self.assertEqual(expected_mapping, actual)

    def test_get_hostname_dnsdata_mapping_returns_raw_ttl(self):
        # We create 2 domains, one with a ttl, one withoout.
        # Within each domain, create an RRset with and without ttl.
        # We then query with raw_ttl=True, and confirm that nothing is
        # inherited.
        global_ttl = random.randint(1, 99)
        Config.objects.set_config("default_dns_ttl", global_ttl)
        domains = [
            factory.make_Domain(),
            factory.make_Domain(ttl=random.randint(100, 199)),
        ]
        for dom in domains:
            factory.make_DNSData(domain=dom)
            factory.make_DNSData(domain=dom, ttl=random.randint(200, 299))
            expected_mapping = {}
            for dnsrr in dom.dnsresource_set.all():
                expected_mapping.update(self.make_mapping(dnsrr, raw_ttl=True))
            actual = DNSData.objects.get_hostname_dnsdata_mapping(
                dom, raw_ttl=True
            )
            self.assertEqual(expected_mapping, actual)
