/* Copyright 2015 Canonical Ltd.  This software is licensed under the
 * GNU Affero General Public License version 3 (see the file LICENSE).
 *
 * Unit tests for ZonesManager.
 */


describe("ZonesManager", function() {

    // Load the MAAS module.
    beforeEach(module("MAAS"));

    // Load the ZonesManager.
    var ZonesManager;
    beforeEach(inject(function($injector) {
        ZonesManager = $injector.get("ZonesManager");
    }));

    it("set requires attributes", function() {
        expect(ZonesManager._pk).toBe("id");
        expect(ZonesManager._handler).toBe("zone");
    });
});
