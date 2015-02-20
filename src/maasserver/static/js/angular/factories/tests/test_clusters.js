/* Copyright 2015 Canonical Ltd.  This software is licensed under the
 * GNU Affero General Public License version 3 (see the file LICENSE).
 *
 * Unit tests for ClustersManager.
 */


describe("ClustersManager", function() {

    // Load the MAAS module.
    beforeEach(module("MAAS"));

    // Load the ClustersManager.
    var ClustersManager;
    beforeEach(inject(function($injector) {
        ClustersManager = $injector.get("ClustersManager");
    }));

    it("set requires attributes", function() {
        expect(ClustersManager._pk).toBe("id");
        expect(ClustersManager._handler).toBe("cluster");
    });
});
