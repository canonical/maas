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
});
