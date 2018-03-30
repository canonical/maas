/* Copyright 2016 Canonical Ltd.  This software is licensed under the
 * GNU Affero General Public License version 3 (see the file LICENSE).
 *
 * Unit tests for DomainsManager.
 */


describe("DomainsManager", function() {

    // Load the MAAS module.
    beforeEach(module("MAAS"));

    // Load the DomainsManager.
    var DomainsManager;
    beforeEach(inject(function($injector) {
        DomainsManager = $injector.get("DomainsManager");
        RegionConnection = $injector.get("RegionConnection");
    }));

    // Make a random domain.
    function makeDomain(id, selected) {
        var domain = {
            name: makeName("name"),
            authoritative: true
        };
        if(angular.isDefined(id)) {
            domain.id = id;
        } else {
            domain.id = makeInteger(1, 100);
        }
        if(angular.isDefined(selected)) {
            domain.$selected = selected;
        }
        return domain;
    }

    it("set requires attributes", function() {
        expect(DomainsManager._pk).toBe("id");
        expect(DomainsManager._handler).toBe("domain");
    });

    describe("getDefaultDomain", function() {
        it("returns null when no domains", function() {
            expect(DomainsManager.getDefaultDomain()).toBe(null);
        });

        it("getDefaultDomain returns domain with id = 0", function() {
            var zero = makeDomain(0);
            DomainsManager._items.push(makeDomain());
            DomainsManager._items.push(zero);
            expect(DomainsManager.getDefaultDomain()).toBe(zero);
        });

        it("getDefaultDomain returns first domain otherwise", function() {
            var i;
            for(i=0;i<3;i++) {
                DomainsManager._items.push(makeDomain());
            }
            expect(DomainsManager.getDefaultDomain()).toBe(
                DomainsManager._items[0]);
        });
    });

    describe("createDNSRecord", function() {
        it("calls create_address_record for A record", function() {
            spyOn(RegionConnection, "callMethod");
            var record = {
                'rrtype': 'A',
                'rrdata': '192.168.0.1'
            };
            DomainsManager.createDNSRecord(record);
            expect(RegionConnection.callMethod).toHaveBeenCalledWith(
                "domain.create_address_record", record);
        });

        it("calls create_address_record for AAAA record", function() {
            spyOn(RegionConnection, "callMethod");
            var record = {
                'rrtype': 'AAAA',
                'rrdata': '2001:db8:1'
            };
            DomainsManager.createDNSRecord(record);
            expect(RegionConnection.callMethod).toHaveBeenCalledWith(
                "domain.create_address_record", record);
        });

        it("converts rrdata into list for A and AAAA", function() {
            spyOn(RegionConnection, "callMethod");
            var record = {
                'rrtype': 'AAAA',
                'rrdata': '2001:db8::1, 10.0.0.1 127.0.0.1'
            };
            DomainsManager.createDNSRecord(record);
            expect(record.ip_addresses).toEqual([
                '2001:db8::1', '10.0.0.1', '127.0.0.1'
            ]);
        });

        it("calls create_dnsdata for other types", function() {
            spyOn(RegionConnection, "callMethod");
            var record = {
                'rrtype': 'SRV'
            };
            DomainsManager.createDNSRecord(record);
            expect(RegionConnection.callMethod).toHaveBeenCalledWith(
                "domain.create_dnsdata", record);
        });
    });

    describe("getDomainByName", function() {
        it("returns null when no domains", function() {
            expect(DomainsManager.getDomainByName('meh')).toBe(null);
        });

        it("getDefaultDomain returns named domain", function() {
            var zero = makeDomain(0);
            DomainsManager._items.push(makeDomain(1));
            DomainsManager._items.push(zero);
            var ours = makeDomain(5);
            DomainsManager._items.push(ours);
            DomainsManager._items.push(makeDomain(3));
            expect(DomainsManager.getDomainByName(ours.name)).toBe(ours);
        });

        it("getDefaultDomain returns null when not found", function() {
            var i;
            for(i=0;i<3;i++) {
                DomainsManager._items.push(makeDomain());
            }
            expect(DomainsManager.getDomainByName("notname")).toBe(null);
        });
    });
});
