/* Copyright 2015 Canonical Ltd.  This software is licensed under the
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

    it("set requires attributes", function() {
        expect(DomainsManager._pk).toBe("id");
        expect(DomainsManager._handler).toBe("domain");
    });
});
